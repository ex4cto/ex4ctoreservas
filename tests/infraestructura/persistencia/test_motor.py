"""Tests del factory del engine SQLAlchemy (motor.py).

El engine debe configurar el pool de conexiones con ``pool_pre_ping`` y
``pool_recycle`` tomados de la configuracion, para reciclar/reconectar conexiones
muertas y evitar "SSL SYSCALL error: EOF detected" con Postgres gestionado.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from garay.infraestructura.persistencia.motor import crear_engine


def test_crear_engine_aplica_pool_pre_ping_y_recycle_desde_settings() -> None:
    settings_stub = SimpleNamespace(
        database_url="sqlite://",
        db_pool_pre_ping=True,
        db_pool_recycle=1800,
    )
    with (
        patch(
            "garay.infraestructura.persistencia.motor.obtener_settings",
            return_value=settings_stub,
        ),
        patch(
            "garay.infraestructura.persistencia.motor.create_engine"
        ) as mock_create,
    ):
        crear_engine()

    mock_create.assert_called_once()
    call = mock_create.call_args
    assert call is not None
    assert call.kwargs["pool_pre_ping"] is True
    assert call.kwargs["pool_recycle"] == 1800
