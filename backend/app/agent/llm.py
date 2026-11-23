from dataclasses import dataclass
from typing import Any, Protocol
import anthropic
from app.agent.errors import LLMError
from app.tools.base import truncate

@dataclass(frozen=True)
class ToolCall:
    """Una herramienta que el modelo pidió usar."""

    id: str
    name: str
    input: dict[str, Any]

@dataclass(frozen=True)
class LLMResponse:
    """La respuesta del modelo, en un formato propio e independiente del proveedor."""

    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    # Los bloques originales de la respuesta. El agente no los interpreta: solo los reenvía
    # tal cual en el historial, que es lo que exige la API.
    raw_content: list[Any]

class LLMClient(Protocol):
    """Lo único que el agente necesita saber de un modelo de lenguaje."""

    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse: ...


class AnthropicClient:
    """Adaptador de la API de Anthropic al contrato LLMClient."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        sdk_client: Any | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        # El SDK ya reintenta solo (2 veces por defecto) ante errores de red, 429 y 5xx.
        self._client = sdk_client or anthropic.Anthropic(api_key=api_key, timeout=120.0)

    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:  # la API no acepta una lista de herramientas vacía
            kwargs["tools"] = tools
        try:
            response = self._client.messages.create(**kwargs)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise LLMError(
                "La clave de la API de Anthropic es inválida o no tiene permisos."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Se alcanzó el límite de uso de la API de Anthropic.") from exc
        except anthropic.APITimeoutError as exc:  # va antes: es subclase de APIConnectionError
            raise LLMError("La API de Anthropic tardó demasiado en responder.") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("No se pudo conectar con la API de Anthropic.") from exc
        except anthropic.BadRequestError as exc:
            # Incluye casos como "saldo de crédito insuficiente": el mensaje de la API ayuda.
            raise LLMError(
                f"La API de Anthropic rechazó el pedido: {truncate(exc.message, 300)}"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"La API de Anthropic respondió con error HTTP {exc.status_code}."
            ) from exc

        return LLMResponse(
            text="".join(block.text for block in response.content if block.type == "text"),
            tool_calls=[
                ToolCall(id=block.id, name=block.name, input=dict(block.input))
                for block in response.content
                if block.type == "tool_use"
            ],
            stop_reason=response.stop_reason or "",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw_content=list(response.content),
        )