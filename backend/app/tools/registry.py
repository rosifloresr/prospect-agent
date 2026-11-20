import logging
from dataclasses import dataclass
from typing import Any
from app.tools.base import Tool, ToolError

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ToolResult:
    """Resultado de ejecutar una herramienta. is_error se le informa a Claude en la Fase 4."""

    content: str
    is_error: bool = False

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Ya existe una herramienta llamada '{tool.name}'.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_api_schema() for tool in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Ejecuta una herramienta. Nunca levanta excepciones: siempre devuelve un resultado.

        Si una herramienta fallara con una excepción, se cortaría todo el ciclo del agente.
        Devolver el error como texto le permite al modelo leerlo y cambiar de estrategia.
        """
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(self.names()) or "ninguna"
            return ToolResult(
                f"Error: la herramienta '{name}' no existe. Herramientas disponibles: {available}.",
                is_error=True,
            )
        if not isinstance(args, dict):
            return ToolResult("Error: los argumentos deben ser un objeto JSON.", is_error=True)
        try:
            tool.validate_input(args)
            return ToolResult(tool.execute(**args))
        except ToolError as exc:
            return ToolResult(f"Error: {exc}", is_error=True)
        except Exception:
            # Un bug nuestro. El detalle va al log; el modelo recibe un mensaje genérico, porque
            # un traceback puede contener rutas, claves o datos internos.
            logger.exception("Fallo inesperado en la herramienta '%s'", name)
            return ToolResult(
                "Error interno al ejecutar la herramienta. Probá con otra estrategia.",
                is_error=True,
            )