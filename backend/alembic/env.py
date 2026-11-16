from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine
from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import get_settings
from app.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compara este metadata (nuestros modelos) con la base real para autogenerar migraciones.
target_metadata = Base.metadata

DATABASE_URL = get_settings().database_url

def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base (útil para revisarlo o dárselo a un DBA)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detecta también cambios de tipo de columna
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()