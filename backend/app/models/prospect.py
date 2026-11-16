import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import new_uuid, utcnow

if TYPE_CHECKING:
    from app.models.report import Report

class Prospect(Base):
    __tablename__ = "prospects"

    # UUID y no un entero secuencial: el id aparece en URLs y no debe poder adivinarse.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(120))
    role: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    reports: Mapped[list["Report"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )