"""Tests for _job_monitor_infraestructura callback and _post_init wiring guard.

Covers AC-10 through AC-13 (callback) and AC-15 (_post_init job registration guard).
All callback tests are async (pytest-asyncio auto mode).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any
from unittest.mock import MagicMock

from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura
from garay.infraestructura.telegram.bot import (
    _job_monitor_infraestructura,
    _post_init,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FECHA_RENOVACION = datetime.date(2027, 3, 15)
_BANDAS = (60, 30, 7, 1)

# A service that is exactly at band 30 when "today" is 2027-02-13
_SERVICIO = ServicioInfraestructura(
    nombre="Dominio garaytours.com",
    fecha_renovacion=_FECHA_RENOVACION,
    bandas_aviso=_BANDAS,
)

_HOY_BAND_30 = datetime.date(2027, 2, 13)  # 30 days before 2027-03-15


class _FakeNotificador:
    """Captures (mensaje, grupo_id) calls; can be configured to raise on demand."""

    def __init__(self, raise_for: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._raise_for: set[str] = raise_for or set()

    def notificar(self, mensaje: str, grupo_id: str) -> None:
        self.calls.append((mensaje, grupo_id))
        if grupo_id in self._raise_for:
            raise RuntimeError(f"Fake notifier failure for {grupo_id}")


def _make_context(
    *,
    servicio: Any | None = "default",
    notificador: Any = "default",
    propietario_ids: str = "111,222",
) -> tuple[MagicMock, Any]:
    """Build a fake PTB CallbackContext with bot_data pre-populated."""
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    ctx = MagicMock()

    fake_notificador = _FakeNotificador() if notificador == "default" else notificador
    monitor_service = (
        MonitorServiciosInfraestructuraService(servicios=[_SERVICIO])
        if servicio == "default"
        else servicio
    )

    bot_data: dict[str, Any] = {}
    if monitor_service is not None:
        bot_data["monitor_infra_service"] = monitor_service
    if fake_notificador is not None:
        bot_data["notificador"] = fake_notificador

    bot_data["propietario_telegram_ids"] = propietario_ids
    ctx.bot_data = bot_data

    return ctx, fake_notificador


# ---------------------------------------------------------------------------
# AC-10: callback delivers to each owner id
# ---------------------------------------------------------------------------


async def test_callback_entrega_a_cada_propietario(monkeypatch: Any) -> None:
    """AC-10: callback calls notificador once per owner id with the alert message."""
    import garay.infraestructura.telegram.bot as bot_module

    ctx, fake_notif = _make_context(propietario_ids="111,222")

    # Freeze "today" to _HOY_BAND_30 so the service returns band 30
    monkeypatch.setattr(
        bot_module,
        "_obtener_hoy_bogota",
        lambda: _HOY_BAND_30,
    )

    await _job_monitor_infraestructura(ctx)

    sent_ids = {grupo_id for _, grupo_id in fake_notif.calls}
    assert sent_ids == {"111", "222"}
    # Both messages should contain the band number (30) and the renewal date
    for mensaje, _ in fake_notif.calls:
        assert "30" in mensaje
        assert "2027-03-15" in mensaje


# ---------------------------------------------------------------------------
# AC-11: empty recipient list — no send, no crash
# ---------------------------------------------------------------------------


async def test_callback_sin_destinatarios_no_envia_ni_crashea(monkeypatch: Any) -> None:
    """AC-11: empty propietario_telegram_ids means nothing is sent."""
    import garay.infraestructura.telegram.bot as bot_module

    ctx, fake_notif = _make_context(propietario_ids="")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY_BAND_30)

    await _job_monitor_infraestructura(ctx)

    assert fake_notif.calls == []


# ---------------------------------------------------------------------------
# AC-12: per-recipient exception is caught; others still notified
# ---------------------------------------------------------------------------


async def test_callback_excepcion_por_destinatario_continua(
    monkeypatch: Any, caplog: Any
) -> None:
    """AC-12: a notifier exception for one recipient is caught, logged; others proceed."""
    import garay.infraestructura.telegram.bot as bot_module

    # Notifier raises when called with "111"
    raising_notif = _FakeNotificador(raise_for={"111"})
    ctx, _ = _make_context(notificador=raising_notif, propietario_ids="111,222")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY_BAND_30)

    # Must not raise even though "111" fails
    with caplog.at_level(logging.ERROR, logger="garay.infraestructura.telegram.bot"):
        await _job_monitor_infraestructura(ctx)

    # "222" must still have been attempted
    attempted_ids = {grupo_id for _, grupo_id in raising_notif.calls}
    assert "222" in attempted_ids

    # The failure for "111" must have been logged (spec: "caught and logged")
    assert any(
        r.levelno == logging.ERROR and "111" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# AC-13: missing bot_data keys — log error and return
# ---------------------------------------------------------------------------


async def test_callback_bot_data_incompleto_log_y_retorna(
    monkeypatch: Any, caplog: Any
) -> None:
    """AC-13: missing monitor_infra_service logs error and returns without raising."""
    import garay.infraestructura.telegram.bot as bot_module

    ctx, _ = _make_context(servicio=None)

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY_BAND_30)

    with caplog.at_level(logging.ERROR, logger="garay.infraestructura.telegram.bot"):
        await _job_monitor_infraestructura(ctx)

    assert any("monitor" in r.getMessage().lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# AC-15: _post_init wiring guard — job registration
# ---------------------------------------------------------------------------


def _make_app_with_job_queue(propietario_ids: str = "111") -> tuple[MagicMock, MagicMock]:
    """Build a fake PTB Application with a spy job_queue."""
    app = MagicMock()

    async def _fake_set_commands(_commands: Any, scope: Any = None) -> bool:
        return True

    app.bot.set_my_commands = _fake_set_commands

    repo = MagicMock()
    repo.listar_activos.return_value = []
    app.bot_data = {"freelancer_repo": repo, "propietario_telegram_ids": propietario_ids}

    job_queue = MagicMock()
    app.job_queue = job_queue

    return app, job_queue


async def test_post_init_registra_job_cuando_hay_servicios(monkeypatch: Any) -> None:
    """AC-15a: job 'monitor_servicios_infra' is registered when services list is non-empty."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(bot_module, "obtener_settings", lambda: settings)

    app, job_queue = _make_app_with_job_queue()
    # Inject a non-empty monitor service into bot_data
    monitor_service = MonitorServiciosInfraestructuraService(servicios=[_SERVICIO])
    app.bot_data["monitor_infra_service"] = monitor_service

    await _post_init(app)

    job_queue.run_daily.assert_called_once()
    call_kwargs = job_queue.run_daily.call_args
    assert call_kwargs.kwargs.get("name") == "monitor_servicios_infra"


async def test_post_init_no_registra_job_cuando_servicios_vacio(monkeypatch: Any) -> None:
    """AC-15b: job is NOT registered when monitor service has empty services list."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(bot_module, "obtener_settings", lambda: settings)

    app, job_queue = _make_app_with_job_queue()
    # Inject an EMPTY monitor service into bot_data
    empty_service = MonitorServiciosInfraestructuraService(servicios=[])
    app.bot_data["monitor_infra_service"] = empty_service

    await _post_init(app)

    job_queue.run_daily.assert_not_called()
