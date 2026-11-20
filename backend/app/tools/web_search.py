from typing import Any, ClassVar
import httpx
from app.tools.base import Tool, ToolError, truncate

TAVILY_URL = "https://api.tavily.com/search"
MAX_RESULTS_LIMIT = 8
SNIPPET_CHARS = 500

class WebSearchTool(Tool):
    name = "buscar_web"
    description = (
        "Busca información actual en internet. Devuelve una lista numerada con título, URL y un "
        "resumen de cada resultado. Usala para encontrar noticias, perfiles profesionales y datos "
        "públicos de una persona o empresa. Para leer una página completa, usá leer_pagina con su URL."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Consulta concreta, por ejemplo: 'Acme Logística noticias 2026'.",
            },
            "max_results": {
                "type": "integer",
                "description": f"Cantidad de resultados, de 1 a {MAX_RESULTS_LIMIT}. Por defecto 5.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))

    def execute(self, query: str, max_results: int = 5) -> str:
        query = query.strip()
        if not query:
            raise ToolError("La consulta está vacía.")
        # El modelo puede pedir cualquier número: se acota para controlar costo y tokens.
        max_results = max(1, min(max_results, MAX_RESULTS_LIMIT))

        try:
            response = self._client.post(
                TAVILY_URL,
                json={"query": query, "max_results": max_results, "search_depth": "basic"},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.TimeoutException as exc:
            raise ToolError("La búsqueda tardó demasiado en responder.") from exc
        except httpx.HTTPError as exc:
            raise ToolError("No se pudo conectar con el servicio de búsqueda.") from exc

        self._raise_for_status(response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise ToolError("El servicio de búsqueda devolvió una respuesta inválida.") from exc
        results = data.get("results", []) if isinstance(data, dict) else []
        if not results:
            return "No se encontraron resultados para esa consulta."
        return "\n\n".join(self._format(i, item) for i, item in enumerate(results, start=1))

    @staticmethod
    def _raise_for_status(status: int) -> None:
        # Los mensajes no incluyen la clave: el modelo los lee y pueden terminar en logs.
        if status in (401, 403):
            raise ToolError("El servicio de búsqueda rechazó la clave de API.")
        if status == 429:
            raise ToolError("Se alcanzó el límite de uso del servicio de búsqueda.")
        if status >= 400:
            raise ToolError(f"El servicio de búsqueda respondió con error HTTP {status}.")

    @staticmethod
    def _format(position: int, item: dict[str, Any]) -> str:
        title = item.get("title") or "(sin título)"
        url = item.get("url") or "(sin URL)"
        content = truncate(str(item.get("content") or "").strip(), SNIPPET_CHARS)
        return f"{position}. {title}\n   URL: {url}\n   {content}"