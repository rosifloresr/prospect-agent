import uuid
from typing import Any, Protocol
from sqlalchemy.orm import Session
from app.models import AgentStep, StepKind

class StepRecorder(Protocol):
    """Quien quiera enterarse de cada paso del agente (la base, la consola, un test)."""

    def record(self, kind: StepKind, tool_name: str | None, payload: dict[str, Any]) -> None: ...

class NullRecorder:
    """No registra nada. Es el valor por defecto: el agente no necesita una base para funcionar."""

    def record(self, kind: StepKind, tool_name: str | None, payload: dict[str, Any]) -> None:
        return None

class DbStepRecorder:
    """Guarda cada paso como una fila de agent_steps, numerada en orden."""

    def __init__(self, db: Session, report_id: uuid.UUID) -> None:
        self._db = db
        self._report_id = report_id
        self._next_number = 1

    def record(self, kind: StepKind, tool_name: str | None, payload: dict[str, Any]) -> None:
        self._db.add(
            AgentStep(
                report_id=self._report_id,
                step_number=self._next_number,
                kind=kind.value,
                tool_name=tool_name,
                payload=payload,
            )
        )
        # Un commit por paso: quien consulte el informe mientras corre ve el avance en vivo.
        self._db.commit()
        self._next_number += 1