import uuid
from app.models import AgentStep, StepKind

VALID_BODY = {
    "prospect": {"name": "Laura Gómez", "company": "Acme Logística", "role": "Directora"},
    "meeting_goal": "Presentar la solución de seguimiento de flotas",
}

def create(client, name="Laura Gómez"):
    body = {**VALID_BODY, "prospect": {**VALID_BODY["prospect"], "name": name}}
    return client.post("/api/v1/reports", json=body)

# ------------------------------------------------------------------ POST
def test_crear_informe_responde_202_con_id_y_estado_pending(client):
    response = create(client)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    uuid.UUID(data["id"])  # si no es un UUID válido, lanza error

def test_crear_informe_con_nombre_vacio_responde_422(client):
    body = {"prospect": {"name": "   ", "company": "Acme"}}
    assert client.post("/api/v1/reports", json=body).status_code == 422

def test_crear_informe_sin_empresa_responde_422(client):
    body = {"prospect": {"name": "Laura"}}
    assert client.post("/api/v1/reports", json=body).status_code == 422

def test_crear_informe_con_nombre_demasiado_largo_responde_422(client):
    body = {"prospect": {"name": "x" * 121, "company": "Acme"}}
    assert client.post("/api/v1/reports", json=body).status_code == 422

def test_los_espacios_sobrantes_se_eliminan(client):
    body = {"prospect": {"name": "  Laura  ", "company": " Acme "}}
    report_id = client.post("/api/v1/reports", json=body).json()["id"]
    data = client.get(f"/api/v1/reports/{report_id}").json()
    assert data["prospect"]["name"] == "Laura"
    assert data["prospect"]["company"] == "Acme"

# ------------------------------------------------------------------ GET uno
def test_obtener_informe_devuelve_el_detalle_completo(client):
    report_id = create(client).json()["id"]
    response = client.get(f"/api/v1/reports/{report_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == report_id
    assert data["status"] == "pending"
    assert data["prospect"]["company"] == "Acme Logística"
    assert data["meeting_goal"] == VALID_BODY["meeting_goal"]
    assert data["markdown"] is None
    assert data["input_tokens"] == 0

def test_obtener_informe_inexistente_responde_404(client):
    response = client.get(f"/api/v1/reports/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Informe no encontrado"}

def test_obtener_informe_con_id_mal_formado_responde_422(client):
    assert client.get("/api/v1/reports/no-es-un-uuid").status_code == 422

# ------------------------------------------------------------------ GET lista
def test_listar_devuelve_los_mas_recientes_primero(client):
    for name in ("Ana", "Beto", "Carla"):
        create(client, name)
    names = [r["prospect"]["name"] for r in client.get("/api/v1/reports").json()]
    assert names == ["Carla", "Beto", "Ana"]

def test_listar_respeta_limit_y_offset(client):
    for name in ("Ana", "Beto", "Carla"):
        create(client, name)
    first_page = client.get("/api/v1/reports?limit=2").json()
    second_page = client.get("/api/v1/reports?limit=2&offset=2").json()
    assert [r["prospect"]["name"] for r in first_page] == ["Carla", "Beto"]
    assert [r["prospect"]["name"] for r in second_page] == ["Ana"]

def test_listar_no_incluye_el_markdown(client):
    create(client)
    item = client.get("/api/v1/reports").json()[0]
    assert "markdown" not in item

def test_listar_rechaza_limit_fuera_de_rango(client):
    assert client.get("/api/v1/reports?limit=0").status_code == 422
    assert client.get("/api/v1/reports?limit=101").status_code == 422
    assert client.get("/api/v1/reports?offset=-1").status_code == 422

def test_listar_sin_informes_devuelve_lista_vacia(client):
    assert client.get("/api/v1/reports").json() == []

# ------------------------------------------------------------------ pasos
def test_pasos_de_un_informe_nuevo_es_lista_vacia(client):
    report_id = create(client).json()["id"]
    response = client.get(f"/api/v1/reports/{report_id}/steps")
    assert response.status_code == 200
    assert response.json() == []

def test_pasos_se_devuelven_ordenados_por_numero(client, db_session):
    report_id = create(client).json()["id"]
    for number in (3, 1, 2):  # insertados desordenados a propósito
        db_session.add(
            AgentStep(
                report_id=uuid.UUID(report_id),
                step_number=number,
                kind=StepKind.TOOL_CALL.value,
                tool_name="buscar_web",
                payload={"query": f"consulta {number}"},
            )
        )
    db_session.commit()

    steps = client.get(f"/api/v1/reports/{report_id}/steps").json()
    assert [s["step_number"] for s in steps] == [1, 2, 3]
    assert steps[0]["payload"] == {"query": "consulta 1"}

def test_pasos_de_un_informe_inexistente_responde_404(client):
    assert client.get(f"/api/v1/reports/{uuid.uuid4()}/steps").status_code == 404

# ------------------------------------------------------------------ DELETE
def test_eliminar_informe_responde_204_y_luego_404(client):
    report_id = create(client).json()["id"]
    assert client.delete(f"/api/v1/reports/{report_id}").status_code == 204
    assert client.get(f"/api/v1/reports/{report_id}").status_code == 404

def test_eliminar_informe_inexistente_responde_404(client):
    assert client.delete(f"/api/v1/reports/{uuid.uuid4()}").status_code == 404