"""Tests for Resend quota monitor integration in the daily job and _post_init guard.

TDD RED phase: tests for wiring that does not yet exist in bot.py.

Covers:
- Quota service present + monthly band due → notifier called per owner
- Quota service present + daily alert → notifier called per owner
- No alerts due → notifier NOT called for quota
- Quota service key absent from bot_data → no crash
- Per-recipient failure for quota alert is caught; others still notified
- _post_init: quota-only config (no domain monitor) → job IS registered
- _post_init: nothing configured → job NOT registered
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


class _FakeMonitorCuotaService:
    """Stub for MonitorCuotaResendService that returns predefined avisos."""

    def __init__(self, avisos: list[Any]) -> None:
        self._avisos = avisos

    def avisos_para(self, hoy: datetime.date) -> list[Any]:
        return list(self._avisos)


def _make_ctx(
    *,
    quota_service: Any = None,
    quota_service_key: bool = True,
    notificador: Any = "default",
    propietario_ids: str = "111,222",
) -> tuple[MagicMock, Any]:
    """Build a fake PTB context with bot_data; domain monitor is absent (quota-only path)."""
    ctx = MagicMock()
    fake_notif = _FakeNotificador() if notificador == "default" else notificador

    # No domain monitor service — tests domain-monitor path is unaffected
    bot_data: dict[str, Any] = {
        "notificador": fake_notif,
        "propietario_telegram_ids": propietario_ids,
    }

    # Domain monitor: inject an always-no-aviso stub so the existing job path doesn't crash
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    bot_data["monitor_infra_service"] = MonitorServiciosInfraestructuraService(servicios=[])

    if quota_service_key:
        bot_data["monitor_cuota_resend_service"] = quota_service

    ctx.bot_data = bot_data
    return ctx, fake_notif


# ---------------------------------------------------------------------------
# Monthly alert delivered to each owner
# ---------------------------------------------------------------------------


async def test_cuota_mensual_entrega_a_cada_propietario(monkeypatch: Any) -> None:
    """Quota monthly aviso → notificador called once per owner with the count in the message."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.cuota_resend import AvisoCuota

    aviso = AvisoCuota(tipo="mensual", umbral=2700, conteo=2700, cap=3000)
    svc = _FakeMonitorCuotaService([aviso])
    ctx, fake_notif = _make_ctx(quota_service=svc, propietario_ids="111,222")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    quota_calls = [
        (m, g) for m, g in fake_notif.calls if "2700" in m or "mensual" in m.lower()
    ]
    sent_ids = {g for _, g in quota_calls}
    assert sent_ids == {"111", "222"}, (
        f"Expected both owner ids to receive quota alert, got: {sent_ids}"
    )


# ---------------------------------------------------------------------------
# Daily alert delivered to each owner
# ---------------------------------------------------------------------------


async def test_cuota_diaria_entrega_a_cada_propietario(monkeypatch: Any) -> None:
    """Quota daily aviso → notificador called once per owner."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.cuota_resend import AvisoCuota

    aviso = AvisoCuota(tipo="diario", umbral=80, conteo=85, cap=100)
    svc = _FakeMonitorCuotaService([aviso])
    ctx, fake_notif = _make_ctx(quota_service=svc, propietario_ids="333")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    quota_calls = [
        (m, g)
        for m, g in fake_notif.calls
        if "85" in m or "diario" in m.lower() or "día" in m.lower()
    ]
    sent_ids = {g for _, g in quota_calls}
    assert "333" in sent_ids


# ---------------------------------------------------------------------------
# No alerts → notificador not called for quota
# ---------------------------------------------------------------------------


async def test_sin_avisos_cuota_no_notifica(monkeypatch: Any) -> None:
    """No quota avisos → notificador is not called for quota."""
    import garay.infraestructura.telegram.bot as bot_module

    svc = _FakeMonitorCuotaService([])
    ctx, fake_notif = _make_ctx(quota_service=svc, propietario_ids="111")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    await _job_monitor_infraestructura(ctx)

    # No quota calls — fake_notif.calls may have domain-monitor calls but NOT quota ones
    # Since domain monitor returns no avisos too (servicios=[]), no calls at all
    assert fake_notif.calls == []


# ---------------------------------------------------------------------------
# Quota service key absent → no crash
# ---------------------------------------------------------------------------


async def test_quota_service_ausente_no_falla(monkeypatch: Any) -> None:
    """Missing monitor_cuota_resend_service key in bot_data → job runs without crashing."""
    import garay.infraestructura.telegram.bot as bot_module

    ctx, fake_notif = _make_ctx(quota_service_key=False, propietario_ids="111")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    # Must not raise
    await _job_monitor_infraestructura(ctx)

    # No quota sends (domain monitor has no services either)
    assert fake_notif.calls == []


# ---------------------------------------------------------------------------
# Per-recipient failure for quota alert is isolated
# ---------------------------------------------------------------------------


async def test_cuota_excepcion_por_destinatario_continua(
    monkeypatch: Any, caplog: Any
) -> None:
    """Notifier raises for one owner; the other still receives the quota alert."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.cuota_resend import AvisoCuota

    aviso = AvisoCuota(tipo="mensual", umbral=2700, conteo=2700, cap=3000)
    svc = _FakeMonitorCuotaService([aviso])
    raising_notif = _FakeNotificador(raise_for={"111"})
    ctx, _ = _make_ctx(quota_service=svc, notificador=raising_notif, propietario_ids="111,222")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    with caplog.at_level(logging.ERROR, logger="garay.infraestructura.telegram.bot"):
        await _job_monitor_infraestructura(ctx)

    attempted_ids = {g for _, g in raising_notif.calls}
    assert "222" in attempted_ids


# ---------------------------------------------------------------------------
# Quota DB failure is caught: no crash, no quota send, logged (W-1)
# ---------------------------------------------------------------------------


async def test_cuota_error_de_db_no_rompe_ni_notifica(
    monkeypatch: Any, caplog: Any
) -> None:
    """W-1: if computing quota alerts (DB) raises, it is logged and no quota alert is
    sent; the callback does not crash and the domain-renewal path is unaffected."""
    import garay.infraestructura.telegram.bot as bot_module

    class _RaisingCuotaService:
        def avisos_para(self, hoy: datetime.date) -> list[Any]:
            raise RuntimeError("DB down")

    ctx, fake_notif = _make_ctx(quota_service=_RaisingCuotaService(), propietario_ids="111")

    monkeypatch.setattr(bot_module, "_obtener_hoy_bogota", lambda: _HOY)

    with caplog.at_level(logging.ERROR, logger="garay.infraestructura.telegram.bot"):
        await _job_monitor_infraestructura(ctx)  # must not raise

    assert fake_notif.calls == []  # no quota sends when the DB call fails
    assert any("quota" in r.getMessage().lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# _post_init: quota-only config → job IS registered
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


async def test_post_init_registra_job_con_solo_cuota(monkeypatch: Any) -> None:
    """AC: quota-only config (no domain renewal services) → daily job IS registered."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(bot_module, "obtener_settings", lambda: settings)

    app, job_queue = _make_app_spy()

    # Domain monitor: EMPTY (no renewal services)
    empty_monitor = MonitorServiciosInfraestructuraService(servicios=[])
    app.bot_data["monitor_infra_service"] = empty_monitor

    # Quota monitor: present (simulating quota-only config)
    from garay.aplicacion.infraestructura_monitor.cuota_resend import (
        MonitorCuotaResendService,
    )

    fake_contador = MagicMock()
    fake_contador.contar_mes_a_la_fecha.return_value = 0
    fake_contador.contar_dia.return_value = 0

    quota_svc = MonitorCuotaResendService(
        contador=fake_contador,
        cap_mensual=3000,
        cap_diario=100,
        bandas_mensual=(0.9, 0.95, 1.0),
        umbral_diario=80,
    )
    app.bot_data["monitor_cuota_resend_service"] = quota_svc

    await _post_init(app)

    job_queue.run_daily.assert_called_once()
    call_kwargs = job_queue.run_daily.call_args
    assert call_kwargs.kwargs.get("name") == "monitor_servicios_infra"


async def test_post_init_no_registra_job_sin_nada_configurado(monkeypatch: Any) -> None:
    """AC: no domain monitor, no quota monitor → daily job NOT registered."""
    import garay.infraestructura.telegram.bot as bot_module
    from garay.aplicacion.infraestructura_monitor.servicio import (
        MonitorServiciosInfraestructuraService,
    )

    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(bot_module, "obtener_settings", lambda: settings)

    app, job_queue = _make_app_spy()

    # Domain monitor: empty
    empty_monitor = MonitorServiciosInfraestructuraService(servicios=[])
    app.bot_data["monitor_infra_service"] = empty_monitor

    # No quota monitor in bot_data

    await _post_init(app)

    job_queue.run_daily.assert_not_called()
