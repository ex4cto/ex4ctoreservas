"""Tests for Railway cost monitor integration in the daily job and _post_init guard.

TDD RED phase: tests for wiring that does not yet exist in bot.py.

Covers:
- Railway service present + alert due → notifier called per owner
- No alerts due → notifier NOT called for railway
- Railway service key absent from bot_data → no crash (skip silently)
- HTTP/service error → caught + logged + no crash + domain and quota alerts unaffected
- Per-recipient failure for railway alert is isolated; others still notified
- _post_init: railway-only config (no domain, no quota) → job IS registered
"""

from __future__ import annotations

import datetime
import logging
from typing import Any
from unittest.mock import MagicMock

from garay.infraestructura.telegram.bot import (
    _job_monitor_infraestructura,
    _post_init,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOY = datetime.date(2026, 8, 16)


class _FakeNotificador:
    """Captures (mensaje, grupo_id) calls; can be configured to raise on demand."""

    def __init__(self, raise_for: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._raise_for: set[str] = raise_for or set()

    def notificar(self, mensaje: str, grupo_id: str) -> None:
        self.calls.append((mensaje, grupo_id))
        if grupo_id in self._raise_for:
            raise RuntimeError(f"Fake notifier failure for {grupo_id}")


class _FakeMonitorRailwayService:
    """Stub for MonitorCostoRailwayService that returns predefined avisos."""

    def __init__(self, avisos: list[Any]) -> None:
        self._avisos = avisos

    def avisos_para(self, hoy: datetime.date) -> list[Any]:
        return list(self._avisos)


class _RaisingRailwayService:
    """Stub that raises on avisos_para — simulates HTTP failure."""

    def avisos_para(self, hoy: datetime.date) -> list[Any]:
        raise RuntimeError("Railway API down")


def _make_ctx(
    *,
    railway_service: Any = None,
    railway_service_key: bool = True,
    notificador: Any = "default",
    propietario_ids: str = "111,222",
) -> tuple[MagicMock, Any]:
    """Build a fake PTB context with bot_data; domain and quota monitors are minimal stubs."""
    ctx = MagicMock()
    fake_notif = _FakeNotificador() if notificador == "default" else notificador

    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    bot_data: dict[str, Any] = {
        "notificador": fake_notif,
        "propietario_telegram_ids": propietario_ids,
        "monitor_infra_service": MonitorServiciosInfraestructuraService(servicios=[]),
    }

    if railway_service_key:
        bot_data["monitor_costo_railway_service"] = railway_service

    ctx.bot_data = bot_data
    return ctx, fake_notif


# ---------------------------------------------------------------------------
# Railway alert delivered to each owner
# ---------------------------------------------------------------------------


async def test_railway_alerta_entrega_a_cada_propietario(monkeypatch: Any) -> None:
    """Railway aviso → notificador called once per owner with cost in the message."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.costo_railway import AvisoCostoRailway

    aviso = AvisoCostoRailway(costo_actual=15.75, umbral=10.0, estimado_factura=22.50)
    svc = _FakeMonitorRailwayService([aviso])
    ctx, fake_notif = _make_ctx(railway_service=svc, propietario_ids="111,222")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    railway_calls = [
        (m, g) for m, g in fake_notif.calls if "15.75" in m or "Railway" in m
    ]
    sent_ids = {g for _, g in railway_calls}
    assert sent_ids == {"111", "222"}, (
        f"Expected both owner ids to receive railway alert, got: {sent_ids}"
    )


# ---------------------------------------------------------------------------
# No alerts → notificador not called for railway
# ---------------------------------------------------------------------------


async def test_sin_avisos_railway_no_notifica(monkeypatch: Any) -> None:
    """No railway avisos → notificador is not called for railway."""
    import garay.infraestructura.telegram.bot as bot_module

    svc = _FakeMonitorRailwayService([])
    ctx, fake_notif = _make_ctx(railway_service=svc, propietario_ids="111")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    assert fake_notif.calls == []


# ---------------------------------------------------------------------------
# Service key absent → no crash
# ---------------------------------------------------------------------------


async def test_railway_service_ausente_no_falla(monkeypatch: Any) -> None:
    """Missing monitor_costo_railway_service key in bot_data → job runs without crashing."""
    import garay.infraestructura.telegram.bot as bot_module

    ctx, fake_notif = _make_ctx(railway_service_key=False, propietario_ids="111")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    assert fake_notif.calls == []


# ---------------------------------------------------------------------------
# HTTP / service error → caught + logged + no crash
# ---------------------------------------------------------------------------


async def test_railway_error_de_api_no_rompe_ni_notifica(
    monkeypatch: Any, caplog: Any
) -> None:
    """Railway API error is caught, logged, no crash, no railway send."""
    import garay.infraestructura.telegram.bot as bot_module

    ctx, fake_notif = _make_ctx(
        railway_service=_RaisingRailwayService(), propietario_ids="111"
    )

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    with caplog.at_level(logging.ERROR, logger="garay.infraestructura.telegram.bot"):
        await _job_monitor_infraestructura(ctx)  # must not raise

    assert fake_notif.calls == []
    # Must have logged the error
    assert any(
        "railway" in r.getMessage().lower() for r in caplog.records
    ), f"Expected railway error in logs, got: {[r.getMessage() for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Domain and quota unaffected when railway errors
# ---------------------------------------------------------------------------


async def test_railway_error_no_afecta_otras_alertas(monkeypatch: Any) -> None:
    """Railway error must not abort quota or domain alert delivery."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.cuota_resend import AvisoCuota

    # Quota service with a real aviso
    class _FakeQuotaService:
        def avisos_para(self, hoy: datetime.date) -> list[Any]:
            return [AvisoCuota(tipo="mensual", umbral=2700, conteo=2700, cap=3000)]

    ctx, fake_notif = _make_ctx(
        railway_service=_RaisingRailwayService(), propietario_ids="111"
    )
    ctx.bot_data["monitor_cuota_resend_service"] = _FakeQuotaService()

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    # Quota alert must still arrive
    quota_calls = [
        (m, g) for m, g in fake_notif.calls if "2700" in m or "mensual" in m.lower()
    ]
    assert len(quota_calls) == 1, f"Expected 1 quota call, got: {quota_calls}"


# ---------------------------------------------------------------------------
# Per-recipient failure is isolated
# ---------------------------------------------------------------------------


async def test_railway_excepcion_por_destinatario_continua(
    monkeypatch: Any, caplog: Any
) -> None:
    """Notifier raises for one owner; the other still receives the railway alert."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.costo_railway import AvisoCostoRailway

    aviso = AvisoCostoRailway(costo_actual=15.75, umbral=10.0, estimado_factura=22.50)
    svc = _FakeMonitorRailwayService([aviso])
    raising_notif = _FakeNotificador(raise_for={"111"})
    ctx, _ = _make_ctx(
        railway_service=svc, notificador=raising_notif, propietario_ids="111,222"
    )

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    with caplog.at_level(logging.ERROR, logger="garay.infraestructura.telegram.bot"):
        await _job_monitor_infraestructura(ctx)

    attempted_ids = {g for _, g in raising_notif.calls}
    assert "222" in attempted_ids


# ---------------------------------------------------------------------------
# _post_init: railway-only config → job IS registered
# ---------------------------------------------------------------------------


def _make_app_spy(propietario_ids: str = "111") -> tuple[MagicMock, MagicMock]:
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


async def test_post_init_registra_job_con_solo_railway(monkeypatch: Any) -> None:
    """AC: railway-only config (no domain, no quota) → daily job IS registered."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(bot_module, "obtener_settings", lambda: settings)

    app, job_queue = _make_app_spy()

    # Domain monitor: empty (no renewal services)
    empty_monitor = MonitorServiciosInfraestructuraService(servicios=[])
    app.bot_data["monitor_infra_service"] = empty_monitor

    # Railway monitor: present (railway-only config)
    railway_svc = _FakeMonitorRailwayService([])
    app.bot_data["monitor_costo_railway_service"] = railway_svc

    # No quota monitor

    await _post_init(app)

    job_queue.run_daily.assert_called_once()
    call_kwargs = job_queue.run_daily.call_args
    assert call_kwargs.kwargs.get("name") == "monitor_servicios_infra"
