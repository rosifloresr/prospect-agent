# Prospect Agent

Agente de IA que investiga a una persona y a su empresa y arma un informe en
Markdown, con fuentes, para prepararte antes de una reunión.

> Estado: en construcción. Fase 1 completa (base del proyecto).

## Requisitos

- Python 3.11 o superior
- Docker (para PostgreSQL)

## Puesta en marcha

```bash
# 1. Levantar PostgreSQL (desde la raíz del repo)
docker compose up -d

# 2. Preparar el backend
cd backend
python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

# 3. Arrancar la API (siempre desde la carpeta backend/)
uvicorn app.main:app --reload
```

Comprobá que funciona: http://127.0.0.1:8000/health debería devolver `{"status":"ok"}`.

## Tests y calidad

```bash
cd backend
pytest
ruff check .
```
