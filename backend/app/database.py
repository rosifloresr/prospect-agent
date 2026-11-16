from collections.abc import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import get_settings

# Nombres explícitos para índices y restricciones. Sin esto, PostgreSQL inventa los nombres
# y Alembic no puede referirse a ellos de forma estable cuando queramos modificarlos.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(constraint_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# pool_pre_ping: antes de reutilizar una conexión del pool comprueba que siga viva,
# así un reinicio de Postgres no deja conexiones muertas dando errores.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    """Clase base de todos los modelos (tablas) que definamos en la Fase 2."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, siempre cerrada al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()