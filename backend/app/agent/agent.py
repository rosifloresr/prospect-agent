from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from app.agent.errors import AgentError, MaxIterationsExceeded
from app.agent.llm import LLMClient, LLMResponse
from app.agent.prompts import build_system_prompt, wrap_tool_output
from app.agent.recorder import NullRecorder, StepRecorder
from app.models import StepKind
from app.tools import ToolRegistry

# Motivos por los que el modelo se detuvo y NO hay informe utilizable.
_STOP_ERRORS = {
    "max_tokens": "El informe se cortó por alcanzar el límite de tokens de salida.",
    "refusal": "El modelo rechazó la solicitud.",
    "model_context_window_exceeded": "Se superó la ventana de contexto del modelo.",
    "pause_turn": "El modelo pausó su turno, algo que este agente no sabe continuar.",
}

@dataclass(frozen=True)
class AgentResult:
    markdown: str
    input_tokens: int
    output_tokens: int
    llm_calls: int
    tool_calls: int

class _Usage:
    """Acumula el consumo para poder informarlo incluso si el agente falla."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.llm_calls = 0
        self.tool_calls = 0

class ProspectAgent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        max_iterations: int = 8,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations
        self._today = today

    def run(self, task: str, recorder: StepRecorder | None = None) -> AgentResult:
        usage = _Usage()
        try:
            return self._loop(task, recorder or NullRecorder(), usage)
        except AgentError as exc:
            # El dinero ya se gastó aunque el informe no haya salido: se informa igual.
            exc.input_tokens = usage.input_tokens
            exc.output_tokens = usage.output_tokens
            raise

    def _loop(self, task: str, recorder: StepRecorder, usage: _Usage) -> AgentResult:
        system = build_system_prompt(self._today(), self._registry.names())
        tools = self._registry.schemas()
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]

        for _turn in range(self._max_iterations):
            response = self._llm.create_message(system=system, messages=messages, tools=tools)
            usage.llm_calls += 1
            usage.input_tokens += response.input_tokens
            usage.output_tokens += response.output_tokens

            if response.stop_reason in _STOP_ERRORS:
                raise AgentError(_STOP_ERRORS[response.stop_reason])

            # Se guarda lo que respondió el modelo, para que en la próxima vuelta vea su propio
            # pedido de herramienta junto con el resultado.
            messages.append({"role": "assistant", "content": response.raw_content})

            if not response.tool_calls:
                return self._finish(response, recorder, usage)

            messages.append({"role": "user", "content": self._run_tools(response, recorder, usage)})

        raise MaxIterationsExceeded(
            f"El agente usó sus {self._max_iterations} vueltas sin terminar el informe."
        )

    def _run_tools(
        self, response: LLMResponse, recorder: StepRecorder, usage: _Usage
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for call in response.tool_calls:
            recorder.record(
                StepKind.TOOL_CALL, call.name, {"tool_use_id": call.id, "input": call.input}
            )
            outcome = self._registry.execute(call.name, call.input)
            usage.tool_calls += 1
            recorder.record(
                StepKind.TOOL_RESULT,
                call.name,
                {"tool_use_id": call.id, "is_error": outcome.is_error, "content": outcome.content},
            )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": wrap_tool_output(call.name, outcome.content),
                    "is_error": outcome.is_error,
                }
            )
        # Todos los resultados de una misma vuelta viajan juntos, en un solo mensaje.
        return results

    @staticmethod
    def _finish(response: LLMResponse, recorder: StepRecorder, usage: _Usage) -> AgentResult:
        if response.stop_reason != "end_turn":
            raise AgentError(
                f"El modelo terminó de forma inesperada ({response.stop_reason or 'sin motivo'})."
            )
        markdown = response.text.strip()
        if not markdown:
            raise AgentError("El modelo terminó sin redactar el informe.")
        recorder.record(StepKind.FINAL, None, {"text": markdown})
        return AgentResult(
            markdown=markdown,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            llm_calls=usage.llm_calls,
            tool_calls=usage.tool_calls,
        )