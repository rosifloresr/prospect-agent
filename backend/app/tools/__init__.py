import logging
from app.config import Settings, get_settings
from backend.app.tools.read_page import ReadFileTool
from app.tools.read_page import ReadPageTool
from app.tools.registry import ToolRegistry, ToolResult
from app.tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)

__all__ = ["ToolRegistry", "ToolResult", "build_default_registry"]

def build_default_registry(settings: Settings | None = None) -> ToolRegistry:
    """Arma el registro con las herramientas que pueden funcionar con la configuración actual."""
    settings = settings or get_settings()
    registry = ToolRegistry()

    api_key = settings.tavily_api_key.get_secret_value()
    if api_key:
        registry.register(WebSearchTool(api_key))
    else:
        # Mejor no ofrecerle al modelo una herramienta que siempre va a fallar: gastaría
        # vueltas del ciclo (y dinero) intentando usarla.
        logger.warning("TAVILY_API_KEY no está configurada: buscar_web no estará disponible.")

    registry.register(ReadPageTool())
    registry.register(ReadFileTool(settings.notes_dir))
    return registry