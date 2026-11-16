import uuid
from datetime import UTC, datetime
from sqlalchemy import JSON, BigInteger, Integer
from sqlalchemy.dialects.postgresql import JSONB

# JSONB en PostgreSQL; JSON genérico en SQLite, que usamos en los tests.
JsonPayload = JSON().with_variant(JSONB(), "postgresql")

# BIGINT autoincremental. SQLite solo autoincrementa las claves de tipo INTEGER,
# por eso en los tests usamos esa variante.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")

def utcnow() -> datetime:
    return datetime.now(UTC)

def new_uuid() -> uuid.UUID:
    return uuid.uuid4()