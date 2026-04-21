from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    wechat = "wechat"


class ToneType(str, Enum):
    formal = "formal"
    concise = "concise"


class TimeGranularity(str, Enum):
    year = "year"
    month = "month"
    day = "day"
    hour = "hour"
    range = "range"
    unknown = "unknown"


class TimeRelation(str, Enum):
    deadline = "deadline"
    start_time = "start_time"
    sync_time = "sync_time"
    unknown = "unknown"


class CertaintyLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class WorkStatus(str, Enum):
    in_progress = "in_progress"
    pending = "pending"
    blocked = "blocked"
    unknown = "unknown"


class StructuredTimeInfo(BaseModel):
    raw_text: str | None = None
    normalized_value: str | None = None
    range_start: str | None = None
    range_end: str | None = None
    granularity: TimeGranularity = TimeGranularity.unknown
    relation: TimeRelation = TimeRelation.unknown
    is_uncertain: bool = False
    certainty_level: CertaintyLevel = CertaintyLevel.medium


class AnalyzeRequest(BaseModel):
    source_type: SourceType = SourceType.wechat
    raw_text: str = Field(min_length=1, max_length=20000)
    language: str = "zh-CN"

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("raw_text must not be empty")
        return cleaned


class WorkItem(BaseModel):
    id: str
    summary: str
    details: str
    people: list[str] = Field(default_factory=list)
    schedule: StructuredTimeInfo | None = None
    status: WorkStatus = WorkStatus.unknown
    priority: Literal["high", "medium", "low"] = "medium"
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: str


class AnalyzeResponse(BaseModel):
    summary: str
    work_items: list[WorkItem] = Field(default_factory=list)
    resource_gaps: list[str] = Field(default_factory=list)
    review_flags: list[str] = Field(default_factory=list)


class FollowupRequest(BaseModel):
    summary: str
    work_items: list[WorkItem] = Field(default_factory=list)
    resource_gaps: list[str] = Field(default_factory=list)
    tone: ToneType = ToneType.formal


class FollowupResponse(BaseModel):
    message: str
