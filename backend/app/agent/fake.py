import copy
from dataclasses import dataclass
from typing import Any
from app.agent.llm import LLMResponse, ToolCall

@dataclass(frozen=True)
class RecordedCall:
    """Lo que el agente le envió al modelo en una vuelta."""

    system: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]

class FakeLLM:
    """Un modelo guionado: responde en orden lo que le cargues, sin red ni costo.

    Sirve para probar el ciclo del agente de forma determinista, y registra cada llamada
    para que los tests puedan comprobar exactamente qué se le envió.
    """

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[RecordedCall] = []

    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        # deepcopy: el agente sigue agregando mensajes a su lista; sin copia, lo registrado
        # cambiaría después y los tests verían un historial que no existía en esa vuelta.
        self.calls.append(RecordedCall(system, copy.deepcopy(messages), copy.deepcopy(tools)))
        if not self._responses:
            raise AssertionError("FakeLLM: el agente pidió más respuestas de las cargadas.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

def text_response(
    text: str,
    *,
    input_tokens: int = 100,
    output_tokens: int = 50,
    stop_reason: str = "end_turn",
) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        stop_reason=stop_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_content=[{"type": "text", "text": text}],
    )

def tool_response(
    *calls: tuple[str, str, dict[str, Any]],
    text: str = "",
    input_tokens: int = 100,
    output_tokens: int = 50,
    stop_reason: str = "tool_use",
) -> LLMResponse:
    """Una respuesta que pide una o varias herramientas: cada una es (id, nombre, argumentos)."""
    raw: list[Any] = [{"type": "text", "text": text}] if text else []
    raw += [
        {"type": "tool_use", "id": call_id, "name": name, "input": args}
        for call_id, name, args in calls
    ]
    return LLMResponse(
        text=text,
        tool_calls=[ToolCall(call_id, name, args) for call_id, name, args in calls],
        stop_reason=stop_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_content=raw,
    )