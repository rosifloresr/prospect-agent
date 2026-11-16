import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from sqlalchemy import ( CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func,)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import BigIntPK, JsonPayload, utcnow

if TYPE_CHECKING:
    from app.models.report import Report

class StepKind(StrEnum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL = "final"

_VALID_KINDS = ", ".join(repr(k.value) for k in StepKind)

class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        #Garantiza que dentro de un informe no haya dos pasos con el mismo número.
        UniqueConstraint("report_id", "step_number", name="report_step"),
        CheckConstraint(f"kind IN ({_VALID_KINDS})", name="kind_valid"),
    )

    #Entero autoincremental: nunca aparece en una URL, así que no necesita ser inadivinable.
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("reports.id", ondelete="CASCADE"))
    step_number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    tool_name: Mapped[str | None] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonPayload)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    report: Mapped["Report"] = relationship(back_populates="steps")