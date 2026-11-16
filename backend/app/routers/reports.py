import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.schemas.report import (
    AgentStepRead,
    ReportCreate,
    ReportCreated,
    ReportRead,
    ReportSummary,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["informes"])

def get_report_service(db: Annotated[Session, Depends(get_db)]) -> ReportService:
    return ReportService(db, model_name=get_settings().anthropic_model)

ServiceDep = Annotated[ReportService, Depends(get_report_service)]

# 202 Accepted y no 201 Created: este endpoint pide un trabajo que se procesa aparte.
# Todavía no hay agente (Fase 5), pero fijamos el contrato ahora para no cambiarlo después.
@router.post("", response_model=ReportCreated, status_code=202)
def create_report(payload: ReportCreate, service: ServiceDep):
    return service.create_report(payload)

@router.get("", response_model=list[ReportSummary])
def list_reports(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return service.list_reports(limit=limit, offset=offset)

@router.get("/{report_id}", response_model=ReportRead)
def get_report(report_id: uuid.UUID, service: ServiceDep):
    return service.get_report(report_id)

@router.get("/{report_id}/steps", response_model=list[AgentStepRead])
def list_steps(report_id: uuid.UUID, service: ServiceDep):
    return service.list_steps(report_id)

@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: uuid.UUID, service: ServiceDep) -> None:
    service.delete_report(report_id)