from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["internal_question", "bug_report", "feature_request", "status_update", "meeting_request", "noise"]
Priority = Literal["low", "medium", "high", "critical"]


class TriageResultJSON(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevant: bool
    category: Category
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    suggested_action: str = Field(min_length=1)
    suggested_reply: str = Field(min_length=1)
    needs_human_approval: bool
