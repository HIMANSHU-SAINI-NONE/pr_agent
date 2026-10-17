from typing import Optional
from typing_extensions import TypedDict, NotRequired

class AgentState(TypedDict):
    task: str
    code: NotRequired[Optional[str]]
    error: NotRequired[Optional[str]]
    iterations: NotRequired[int]
    feedback: NotRequired[Optional[str]]