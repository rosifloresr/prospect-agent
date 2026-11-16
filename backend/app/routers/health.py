from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["salud"])

@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # 503 y no 500: el servicio está vivo pero una dependencia (la base) no responde.
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from exc
    return {"status": "ok"}