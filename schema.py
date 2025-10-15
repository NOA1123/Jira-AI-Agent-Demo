from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class GivenWhenThen(BaseModel):
    given: str
    when: str
    then: str

class StoryDescription(BaseModel):
    asA: str = Field(..., alias="asA")
    iWant: str
    soThat: str

class Story(BaseModel):
    id: Optional[str] = None
    featureId: Optional[str] = None
    title: str
    description: StoryDescription
    acceptanceCriteria: List[GivenWhenThen]
    storyPoints: Literal[1,2,3,5,8,13]

class TestCase(BaseModel):
    id: str
    storyId: str
    preconditions: str
    steps: List[str]
    expected: str

class Feature(BaseModel):
    id: str = ""
    key: Optional[str] = None
    title: str
    description: Optional[str] = ""

class StoriesRequest(BaseModel):
    features: List[Feature]

class TestsRequest(BaseModel):
    stories: List[Story]
