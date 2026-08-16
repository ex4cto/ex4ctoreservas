"""Configuracion centralizada, cargada desde entorno o archivo .env.

Ningun valor de negocio ni secreto se hardcodea: todo se resuelve aca.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from enum import StrEnum
from functools import lru_cache

from pydantic import AliasChoices, Field
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

    # Developer bypass — full access to all commands regardless of role.
    # GARAY_DEV_TELEGRAM_IDS="123456789,987654321" (comma-separated)
    dev_telegram_ids: str = Field(default="")

    # Streamlit dashboard URL — sent alongside /dashboard_ventas reply.
    dashboard_url: str = Field(default="http://localhost:8501")

    factura_logo_url: str = Field(default="")

    # Resend HTTP API for invoice delivery.
    resend_api_key: str = Field(default="")
    resend_from: str = Field(default="")

    # Feature flag: allow accumulating multiple tours in one reservation.
    # Default False → one tour per reservation (reserva-por-tour, 2026-08-11).
    # Set GARAY_MULTI_TOUR_HABILITADO=true to re-enable the multi-tour accumulator.
    multi_tour_habilitado: bool = False

    # Conciliacion: propietario access and engine parameters.
    # GARAY_PROPIETARIO_TELEGRAM_IDS="123456789,987654321" (comma-separated, empty = deny all)
    propietario_telegram_ids: str = Field(default="")
    conciliacion_tolerancia_pct: Decimal = Field(default=Decimal("0.05"))
    conciliacion_ventana_dias: int = Field(default=3)
    conciliacion_confianza_auto: Decimal = Field(default=Decimal("0.90"))
    conciliacion_peso_monto: Decimal = Field(default=Decimal("0.6"))
    conciliacion_peso_fecha: Decimal = Field(default=Decimal("0.4"))

    # --- Monitor de servicios de infraestructura (Slice 1: dominio por fecha) ---
    # Fecha de renovacion del dominio (formato ISO YYYY-MM-DD). Vacio/None = monitor no-op.
    dominio_renovacion: datetime.date | None = Field(default=None)
    # Bandas de aviso en dias-antes de la renovacion. Default 60/30/7/1.
    dominio_bandas_aviso: tuple[int, ...] = Field(default=(60, 30, 7, 1))

    # --- Monitor de costo Railway (Batch 1) ---
    # API token for the Railway GraphQL API.
    railway_api_token: str = Field(default="")
    # Project ID injected by Railway at deploy time as RAILWAY_PROJECT_ID (no GARAY_ prefix).
    # AliasChoices lets pydantic-settings check the un-prefixed env var first.
    railway_project_id: str = Field(
        default="",
        validation_alias=AliasChoices("RAILWAY_PROJECT_ID"),
    )
    # Alert threshold in USD for actual month-to-date Railway spend.
    railway_umbral_costo: float = Field(default=20.0)
    # Unit prices sourced from the Railway Hobby plan dashboard (USD).
    railway_precio_memoria_gb_min: float = Field(default=0.000231)
    railway_precio_cpu_vcpu_min: float = Field(default=0.000463)
    railway_precio_egress_gb: float = Field(default=0.05)
    railway_precio_volumen_gb_min: float = Field(default=0.000003)
    # Monthly base fee for the Railway Hobby plan (the bill is max(plan_fee, usage)).
    railway_plan_fee: float = Field(default=5.0)

    # --- Monitor de cuota Resend (Slice 2: email quota) ---
    # Monthly email cap for the Resend free tier.
    resend_cap_mensual: int = Field(default=3000)
    # Daily email cap for the Resend free tier.
    resend_cap_diario: int = Field(default=100)
    # Monthly alert bands as fractions of resend_cap_mensual (e.g. 0.80 = 80%).
    resend_bandas_mensual: tuple[float, ...] = Field(default=(0.80, 0.95, 1.0))
    # Daily threshold (absolute count) to trigger a daily-overage alert.
    resend_umbral_diario: int = Field(default=80)


@lru_cache(maxsize=1)
def obtener_settings() -> Settings:
    """Devuelve la configuracion, cacheada para todo el proceso."""
    return Settings()
