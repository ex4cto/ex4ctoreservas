"""Configuracion centralizada, cargada desde entorno o archivo .env.

Ningun valor de negocio ni secreto se hardcodea: todo se resuelve aca.
"""

from __future__ import annotations

from decimal import Decimal
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

    # Secret for Forward Email webhook (distinct from Telegram webhook_secret).
    forward_email_secret: str = Field(default="")

    # Moneda base del sistema.
    moneda_predeterminada: str = "COP"

    # Claude AI configuration.
    anthropic_api_key: str = Field(default="")
    claude_modelo: str = Field(default="claude-haiku-4-5-20251001")

    # Conciliacion: propietario access and engine parameters.
    # GARAY_PROPIETARIO_TELEGRAM_IDS="123456789,987654321" (comma-separated, empty = deny all)
    propietario_telegram_ids: str = Field(default="")
    conciliacion_tolerancia_pct: Decimal = Field(default=Decimal("0.05"))
    conciliacion_ventana_dias: int = Field(default=3)
    conciliacion_confianza_auto: Decimal = Field(default=Decimal("0.90"))
    conciliacion_peso_monto: Decimal = Field(default=Decimal("0.6"))
    conciliacion_peso_fecha: Decimal = Field(default=Decimal("0.4"))


@lru_cache(maxsize=1)
def obtener_settings() -> Settings:
    """Devuelve la configuracion, cacheada para todo el proceso."""
    return Settings()
