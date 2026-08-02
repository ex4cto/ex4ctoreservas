"""FastAPI application factory for the webhook service.

Exposes ``crear_app`` for both production startup and test injection.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from garay.dominio.puertos.repositorios import (
    CorreoNoParseadoRepository,
    EgresoRepository,
    IngresoRepository,
)
from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.infraestructura.webhook.rutas import router

logger = logging.getLogger(__name__)


def crear_app(
    *,
    ingreso_repo: IngresoRepository | None = None,
    egreso_repo: EgresoRepository | None = None,
    correo_repo: CorreoNoParseadoRepository | None = None,
    notificador: NotificadorGrupo | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    ingreso_repo: Optional IngresoRepository to override for tests.
    egreso_repo: Optional EgresoRepository to override for tests.
    correo_repo: Optional CorreoNoParseadoRepository to override for tests.
    notificador: Optional NotificadorGrupo to override for tests.
    """
    app = FastAPI(title="Garay Tours — Webhook")

    if ingreso_repo is not None:
        app.dependency_overrides[IngresoRepository] = lambda: ingreso_repo

    if egreso_repo is not None:
        app.dependency_overrides[EgresoRepository] = lambda: egreso_repo

    if correo_repo is not None:
        app.dependency_overrides[CorreoNoParseadoRepository] = lambda: correo_repo

    if notificador is not None:
        app.dependency_overrides[NotificadorGrupo] = lambda: notificador

    app.include_router(router)
    return app
