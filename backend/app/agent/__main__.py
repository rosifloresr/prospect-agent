"""Prueba el agente desde la terminal, sin base de datos ni API.

Uso:
    python -m app.agent "Laura Gómez" "Acme Logística" --role "Directora" --goal "Demo"
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from typing import Any
from app.agent import AgentError, ProspectAgent, build_agent, build_task
from app.models import StepKind

class ConsoleRecorder:
    """Muestra cada paso en pantalla a medida que ocurre."""

    def __init__(self, out: Callable[[str], None]) -> None:
        self._out = out

    def record(self, kind: StepKind, tool_name: str | None, payload: dict[str, Any]) -> None:
        if kind is StepKind.TOOL_CALL:
            args = json.dumps(payload["input"], ensure_ascii=False)
            self._out(f"  → {tool_name} {args}")
        elif kind is StepKind.TOOL_RESULT:
            state = "ERROR" if payload["is_error"] else "ok"
            self._out(f"  ← {state} ({len(payload['content'])} caracteres)")

def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.agent", description=__doc__)
    parser.add_argument("name", help="Nombre del prospecto")
    parser.add_argument("company", help="Empresa del prospecto")
    parser.add_argument("--role", help="Cargo (opcional)")
    parser.add_argument("--goal", help="Objetivo de la reunión (opcional)")
    parser.add_argument("--notes", help="Notas del vendedor (opcional)")
    return parser.parse_args(argv)

def main(
    argv: Sequence[str] | None = None,
    agent_factory: Callable[[], ProspectAgent] = build_agent,
    out: Callable[[str], None] = print,
) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        agent = agent_factory()
        out("Investigando... (cada línea es un paso del agente)")
        result = agent.run(
            build_task(args.name, args.company, args.role, args.goal, args.notes),
            recorder=ConsoleRecorder(out),
        )
    except AgentError as exc:
        out(f"\nError: {exc}")
        out(
            f"(tokens consumidos antes de fallar: {exc.input_tokens} de entrada, {exc.output_tokens} de salida)"
        )
        return 1
    out("\n" + result.markdown)
    out(
        f"\n— {result.llm_calls} llamadas al modelo, {result.tool_calls} herramientas, "
        f"{result.input_tokens} tokens de entrada y {result.output_tokens} de salida."
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())