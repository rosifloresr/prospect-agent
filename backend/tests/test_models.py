import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.models import AgentStep, Prospect, Report, ReportStatus, StepKind

def make_report(db, **overrides) -> Report:
    prospect = Prospect(name="Laura Gómez", company="Acme")
    report = Report(prospect=prospect, model="modelo-de-prueba", **overrides)
    db.add(report)
    db.commit()
    return report

def add_step(db, report, number, kind=StepKind.TOOL_CALL.value) -> AgentStep:
    step = AgentStep(report_id=report.id, step_number=number, kind=kind, payload={"n": number})
    db.add(step)
    db.commit()
    return step

def test_un_informe_nuevo_queda_pending_y_con_contadores_en_cero(db_session):
    report = make_report(db_session)
    assert report.status == "pending"
    assert report.input_tokens == 0
    assert report.output_tokens == 0
    assert report.id is not None

@pytest.mark.parametrize("status", [s.value for s in ReportStatus])
def test_acepta_todos_los_estados_validos(db_session, status):
    report = make_report(db_session, status=status)
    assert report.status == status

def test_un_estado_inventado_viola_el_check(db_session):
    with pytest.raises(IntegrityError):
        make_report(db_session, status="inventado")

def test_un_tipo_de_paso_inventado_viola_el_check(db_session):
    report = make_report(db_session)
    with pytest.raises(IntegrityError):
        add_step(db_session, report, 1, kind="inventado")

def test_dos_pasos_con_el_mismo_numero_violan_la_restriccion_unique(db_session):
    report = make_report(db_session)
    add_step(db_session, report, 1)
    with pytest.raises(IntegrityError):
        add_step(db_session, report, 1)


def test_borrar_un_informe_borra_sus_pasos(db_session):
    report = make_report(db_session)
    add_step(db_session, report, 1)
    add_step(db_session, report, 2)

    db_session.delete(report)
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(AgentStep)) == 0

def test_borrar_un_prospecto_borra_sus_informes(db_session):
    report = make_report(db_session)
    db_session.delete(report.prospect)
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(Report)) == 0