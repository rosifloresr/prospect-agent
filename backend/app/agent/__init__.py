from app.agent.agent import AgentResult, ProspectAgent
from app.agent.errors import AgentConfigError, AgentError, LLMError, MaxIterationsExceeded
from app.agent.llm import AnthropicClient
from app.agent.prompts import build_task
from app.config import Settings, get_settings
from app.tools import build_default_registry

__all__ = [
    "AgentConfigError",
    "AgentError",
    "AgentResult",
    "LLMError",
    "MaxIterationsExceeded",
    "ProspectAgent",
    "build_agent",
    "build_task",
]

def build_agent(settings: Settings | None = None) -> ProspectAgent:
    """Arma el agente real: el modelo de Anthropic más las herramientas disponibles."""
    settings = settings or get_settings()
    api_key = settings.anthropic_api_key.get_secret_value()
    if not api_key:
        raise AgentConfigError("Falta ANTHROPIC_API_KEY: configurala en backend/.env.")
    llm = AnthropicClient(
        api_key=api_key,
        model=settings.anthropic_model,
        max_tokens=settings.agent_max_output_tokens,
    )
    return ProspectAgent(
        llm=llm,
        registry=build_default_registry(settings),
        max_iterations=settings.agent_max_iterations,
    )