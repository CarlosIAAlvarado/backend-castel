from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    mongodb_uri: str
    database_name: str
    timezone: str = "America/Bogota"

    api_title: str = "Casterly Rock Simulation API"
    api_version: str = "1.0.0"
    api_description: str = "Sistema de selección, asignación y rotación de agentes"

    debug: bool = False

    cors_origins: str = "*"

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True


settings = Settings()
