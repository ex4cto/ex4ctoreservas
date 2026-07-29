"""Production entry point for the FastAPI webhook service."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from garay.aplicacion.webhook.app import crear_app
from garay.config.settings import obtener_settings
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository

logging.basicConfig(level=logging.INFO)

_settings = obtener_settings()
_engine = crear_engine(_settings.database_url)
_sf = crear_fabrica_sesiones(_engine)

app: FastAPI = crear_app(
    ingreso_repo=SQLAIngresoRepository(_sf),
    egreso_repo=SQLAEgresoRepository(_sf),
)
