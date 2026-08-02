"""Production entry point for the FastAPI webhook service."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from garay.aplicacion.webhook.app import crear_app
from garay.config.settings import obtener_settings
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.correos_no_parseados import (
    SQLACorreoNoParseadoRepository,
)
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository
from garay.infraestructura.telegram.notificador import NotificadorGrupoTelegram

logging.basicConfig(level=logging.INFO)

_settings = obtener_settings()

if not _settings.telegram_bot_token:
    logging.warning(
        "GARAY_TELEGRAM_BOT_TOKEN is empty — webhook parse-error alerts are disabled"
    )

_engine = crear_engine(_settings.database_url)
_sf = crear_fabrica_sesiones(_engine)

app: FastAPI = crear_app(
    ingreso_repo=SQLAIngresoRepository(_sf),
    egreso_repo=SQLAEgresoRepository(_sf),
    correo_repo=SQLACorreoNoParseadoRepository(_sf),
    notificador=NotificadorGrupoTelegram(_settings.telegram_bot_token),
)
