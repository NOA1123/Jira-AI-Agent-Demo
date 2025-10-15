'''import base64, io, csv
from typing import List
from schema import Feature, Story, TestCase, GivenWhenThen, StoryDescription

def basic_auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")

def estimate_points(title: str) -> int:
    t = title.lower()
    if any(k in t for k in ["error","failed","retry","edge","validation","timeout"]):
        return 3
    if any(k in t for k in ["payment","authentication","auth","sync","email","pdf","export","webhook","integration"]):
        return 5
    return 2

def features_to_baseline_stories(features: List[Feature]) -> List[Story]:
    stories: List[Story] = []
    idx = 1
    for ft in features:
        seeds = [
            ("Implement core flow", [
                {"given":"a valid session","when":"the user performs the main action","then":"the system completes the flow successfully"}
            ]),
            ("Handle validation and errors", [
                {"given":"required fields are missing","when":"the user submits the form","then":"an inline error message is shown"}
            ]),
            ("Confirmation & notification", [
                {"given":"the action completes","when":"the user lands on confirmation","then":"a confirmation message and reference ID are displayed"}
            ]),
        ]
        for title, ac in seeds:
            stories.append(Story(
                id=f"S-{idx:03d}",
                featureId=ft.id or ft.title or "F",
                title=f"{ft.title}: {title}" if ft.title else title,
                description=StoryDescription(asA="end user", iWant=title, soThat="I achieve the goal described by the feature"),
                acceptanceCriteria=[GivenWhenThen(**x) for x in ac],
                storyPoints=estimate_points(title)
            ))
            idx += 1
    return stories

def export_csv(stories: List[Story], tests: List[TestCase]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["TYPE","ID","PARENT","TITLE/DESC","AC_OR_STEPS","POINTS_OR_EXPECTED"])
    for s in stories:
        ac = " | ".join([f"G:{a.given} W:{a.when} T:{a.then}" for a in s.acceptanceCriteria])
        desc = f"As a {s.description.asA} I want {s.description.iWant} so that {s.description.soThat}"
        w.writerow(["STORY", s.id or "", s.featureId or "", f"{s.title} :: {desc}", ac, s.storyPoints])
    for t in tests:
        steps = " | ".join(t.steps)
        w.writerow(["TEST", t.id, t.storyId, t.preconditions, steps, t.expected])
    return buf.getvalue()'''
# backend/utils.py
# backend/utils.py
import base64
from typing import List
from schema import Feature, Story, TestCase, GivenWhenThen, StoryDescription

def basic_auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")

def estimate_points(title: str) -> int:
    """Simple heuristic to vary Fibonacci estimates."""
    t = (title or "").lower()
    if any(k in t for k in ["auth", "login", "signup", "register", "payment", "checkout", "pdf", "export", "email"]):
        return 5
    if any(k in t for k in ["error", "retry", "timeout", "edge", "validation"]):
        return 3
    return 2  # small default

def _mk_ac(items: List[tuple[str, str, str]]) -> List[GivenWhenThen]:
    return [GivenWhenThen(given=g, when=w, then=t) for (g, w, t) in items]
# utils.py
FIB = [1, 2, 3, 5, 8, 13]

def fib_down(n: int) -> int:
    # largest fib <= n
    for v in reversed(FIB):
        if v <= n:
            return v
    return 1

def fib_next_lower(n: int) -> int:
    # next lower fib in the sequence
    i = FIB.index(fib_down(n))
    return FIB[max(0, i-1)]


def features_to_baseline_stories(features: List[Feature]) -> List[Story]:
    """
    Fallback story generator (no AI). Produces 1–2 stories per feature with
    simple G/W/T acceptance criteria and Fibonacci points.
    """
    stories: List[Story] = []
    sid = 1
    for f in features:
        base_title = f.title.strip() if f and f.title else "Feature"

        # Story 1 (happy path)
        points1 = fib_down(estimate_points(base_title))
        s1 = Story(
            id=f"S-{sid:03d}",
            featureId=f.id or f.key or base_title,
            title=f"{base_title}: happy path",
            description=StoryDescription(
                asA="end user",
                iWant=f"to use {base_title.lower()} successfully",
                soThat="I can achieve my goal",
            ),
            acceptanceCriteria=_mk_ac([
                ("valid inputs", "I perform the main action", "the system completes it successfully"),
                ("system is available", "I retry once", "the system responds within 2 seconds"),
            ]),
            storyPoints=points1,
        )
        sid += 1
        stories.append(s1)

        # Optional Story 2 (error handling)
        if (f.description or "").strip():
            points2 = fib_next_lower(points1)
            s2 = Story(
                id=f"S-{sid:03d}",
                featureId=f.id or f.key or base_title,
                title=f"{base_title}: error handling",
                description=StoryDescription(
                    asA="end user",
                    iWant=f"to see clear errors while using {base_title.lower()}",
                    soThat="I can recover and proceed",
                ),
                acceptanceCriteria=_mk_ac([
                    ("invalid inputs", "I submit the form", "I see helpful validation messages"),
                    ("a server error occurs", "I try again", "I see a non-destructive error and can retry"),
                ]),
                storyPoints=points2,
            )
            sid += 1
            stories.append(s2)
    return stories

def stories_to_baseline_tests(stories: List[Story]) -> List[TestCase]:
    """
    Fallback test generator (no AI). One test per story with basic steps.
    """
    tests: List[TestCase] = []
    tid = 1
    for s in stories:
        steps = [
            f"Navigate to the area for '{s.title}'",
            "Provide valid inputs (or reproduce described scenario)",
            "Trigger the main action",
            "Observe system response",
        ]
        expected = "System completes the action successfully without errors"

        st = (s.title or "").lower()
        if any(k in st for k in ["error", "validation", "retry", "fail"]):
            expected = "Clear error shown with guidance; user can retry or recover"

        tcase = TestCase(
            id=f"T-{tid:03d}",
            storyId=s.id or "",
            preconditions="User has access and system is available",
            steps=steps,
            expected=expected,
        )
        tid += 1
        tests.append(tcase)
    return tests
