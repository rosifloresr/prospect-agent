from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la app, leída de variables de entorno o del archivo .env."""

    app_env: str = "development"
    database_url: str

    # extra="ignore": si el .env tiene variables que todavía no usamos, no falla.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    # lru_cache: se lee y valida el entorno una sola vez, no en cada uso.
    return Settings()