import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ProspectIn(BaseModel):
    # str_strip_whitespace: "  Laura " se guarda como "Laura", y "   " cuenta como vacío.
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)

class ReportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prospect: ProspectIn
    meeting_goal: str | None = Field(default=None, max_length=1000)

class ProspectRead(BaseModel):
    # from_attributes: permite construir este schema directamente desde un modelo SQLAlchemy.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    company: str
    role: str | None

class ReportCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str

class ReportSummary(BaseModel):
    """Versión liviana para listados: no incluye el Markdown, que puede ser largo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    prospect: ProspectRead
    created_at: datetime
    finished_at: datetime | None

class ReportRead(ReportSummary):
    meeting_goal: str | None
    markdown: str | None
    error: str | None
    model: str
    input_tokens: int
    output_tokens: int

class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_number: int
    kind: str
    tool_name: str | None
    payload: dict[str, Any]
    created_at: datetime