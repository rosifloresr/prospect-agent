import os

# Se ejecuta antes de importar la app: los tests no deben depender del .env de cada
# desarrollador. Crear el engine no abre conexión, así que esta URL ficticia alcanza.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.database import Base, get_db
from app.main import app

@pytest.fixture
def db_session():
    """Base de datos SQLite en memoria, nueva y vacía para cada test."""
    # StaticPool + check_same_thread=False: todas las conexiones comparten la misma base en
    # memoria, aunque FastAPI ejecute los endpoints en otro hilo.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        # SQLite ignora las claves foráneas salvo que se lo pidamos. PostgreSQL siempre las aplica.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()