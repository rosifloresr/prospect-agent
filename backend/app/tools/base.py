from abc import ABC, abstractmethod
from typing import Any, ClassVar

class ToolError(Exception):
    """Fallo esperado de una herramienta (entrada inválida, acceso bloqueado, red caída).

    El mensaje se le muestra al modelo para que pueda corregirse, así que debe ser claro
    y no contener secretos ni detalles internos.
    """

def truncate(text: str, max_chars: int) -> str:
    """Recorta el texto para no gastar tokens de más ni desbordar el contexto del modelo."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[... texto truncado por longitud ...]"

class Tool(ABC):
    """Contrato que cumple toda herramienta. El agente solo conoce esta interfaz."""

    name: str
    description: str
    input_schema: ClassVar[dict[str, Any]]

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Ejecuta la herramienta y devuelve texto. Los fallos esperados levantan ToolError."""

    def to_api_schema(self) -> dict[str, Any]:
        """La descripción que se le envía a Claude para que sepa que la herramienta existe."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def validate_input(self, args: dict[str, Any]) -> None:
        """Valida lo que pidió el modelo. Recordá: es entrada no confiable, igual que un formulario."""
        properties = self.input_schema.get("properties", {})
        for field in self.input_schema.get("required", []):
            if field not in args:
                raise ToolError(f"Falta el argumento obligatorio '{field}'.")
        for field, value in args.items():
            if field not in properties:
                valid = ", ".join(properties) or "ninguno"
                raise ToolError(f"Argumento desconocido '{field}'. Argumentos válidos: {valid}.")
            expected = properties[field].get("type")
            if expected == "string" and not isinstance(value, str):
                raise ToolError(f"El argumento '{field}' debe ser un texto.")
            # bool es subclase de int en Python: True pasaría por un entero si no lo excluimos.
            if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                raise ToolError(f"El argumento '{field}' debe ser un número entero.")