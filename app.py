import os
import json
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import FastAPI, Body, UploadFile, File, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv
from pydantic import ValidationError

from schema import Feature, StoriesRequest, Story, TestsRequest, TestCase
from utils import basic_auth_header, features_to_baseline_stories, stories_to_baseline_tests

# -------------------------------------------------------------------
# .env loading
# -------------------------------------------------------------------
ENV_FILE = find_dotenv(filename=".env", usecwd=True)
if ENV_FILE:
    load_dotenv(ENV_FILE, override=True)
else:
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

def _mask(s: Optional[str]):
    if not s:
        return None
    s = s.strip()
    return s[:4] + "..." + s[-4:] if len(s) > 8 else "********"

print("[ENV] JIRA_BASE_URL =", os.getenv("JIRA_BASE_URL"))
print("[ENV] JIRA_EMAIL    =", os.getenv("JIRA_EMAIL"))
print("[ENV] JIRA_API_TOKEN=", _mask(os.getenv("JIRA_API_TOKEN")))
print("[ENV] GEMINI_API_KEY=", _mask(os.getenv("GEMINI_API_KEY")))

# -------------------------------------------------------------------
# Gemini client
# -------------------------------------------------------------------
try:
    import google.generativeai as genai
except ImportError:
    raise RuntimeError("Please install google-generativeai: pip install google-generativeai")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    _gemini_model = genai.GenerativeModel("gemini-2.5-flash")  # stable model name
else:
    print("Missing GEMINI_API_KEY in .env")
    _gemini_model = None

def llm_available() -> bool:
    return _gemini_model is not None

def _gemini_json(system: str, user: str) -> list:
    if not _gemini_model:
        raise RuntimeError("Gemini not configured.")
    prompt = f"{system}\n\nUSER INPUT:\n{user}\n\nReturn ONLY valid JSON (no markdown)."
    resp = _gemini_model.generate_content(prompt)
    text = (getattr(resp, "text", "") or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)

# -------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------
app = FastAPI(title="AI + Jira Backend (Gemini)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

STATE = {"features": [], "stories": [], "tests": []}
LAST_AI_ENGINE = "unknown"
LAST_AI_ERROR = None

@app.get("/")
def home():
    return {"ok": True, "msg": "Running (Gemini)."}

@app.get("/__env_check")
def __env_check():
    return {
        "JIRA_BASE_URL": os.getenv("JIRA_BASE_URL"),
        "JIRA_EMAIL": os.getenv("JIRA_EMAIL"),
        "JIRA_API_TOKEN": "***MASKED***" if os.getenv("JIRA_API_TOKEN") else None,
        "GEMINI_API_KEY": "***MASKED***" if os.getenv("GEMINI_API_KEY") else None,
    }

@app.get("/__ai_engine")
def __ai_engine():
    return {"engine": LAST_AI_ENGINE, "error": LAST_AI_ERROR}

# -------------------------------------------------------------------
# Jira ingestion
# -------------------------------------------------------------------
def _plain_desc(desc):
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict) and desc.get("type") == "doc":
        parts = []
        for node in desc.get("content", []):
            if isinstance(node, dict):
                for sub in node.get("content", []):
                    if isinstance(sub, dict) and sub.get("type") == "text":
                        parts.append(sub.get("text", ""))
        return " ".join(parts)
    return ""

@app.post("/ingest/jira")
async def ingest_jira(jql: str = Body(..., embed=True)):
    base = os.getenv("JIRA_BASE_URL")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if not all([base, email, token]):
        return {"error": "Missing JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN in .env"}

    url = f"{base}/rest/api/3/search/jql"
    headers = {"Authorization": basic_auth_header(email, token), "Accept": "application/json"}
    payload = {"jql": jql, "fields": ["summary", "description", "issuetype", "key"], "maxResults": 50}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            print("[JIRA] POST", url, "payload:", payload)
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        return {"error": f"Jira request failed: {e}"}

    feats: List[Feature] = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        if (fields.get("issuetype", {}) or {}).get("name", "").lower() != "epic":
            continue
        feats.append(Feature(
            id=issue.get("id",""),
            key=issue.get("key"),
            title=(fields.get("summary") or "").strip(),
            description=_plain_desc(fields.get("description"))
        ))

    STATE["features"] = [f.model_dump() for f in feats]
    return {"count": len(STATE["features"]), "features": STATE["features"]}

# -------------------------------------------------------------------
# Mock ingestion
# -------------------------------------------------------------------
@app.post("/ingest/mock")
async def ingest_mock(file: UploadFile = File(...)):
    raw = await file.read()
    data = json.loads(raw)
    feats = [Feature(**f) for f in data.get("features", [])]
    STATE["features"] = [f.model_dump() for f in feats]
    return {"count": len(STATE["features"]), "features": STATE["features"]}

# -------------------------------------------------------------------
# Normalizer for TestCase shape
# -------------------------------------------------------------------
def _normalize_testcase(t: dict, story_id_fallback: str = "S") -> dict:
    """Coerce Gemini output into valid TestCase fields."""
    t = dict(t or {})

    # steps: ensure list[str]
    steps = t.get("steps")
    if isinstance(steps, str):
        steps = [steps]
    elif not isinstance(steps, list):
        steps = []
    t["steps"] = [str(s) for s in steps]

    # expected: force str
    exp = t.get("expected")
    if isinstance(exp, list):
        exp = " ".join(str(x) for x in exp)
    elif exp is None:
        exp = ""
    t["expected"] = str(exp)

    # preconditions: force str
    prec = t.get("preconditions")
    t["preconditions"] = str(prec or "")

    # ids
    t["storyId"] = str(t.get("storyId") or story_id_fallback)
    t["id"] = str(t.get("id") or f"TC-{t['storyId']}-{len(t['steps']) or 1}")
    return t

# -------------------------------------------------------------------
# AI: Stories
# -------------------------------------------------------------------
# ── Normalizers for Stories ─────────────────────────────────────
_FIB_ALLOWED = [1, 2, 3, 5, 8, 13]

def _to_fib(value) -> int:
    """Coerce any number/string into the nearest allowed Fibonacci point (ties → lower)."""
    try:
        n = int(str(value).strip())
    except Exception:
        return 3
    best = min(_FIB_ALLOWED, key=lambda v: (abs(v - n), v))
    return best

def _normalize_gwt(item: dict) -> dict:
    """Normalize AC item to {given, when, then} strings."""
    if not isinstance(item, dict):
        item = {}
    given = item.get("given") or item.get("Given") or item.get("precondition") or item.get("context") or ""
    when  = item.get("when")  or item.get("When")  or item.get("action")       or item.get("event")    or ""
    then  = item.get("then")  or item.get("Then")  or item.get("outcome")      or item.get("result")   or ""
    return {
        "given": str(given).strip(),
        "when":  str(when).strip(),
        "then":  str(then).strip(),
    }

def _normalize_story(s: dict, feature_fallback) -> dict:
    """
    Coerce AI story into your schema:
      - featureId: string
      - title: string
      - description: {asA,iWant,soThat}
      - acceptanceCriteria: list[{given,when,then}]
      - storyPoints: 1|2|3|5|8|13
      (caller sets 'id' later)
    """
    s = dict(s or {})

    # featureId
    feature_id = (
        s.get("featureId")
        or getattr(feature_fallback, "id", None)
        or getattr(feature_fallback, "key", None)
        or getattr(feature_fallback, "title", None)
        or "F"
    )

    # title
    title = (s.get("title") or "").strip()
    if not title:
        ft = getattr(feature_fallback, "title", "") or "feature"
        title = f"Implement {ft}".strip()

    # description
    desc = s.get("description")
    if isinstance(desc, dict):
        asA    = (desc.get("asA")    or desc.get("role") or "end-user").strip()
        iWant  = (desc.get("iWant")  or desc.get("goal") or getattr(feature_fallback, "title", "") or "use the feature").strip()
        soThat = (desc.get("soThat") or desc.get("why")  or "I get value quickly").strip()
    else:
        asA, iWant, soThat = "end-user", (getattr(feature_fallback, "title", "") or "use the feature"), "I get value quickly"
    description = {"asA": asA, "iWant": iWant, "soThat": soThat}

    # acceptanceCriteria
    ac = s.get("acceptanceCriteria") or s.get("acceptance_criteria") or s.get("AC") or []
    if isinstance(ac, dict):
        ac = [ac]
    if not isinstance(ac, list):
        ac = []
    ac_norm = [_normalize_gwt(x) for x in ac if x is not None]
    if not ac_norm:
        ft = getattr(feature_fallback, "title", "") or "the feature"
        ac_norm = [
            _normalize_gwt({"given": "valid input",   "when": f"I use {ft.lower()}", "then": "the system completes successfully"}),
            _normalize_gwt({"given": "invalid input", "when": f"I use {ft.lower()}", "then": "a clear validation message is shown"}),
        ]

    # storyPoints
    sp = _to_fib(s.get("storyPoints"))

    return {
        "featureId": str(feature_id).strip() or "F",
        "title": title,
        "description": description,
        "acceptanceCriteria": ac_norm,
        "storyPoints": sp,
    }

@app.post("/generate/stories")
async def generate_stories(req: StoriesRequest):
    global LAST_AI_ENGINE, LAST_AI_ERROR
    features = req.features
    stories: List[Story] = []

    # Fallback if Gemini unavailable
    if not llm_available():
        LAST_AI_ENGINE = "fallback"
        stories = features_to_baseline_stories(features)
        STATE["stories"] = [s.model_dump() for s in stories]
        return {"count": len(stories), "engine": LAST_AI_ENGINE, "stories": STATE["stories"]}

    try:
        system = (
            "You are an Agile Business Analyst. "
            "Convert each FEATURE into 1–3 user stories with title, description {asA,iWant,soThat}, "
            "2–4 acceptanceCriteria items {given,when,then}, and storyPoints ∈ {1,2,3,5,8,13}. "
            "Return ONLY a JSON array (no markdown, no explanations)."
        )
        user = "FEATURES_JSON:\n" + json.dumps([f.model_dump() for f in features], ensure_ascii=False)
        raw = _gemini_json(system, user)
        LAST_AI_ENGINE, LAST_AI_ERROR = "gemini", None

        # Ensure iterable array
        if isinstance(raw, dict):
            raw = [raw]
        elif not isinstance(raw, list):
            raw = []

        default_feature = features[0] if features else None
        for idx, s in enumerate(raw, start=1):
            ns = _normalize_story(s, default_feature)
            ns["id"] = s.get("id") or f"S-{idx:03d}"
            if not ns.get("featureId"):
                ns["featureId"] = (
                    default_feature.id or default_feature.key or default_feature.title or "F"
                ) if default_feature else "F"
            stories.append(Story(**ns))  # Pydantic validation here

    except Exception as e:
        LAST_AI_ENGINE = "fallback"
        LAST_AI_ERROR = str(e)
        stories = features_to_baseline_stories(features)

    STATE["stories"] = [s.model_dump() for s in stories]
    return {"count": len(stories), "engine": LAST_AI_ENGINE, "stories": STATE["stories"]}


# -------------------------------------------------------------------
# AI: Tests (with normalization)
# ---------#----------------------------------------------------------
def _normalize_testcase(t: dict, story_id_fallback: str = "S") -> dict:
    """
    Coerce AI output into the exact schema for TestCase:
      - steps: list[str]
      - expected: str (never list)
      - preconditions: str
      - id, storyId: strings with sensible fallbacks
    """
    t = dict(t or {})

    # steps → list[str], trimmed and cleaned
    steps = t.get("steps")
    if isinstance(steps, str):
        steps = [steps]
    elif not isinstance(steps, list):
        steps = []
    steps = [str(s).strip() for s in steps if s is not None and str(s).strip()]
    t["steps"] = steps

    # expected → str (never list)
    exp = t.get("expected")
    if isinstance(exp, list):
        exp = " ".join(str(x).strip() for x in exp if x is not None and str(x).strip())
    elif exp is None:
        exp = ""
    t["expected"] = str(exp).strip()

    # preconditions → str
    prec = t.get("preconditions")
    t["preconditions"] = ("" if prec is None else str(prec)).strip()

    # ids
    sid = (t.get("storyId") or story_id_fallback or "S")
    t["storyId"] = str(sid).strip() or "S"
    tid = t.get("id")
    if not isinstance(tid, str) or not tid.strip():
        t["id"] = f"TC-{t['storyId']}-{max(1, len(t['steps']))}"

    return t


@app.post("/generate/tests")
async def generate_tests(req: TestsRequest):
    """
    Generate manual test cases using Gemini AI or fallback templates.
    This version includes a normalization step to prevent Pydantic validation errors.
    """
    global LAST_AI_ENGINE, LAST_AI_ERROR
    stories = req.stories
    tests: List[TestCase] = []

    # 1️⃣ Fallback if Gemini unavailable
    if not llm_available():
        LAST_AI_ENGINE = "fallback"
        tests = stories_to_baseline_tests(stories)
        STATE["tests"] = [t.model_dump() for t in tests]
        return {"count": len(tests), "engine": LAST_AI_ENGINE, "tests": STATE["tests"]}

    # 2️⃣ Try Gemini
    try:
        system = (
            "You are a QA Engineer. Generate 2–3 manual test cases per story with: "
            "id, storyId, preconditions, steps[], expected (expected MUST be a single string). "
            "Return ONLY JSON array (no markdown, no explanations)."
        )
        user = "STORIES_JSON:\n" + json.dumps([s.model_dump() for s in stories], ensure_ascii=False)
        raw = _gemini_json(system, user)
        LAST_AI_ENGINE = "gemini"

        # Ensure iterable list
        if isinstance(raw, dict):
            raw = [raw]
        elif not isinstance(raw, list):
            raw = []

        # Normalize output before validation
        story_id_default = stories[0].id if stories else "S"
        normalized = [_normalize_testcase(t, story_id_default) for t in raw]
        for t in normalized:
            tests.append(TestCase(**t))

    # 3️⃣ Fallback on error
    except Exception as e:
        LAST_AI_ENGINE = "fallback"
        LAST_AI_ERROR = str(e)
        tests = stories_to_baseline_tests(stories)

    # 4️⃣ Save + respond
    STATE["tests"] = [t.model_dump() for t in tests]
    return {"count": len(tests), "engine": LAST_AI_ENGINE, "tests": STATE["tests"]}


# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------
@app.get("/export")
def export(fmt: str = Query("json")):
    if fmt == "json":
        return {"features": STATE["features"], "stories": STATE["stories"], "tests": STATE["tests"]}
    elif fmt == "md":
        out = ["# Generated Stories & Tests\n"]
        for s in STATE["stories"]:
            d = s.get("description", {})
            out.append(f"## {s.get('id')} - {s.get('title')}")
            out.append(f"As a {d.get('asA')}, I want {d.get('iWant')} so that {d.get('soThat')}.")
        return {"markdown": "\n".join(out)}
    else:
        return {"error": f"Unsupported format: {fmt}"}


