import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import new_uuid, utcnow

if TYPE_CHECKING:
    from app.models.agent_step import AgentStep
    from app.models.prospect import Prospect

class ReportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

#La lista de estados válidos se escribe una sola vez (en el enum) y de ahí sale el CHECK.
_VALID_STATUSES = ", ".join(repr(s.value) for s in ReportStatus)

class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (CheckConstraint(f"status IN ({_VALID_STATUSES})", name="status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    prospect_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True
    )
    meeting_goal: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        default=ReportStatus.PENDING.value,
        server_default=ReportStatus.PENDING.value,
    )
    markdown: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #Índice para el historial. Un índice B-tree también sirve para ORDER BY ... DESC:
    #PostgreSQL puede recorrerlo al revés, así que no hace falta declararlo descendente.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    prospect: Mapped["Prospect"] = relationship(back_populates="reports")
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="AgentStep.step_number",
    )