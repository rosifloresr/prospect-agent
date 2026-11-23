# Prospect Agent

Agente de IA que investiga a una persona y a su empresa y arma un informe en
Markdown, con fuentes, para prepararte antes de una reunión.

> **Estado: en construcción.** Fases 0 a 3 completas: diseño, base del proyecto,
> datos y herramientas del agente. Falta el agente en sí (Fase 4), su ejecución en
> segundo plano (Fase 5) y el frontend (Fase 6). Hoy los informes se crean en
> estado `pending` y ahí se quedan.

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

# 3. Crear las tablas (siempre desde backend/)
alembic upgrade head

# 4. Arrancar la API (siempre desde la carpeta backend/)
uvicorn app.main:app --reload
```

Comprobá que funciona: http://127.0.0.1:8000/health debería devolver `{"status":"ok"}`.
La documentación interactiva de la API está en http://127.0.0.1:8000/docs.

## Configuración

Las variables se definen en `backend/.env` (plantilla en `backend/.env.example`).
El archivo `.env` real **no se sube a Git**.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DATABASE_URL` | Sí | Conexión a PostgreSQL |
| `ANTHROPIC_MODEL` | No | Modelo de Claude que se registrará en cada informe |
| `TAVILY_API_KEY` | No | Clave para `buscar_web`. Sin ella, esa herramienta no se ofrece |
| `NOTES_DIR` | No | Carpeta de notas internas (por defecto `data/notes`) |
| `APP_ENV` | No | Entorno de ejecución (por defecto `development`) |
| `ANTHROPIC_API_KEY` | Sí, para ejecutar el agente | Clave de la API de Anthropic |
| `AGENT_MAX_ITERATIONS` | No | Máximo de vueltas del agente (por defecto 8) |

## API

Prefijo `/api/v1`. Un informe se crea en estado `pending`.

| Método y ruta | Descripción | Respuestas |
|---|---|---|
| `POST /api/v1/reports` | Crea un informe | 202, 422 |
| `GET /api/v1/reports` | Lista informes (`limit`, `offset`) | 200 |
| `GET /api/v1/reports/{id}` | Detalle de un informe | 200, 404 |
| `GET /api/v1/reports/{id}/steps` | Pasos del agente, en orden | 200, 404 |
| `DELETE /api/v1/reports/{id}` | Elimina un informe y sus pasos | 204, 404 |
| `GET /health` | Estado de la API y de la base | 200, 503 |

Ejemplo:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/reports \
  -H "Content-Type: application/json" \
  -d '{"prospect": {"name": "Laura Gómez", "company": "Acme Logística"}}'
```

## Herramientas del agente

El agente dispone de tres herramientas, todas de **solo lectura**:

| Herramienta | Qué hace | Requiere |
|---|---|---|
| `buscar_web` | Busca en internet | `TAVILY_API_KEY` |
| `leer_pagina` | Lee el texto de una página pública | nada |
| `leer_archivo` | Lee notas de `backend/data/notes/` | nada |

Medidas de seguridad: `leer_pagina` bloquea direcciones internas (SSRF),
puertos distintos de 80 y 443 y redirecciones peligrosas; `leer_archivo` no puede
salir de la carpeta de notas (path traversal) y solo lee `.md` y `.txt`.

Las notas reales (`backend/data/notes/*`) no se suben a Git: solo el archivo de ejemplo.

## Tests y calidad

```bash
cd backend
pytest                  # 164 tests, sin Docker ni red
pytest tests/tools      # solo las herramientas
ruff check .
alembic check           # verifica que los modelos coincidan con la base
```

## Probar el agente desde la terminal

```bash
cd backend
python -m app.agent "Laura Gómez" "Acme Logística" --role "Directora" --goal "Presentar la demo"
```

Muestra cada paso del agente y el informe final. **Consume crédito de la API de Anthropic**
(centavos por informe). Sin `ANTHROPIC_API_KEY` termina con un error claro.

## Estructura

```
backend/
├── alembic/            # migraciones de la base de datos
├── app/
│   ├── models/         # tablas (SQLAlchemy)
│   ├── schemas/        # contratos de la API (Pydantic)
│   ├── services/       # casos de uso
│   ├── routers/        # endpoints
│   └── tools/          # herramientas del agente
├── data/notes/         # notas internas que puede leer el agente
└── tests/
```

## Diseño

El documento de diseño (arquitectura, base de datos, endpoints) está en
`docs/fase-0-diseno-agente-prospecto.pdf`.