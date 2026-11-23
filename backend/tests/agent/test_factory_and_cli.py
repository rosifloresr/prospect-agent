from datetime import date
from typing import Any, ClassVar
import pytest
from app.agent import AgentConfigError, LLMError, ProspectAgent, build_agent
from app.agent.__main__ import main
from app.agent.fake import FakeLLM, text_response, tool_response
from app.config import Settings
from app.tools import ToolRegistry
from app.tools.base import Tool

API_KEY = "sk-ant-clave-secreta-de-prueba"

def make_settings(**overrides) -> Settings:
    # _env_file=None: el resultado no depende del .env de quien ejecute los tests.
    return Settings(
        _env_file=None, database_url="postgresql+psycopg://x:x@localhost/x", **overrides
    )

# ------------------------------------------------------------------ fábrica
def test_sin_clave_de_anthropic_no_se_puede_armar_el_agente():
    with pytest.raises(AgentConfigError, match="ANTHROPIC_API_KEY"):
        build_agent(make_settings(anthropic_api_key=""))

def test_con_clave_se_arma_el_agente_con_las_herramientas_disponibles():
    agent = build_agent(make_settings(anthropic_api_key=API_KEY, tavily_api_key=""))
    assert isinstance(agent, ProspectAgent)
    assert agent._registry.names() == ["leer_archivo", "leer_pagina"]  # sin Tavily, sin buscar_web

def test_los_limites_del_agente_salen_de_la_configuracion():
    agent = build_agent(make_settings(anthropic_api_key=API_KEY, agent_max_iterations=3))
    assert agent._max_iterations == 3

def test_la_clave_de_anthropic_no_aparece_al_imprimir_la_configuracion():
    settings = make_settings(anthropic_api_key=API_KEY)
    assert API_KEY not in repr(settings)
    assert API_KEY not in str(settings)

def test_valores_por_defecto_de_los_limites():
    settings = make_settings()
    assert settings.agent_max_iterations == 8
    assert settings.agent_max_output_tokens == 4096

# ------------------------------------------------------------------ línea de comandos
class EchoTool(Tool):
    name = "eco"
    description = "Devuelve el texto."
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def execute(self, text: str) -> str:
        return text

def fake_agent(llm: FakeLLM) -> ProspectAgent:
    registry = ToolRegistry()
    registry.register(EchoTool())
    return ProspectAgent(llm, registry, today=lambda: date(2026, 11, 22))

def run_cli(argv: list[str], agent: ProspectAgent | Exception) -> tuple[int, str]:
    output: list[str] = []

    def factory() -> ProspectAgent:
        if isinstance(agent, Exception):
            raise agent
        return agent

    code = main(argv, agent_factory=factory, out=output.append)
    return code, "\n".join(output)

def test_la_linea_de_comandos_muestra_los_pasos_y_el_informe():
    llm = FakeLLM(
        [
            tool_response(("t1", "eco", {"text": "hola"}), input_tokens=100, output_tokens=20),
            text_response("## Resumen ejecutivo\nTodo bien.", input_tokens=150, output_tokens=40),
        ]
    )
    code, output = run_cli(["Laura Gómez", "Acme", "--role", "Directora"], fake_agent(llm))

    assert code == 0
    assert '→ eco {"text": "hola"}' in output
    assert "← ok (4 caracteres)" in output
    assert "## Resumen ejecutivo" in output
    assert "2 llamadas al modelo, 1 herramientas, 250 tokens de entrada y 60 de salida" in output
    assert (
        "Cargo: Directora" in llm.calls[0].messages[0]["content"]
    )  # los argumentos llegan al pedido

def test_la_linea_de_comandos_muestra_los_errores_de_herramienta():
    llm = FakeLLM([tool_response(("t1", "inexistente", {})), text_response("# Informe")])
    _code, output = run_cli(["Laura", "Acme"], fake_agent(llm))
    assert "← ERROR" in output

def test_sin_clave_la_linea_de_comandos_sale_con_error_y_mensaje_claro():
    code, output = run_cli(["Laura", "Acme"], AgentConfigError("Falta ANTHROPIC_API_KEY"))
    assert code == 1
    assert "Falta ANTHROPIC_API_KEY" in output

def test_si_el_modelo_falla_informa_el_consumo_previo():
    llm = FakeLLM([tool_response(("t1", "eco", {"text": "x"})), LLMError("sin conexión")])
    code, output = run_cli(["Laura", "Acme"], fake_agent(llm))
    assert code == 1
    assert "sin conexión" in output
    assert "100 de entrada, 50 de salida" in output

def test_faltan_argumentos_obligatorios():
    with pytest.raises(SystemExit):
        main(["solo-el-nombre"], out=lambda _msg: None)