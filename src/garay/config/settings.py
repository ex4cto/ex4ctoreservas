"""Configuracion centralizada, cargada desde entorno o archivo .env.

Ningun valor de negocio ni secreto se hardcodea: todo se resuelve aca.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Entorno(StrEnum):
    """Entorno de ejecucion del sistema."""

    DESARROLLO = "desarrollo"
    PRODUCCION = "produccion"
    PRUEBAS = "pruebas"


class Settings(BaseSettings):
    """Configuracion tipada del sistema. Prefijo de variables: ``GARAY_``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GARAY_",
        extra="ignore",
    )

    entorno: Entorno = Entorno.DESARROLLO

    # Secretos (se completan por entorno, nunca en el codigo).
    database_url: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    webhook_secret: str = Field(default="")
    grupo_id: str = Field(default="")

    # Moneda base del sistema.
    moneda_predeterminada: str = "COP"

    # Ollama AI configuration.
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_modelo: str = Field(default="llava")
    ollama_bin: str = Field(default="ollama")
    ollama_timeout: int = Field(default=300)


@lru_cache(maxsize=1)
def obtener_settings() -> Settings:
    """Devuelve la configuracion, cacheada para todo el proceso."""
    return Settings()
