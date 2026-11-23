from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import SecretStr

class Settings(BaseSettings):
    """Configuración de la app, leída de variables de entorno o del archivo .env."""

    app_env: str = "development"
    database_url: str

    #Modelo de Claude que usará el agente. Se guarda en cada informe para saber con cuál se generó.
    anthropic_model: str = "claude-sonnet-5-5"
    
    # SecretStr: al imprimir la configuración (en un log o un error) la clave se ve como ********.
    # Para usarla hay que pedirla de forma explícita con .get_secret_value().
    tavily_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    # Límites del agente: sin ellos, un modelo confundido podría dar vueltas (y gastar) sin fin.
    agent_max_iterations: int = 8
    agent_max_output_tokens: int = 4096
    
    notes_dir: Path = Path("data/notes")
    
    #extra="ignore": si el .env tiene variables que todavía no usamos, no falla.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    # lru_cache: se lee y valida el entorno una sola vez, no en cada uso.
    return Settings()