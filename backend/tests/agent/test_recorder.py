import uuid
from datetime import date
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.agent import ProspectAgent
from app.agent.fake import FakeLLM, text_response, tool_response
from app.agent.recorder import DbStepRecorder, NullRecorder
from app.models import AgentStep, Prospect, Report, StepKind
from app.tools import ToolRegistry
from app.tools.read_file import ReadFileTool

@pytest.fixture
def report(db_session) -> Report:
    report = Report(prospect=Prospect(name="Laura Gómez", company="Acme"), model="modelo-de-prueba")
    db_session.add(report)
    db_session.commit()
    return report

def saved_steps(db, report) -> list[AgentStep]:
    stmt = select(AgentStep).where(AgentStep.report_id == report.id).order_by(AgentStep.step_number)
    return list(db.scalars(stmt))

def test_guarda_cada_paso_numerado_desde_uno(db_session, report):
    recorder = DbStepRecorder(db_session, report.id)
    recorder.record(StepKind.TOOL_CALL, "buscar_web", {"input": {"query": "Acme"}})
    recorder.record(StepKind.TOOL_RESULT, "buscar_web", {"is_error": False, "content": "..."})
    recorder.record(StepKind.FINAL, None, {"text": "# Informe"})

    steps = saved_steps(db_session, report)
    assert [s.step_number for s in steps] == [1, 2, 3]
    assert [s.kind for s in steps] == ["tool_call", "tool_result", "final"]
    assert [s.tool_name for s in steps] == ["buscar_web", "buscar_web", None]
    assert steps[0].payload == {"input": {"query": "Acme"}}

def test_cada_paso_se_confirma_en_el_momento(db_session, report):
    DbStepRecorder(db_session, report.id).record(StepKind.FINAL, None, {"text": "x"})
    assert not db_session.in_transaction()  # hubo commit: quien consulte ya ve el paso

def test_el_payload_conserva_los_acentos_y_la_estructura(db_session, report):
    payload = {"input": {"query": "Acme Logística — próximos años"}, "lista": [1, 2, {"a": None}]}
    DbStepRecorder(db_session, report.id).record(StepKind.TOOL_CALL, "buscar_web", payload)
    db_session.expire_all()
    assert saved_steps(db_session, report)[0].payload == payload

def test_el_registrador_nulo_no_hace_nada():
    assert NullRecorder().record(StepKind.FINAL, None, {"text": "x"}) is None

def test_un_informe_inexistente_se_rechaza_por_la_clave_foranea(db_session):
    recorder = DbStepRecorder(db_session, uuid.uuid4())
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        recorder.record(StepKind.FINAL, None, {"text": "x"})

# ------------------------------------------------------------------ de punta a punta
def test_el_agente_deja_sus_pasos_visibles_en_la_api_de_la_fase_2(client, db_session, tmp_path):
    """Une tres fases: la API crea el informe, el agente trabaja, y la API muestra sus pasos."""
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "acme.md").write_text(
        "Contacto: Laura Gómez, Directora de Operaciones.", encoding="utf-8"
    )
    registry = ToolRegistry()
    registry.register(ReadFileTool(notes))

    created = client.post(
        "/api/v1/reports", json={"prospect": {"name": "Laura Gómez", "company": "Acme"}}
    )
    report_id = created.json()["id"]

    llm = FakeLLM(
        [
            tool_response(("t1", "leer_archivo", {"path": "."})),
            tool_response(("t2", "leer_archivo", {"path": "acme.md"})),
            text_response("## Resumen ejecutivo\nLaura es Directora (nota interna: acme.md)."),
        ]
    )
    agent = ProspectAgent(llm, registry, today=lambda: date(2026, 11, 22))
    result = agent.run("tarea", recorder=DbStepRecorder(db_session, uuid.UUID(report_id)))

    steps = client.get(f"/api/v1/reports/{report_id}/steps").json()
    assert [(s["step_number"], s["kind"]) for s in steps] == [
        (1, "tool_call"),
        (2, "tool_result"),
        (3, "tool_call"),
        (4, "tool_result"),
        (5, "final"),
    ]
    assert steps[0]["tool_name"] == "leer_archivo"
    assert steps[0]["payload"]["input"] == {"path": "."}
    assert "acme.md" in steps[1]["payload"]["content"]  # el listado de notas
    assert "Directora de Operaciones" in steps[3]["payload"]["content"]  # la nota leída de verdad
    assert steps[4]["payload"]["text"] == result.markdown