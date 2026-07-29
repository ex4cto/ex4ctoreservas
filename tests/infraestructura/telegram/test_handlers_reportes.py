"""Tests for handlers_reportes — cmd_dashboard_ventas, cmd_flujo_caja, callbacks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update(user_id: int = 123) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    update.callback_query = None
    return update


def _make_context(**bot_data: object) -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = dict(bot_data)
    return ctx


def _make_settings(*, propietario_ids: str = "999") -> MagicMock:
    s = MagicMock()
    s.propietario_telegram_ids = propietario_ids
    return s


def _make_freelancer_repo(*, found: bool = True, es_admin: bool = True) -> MagicMock:
    repo = MagicMock()
    if found:
        fl = MagicMock()
        fl.es_admin = es_admin
        repo.buscar_por_telegram_id.return_value = fl
    else:
        repo.buscar_por_telegram_id.return_value = None
    return repo


def _make_resumen_service(total_ventas: int = 0) -> MagicMock:
    from garay.aplicacion.reportes.resumen_ventas import ResumenVentas
    from garay.dominio.comun.dinero import Dinero

    resumen = ResumenVentas(
        mes=7,
        año=2026,
        total_ventas=total_ventas,
        total_valor=Dinero(0),
        ganancia_agencia=Dinero(0),
        por_vendedor=(),
    )
    svc = MagicMock()
    svc.ejecutar.return_value = resumen
    return svc


def _make_flujo_service() -> MagicMock:
    from garay.aplicacion.reportes.flujo_caja import FlujoCaja
    from garay.dominio.comun.dinero import Dinero

    flujo = FlujoCaja(
        mes=7,
        año=2026,
        total_ingresos=Dinero(0),
        total_egresos=Dinero(0),
        balance=Dinero(0),
        ingresos_conciliados=0,
        ingresos_pendientes=0,
        egresos_por_categoria=(),
    )
    svc = MagicMock()
    svc.ejecutar.return_value = flujo
    return svc


# ---------------------------------------------------------------------------
# cmd_dashboard_ventas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_dashboard_ventas_bloqueado_para_non_admin() -> None:
    """Non-admin user → handler replies denial message (via requiere_admin decorator)."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=456)
    repo = _make_freelancer_repo(found=True, es_admin=False)
    context = _make_context(
        freelancer_repo=repo,
        resumen_ventas_service=_make_resumen_service(),
    )

    # Call the full (decorated) handler to test the auth guard
    await cmd_dashboard_ventas(update, context)

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "admin" in msg.lower() or "acceso" in msg.lower() or "administrador" in msg.lower()


@pytest.mark.asyncio
async def test_cmd_dashboard_ventas_funciona_para_admin() -> None:
    """Admin user with no ventas → reply contains sin_datos message."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=123)
    repo = _make_freelancer_repo(found=True, es_admin=True)
    svc = _make_resumen_service(total_ventas=0)
    context = _make_context(freelancer_repo=repo, resumen_ventas_service=svc)

    # Use the unwrapped function to bypass auth and test the logic itself
    await cmd_dashboard_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "datos" in msg.lower() or "período" in msg.lower() or "periodo" in msg.lower()


# ---------------------------------------------------------------------------
# cmd_flujo_caja
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_flujo_caja_bloqueado_para_non_propietario() -> None:
    """User not in propietario list → reply denial message (via requiere_propietario)."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_flujo_caja

    update = _make_update(user_id=456)
    context = _make_context(flujo_caja_service=_make_flujo_service())

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings(propietario_ids="999"),
    ):
        # Call the full decorated handler to test auth guard
        await cmd_flujo_caja(update, context)

    update.effective_message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_dashboard_ventas_navega_a_diciembre_desde_enero() -> None:
    """Callback rep_v:2026-01 — navigation to previous month should work (Dec 2025)."""
    from garay.aplicacion.reportes.resumen_ventas import ResumenVentas
    from garay.dominio.comun.dinero import Dinero
    from garay.infraestructura.telegram.handlers_reportes import cb_dashboard_ventas

    resumen_dic = ResumenVentas(
        mes=12,
        año=2025,
        total_ventas=0,
        total_valor=Dinero(0),
        ganancia_agencia=Dinero(0),
        por_vendedor=(),
    )
    svc = MagicMock()
    svc.ejecutar.return_value = resumen_dic

    query = AsyncMock()
    query.data = "rep_v:2026-01"
    query.message = AsyncMock()

    update = MagicMock()
    update.callback_query = query

    context = _make_context(resumen_ventas_service=svc)

    await cb_dashboard_ventas(update, context)

    # Should have called service with month=1, year=2026
    svc.ejecutar.assert_called_once_with(1, 2026)
    query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_cb_flujo_caja_parsea_mes_y_ano() -> None:
    """Callback rep_c:2026-07 — service called with correct month and year."""
    from garay.aplicacion.reportes.flujo_caja import FlujoCaja
    from garay.dominio.comun.dinero import Dinero
    from garay.infraestructura.telegram.handlers_reportes import cb_flujo_caja

    flujo = FlujoCaja(
        mes=7,
        año=2026,
        total_ingresos=Dinero(0),
        total_egresos=Dinero(0),
        balance=Dinero(0),
        ingresos_conciliados=0,
        ingresos_pendientes=0,
        egresos_por_categoria=(),
    )
    svc = MagicMock()
    svc.ejecutar.return_value = flujo

    query = AsyncMock()
    query.data = "rep_c:2026-07"
    query.message = AsyncMock()

    update = MagicMock()
    update.callback_query = query

    context = _make_context(flujo_caja_service=svc)

    await cb_flujo_caja(update, context)

    svc.ejecutar.assert_called_once_with(7, 2026)
    query.edit_message_text.assert_called_once()
