#Importar los modelos acá hace que queden registrados en Base.metadata. Alembic y los tests
#dependen de eso para saber qué tablas existen.
from app.models.agent_step import AgentStep, StepKind
from app.models.prospect import Prospect
from app.models.report import Report, ReportStatus

__all__ = ["AgentStep", "Prospect", "Report", "ReportStatus", "StepKind"]