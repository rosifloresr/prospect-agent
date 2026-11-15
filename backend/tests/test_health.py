from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.database import get_db
from app.main import app

class FakeSessionOk:
    def execute(self, *_args, **_kwargs):
        return None

class FakeSessionDown:
    def execute(self, *_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("conexión rechazada"))

def make_client(fake_session) -> TestClient:
    #Reemplazamos la dependencia real por un doble de prueba: sin Postgres, sin red.
    app.dependency_overrides[get_db] = lambda: fake_session
    return TestClient(app)

def teardown_function():
    app.dependency_overrides.clear()

def test_health_ok_cuando_la_base_responde():
    response = make_client(FakeSessionOk()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_health_503_cuando_la_base_falla():
    response = make_client(FakeSessionDown()).get("/health")
    assert response.status_code == 503