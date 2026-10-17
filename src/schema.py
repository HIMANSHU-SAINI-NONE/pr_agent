from pydantic import BaseModel, Field

class code_base(BaseModel):
    explaination: str = Field(
        description="A concise rationale explaining the algorithmic approach and logic."
    )
    code: str = Field(
        description="Executable, self-contained Python code including assert statements for tests."
    )