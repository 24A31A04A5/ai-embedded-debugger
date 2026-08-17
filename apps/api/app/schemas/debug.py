from typing import Literal

from pydantic import BaseModel, Field


class DebugRequest(BaseModel):
    firmware_code: str = Field(..., description="The C/C++ firmware source code.")
    compiler_output: str = Field(default="", description="The compiler error output.")
    serial_logs: str = Field(default="", description="The serial monitor or runtime logs.")


class LikelyCause(BaseModel):
    cause: str = Field(..., description="The potential root cause of the issue.")
    plausibility: Literal["high", "medium", "low"] = Field(
        ..., description="How likely this is to be the actual root cause."
    )


class DebugResponse(BaseModel):
    problem_observed: str = Field(
        ..., description="A concise summary of the problem based on the evidence."
    )
    evidence_used: list[str] = Field(
        ..., description="Key pieces of evidence from the code or logs."
    )
    likely_causes: list[LikelyCause] = Field(
        ..., description="Ranked list of likely causes."
    )
    recommended_steps: list[str] = Field(
        ..., description="Actionable verification or debugging steps."
    )
    proposed_fix: str = Field(
        ..., description="Explanation of the proposed solution."
    )
    corrected_code: str | None = Field(
        default=None, description="The corrected code snippet or patch, if applicable."
    )
    risks_limitations: str | None = Field(
        default=None, description="Risks of the fix or hardware damage warnings."
    )
    follow_up_required: str | None = Field(
        default=None, description="What information is missing to make a confident diagnosis."
    )
