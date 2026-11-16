from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# pool_pre_ping: antes de reutilizar una conexión del pool comprueba que siga viva,
# así un reinicio de Postgres no deja conexiones muertas dando errores.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    """Clase base de todos los modelos (tablas) que definamos en la Fase 2."""


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, siempre cerrada al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()