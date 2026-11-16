import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.exceptions import ReportNotFoundError
from app.models import AgentStep, Prospect, Report, ReportStatus
from app.schemas.report import ReportCreate

class ReportService:
    """Casos de uso de los informes. No sabe nada de HTTP."""

    def __init__(self, db: Session, model_name: str) -> None:
        self.db = db
        self.model_name = model_name

    def create_report(self, data: ReportCreate) -> Report:
        prospect = Prospect(**data.prospect.model_dump())
        report = Report(
            prospect=prospect,
            meeting_goal=data.meeting_goal,
            status=ReportStatus.PENDING.value,
            model=self.model_name,
        )
        # Una sola transacción: o se guardan el prospecto y el informe, o ninguno.
        self.db.add(report)
        self.db.commit()
        return report

    def get_report(self, report_id: uuid.UUID) -> Report:
        stmt = select(Report).options(joinedload(Report.prospect)).where(Report.id == report_id)
        report = self.db.execute(stmt).scalar_one_or_none()
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    def list_reports(self, limit: int, offset: int) -> list[Report]:
        # joinedload trae el prospecto en la misma consulta. Sin él, listar N informes haría
        # 1 consulta + N más (el problema "N+1").
        stmt = (
            select(Report)
            .options(joinedload(Report.prospect))
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def list_steps(self, report_id: uuid.UUID) -> list[AgentStep]:
        exists = self.db.scalar(select(Report.id).where(Report.id == report_id))
        if exists is None:
            raise ReportNotFoundError(report_id)
        stmt = (
            select(AgentStep)
            .where(AgentStep.report_id == report_id)
            .order_by(AgentStep.step_number)
        )
        return list(self.db.scalars(stmt))

    def delete_report(self, report_id: uuid.UUID) -> None:
        report = self.db.get(Report, report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        self.db.delete(report)
        self.db.commit()