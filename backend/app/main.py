from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.exceptions import ReportNotFoundError
from app.routers import health, reports

async def report_not_found_handler(_request: Request, _exc: ReportNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Informe no encontrado"})

def create_app() -> FastAPI:
    app = FastAPI(title="Prospect Agent", version="0.2.0")
    app.include_router(health.router)
    app.include_router(reports.router, prefix="/api/v1")
    app.add_exception_handler(ReportNotFoundError, report_not_found_handler)
    return app

app = create_app()