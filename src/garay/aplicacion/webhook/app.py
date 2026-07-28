"""FastAPI application factory for the webhook service.

Exposes ``crear_app`` for both production startup and test injection.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from garay.dominio.puertos.repositorios import IngresoRepository
from garay.infraestructura.webhook.rutas import router

logger = logging.getLogger(__name__)


def crear_app(repo: IngresoRepository | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        repo: Optional IngresoRepository to override for tests.
              When None, the router uses its own Depends() resolution.

    Returns:
        Configured FastAPI instance with the webhook router mounted.
    """
    app = FastAPI(title="Garay Tours — Webhook")

    if repo is not None:
        from garay.dominio.puertos.repositorios import IngresoRepository as _IngresoRepository

        app.dependency_overrides[_IngresoRepository] = lambda: repo

    app.include_router(router)
    return app
