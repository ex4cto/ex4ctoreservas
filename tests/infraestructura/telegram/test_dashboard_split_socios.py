"""Tests for E4 — partner split section in /dashboard_ventas (owner-only)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.aplicacion.socios.split import ResumenSocio, ResumenSplitSocios
from garay.dominio.comun.dinero import Dinero

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resumen_split(
    *,
    por_socio: tuple[ResumenSocio, ...] | None = None,
) -> ResumenSplitSocios:
    if por_socio is None:
        por_socio = (
            ResumenSocio(
                nombre="empresa",
                porcentaje=Decimal("50"),
                acumulado=Dinero(1_000_000),
                pagado=Dinero(800_000),
                pendiente=Dinero(200_000),
            ),
            ResumenSocio(
                nombre="garay",
                porcentaje=Decimal("25"),
                acumulado=Dinero(500_000),
                pagado=Dinero(500_000),
                pendiente=Dinero(0),
            ),
            ResumenSocio(
                nombre="ryan",
                porcentaje=Decimal("25"),
                acumulado=Dinero(500_000),
                pagado=Dinero(300_000),
                pendiente=Dinero(200_000),
            ),
        )
    return ResumenSplitSocios(por_socio=por_socio, total_agencia=Dinero(2_000_000))


def _make_resumen_ventas_service() -> MagicMock:
    from garay.aplicacion.reportes.resumen_ventas import ResumenVentas

    resumen = ResumenVentas(
        mes=9,
        año=2026,
        total_ventas=0,
        total_valor=Dinero(0),
        ganancia_agencia=Dinero(0),
        por_vendedor=(),
    )
    svc = MagicMock()
    svc.ejecutar.return_value = resumen
    return svc


def _make_split_service(resumen: ResumenSplitSocios | None = None) -> MagicMock:
    svc = MagicMock()
    svc.calcular_acumulado.return_value = resumen if resumen is not None else _make_resumen_split()
    return svc


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _fake_settings(*, dashboard_url: str = "http://example.com") -> MagicMock:
    import datetime

    s = MagicMock()
    s.dashboard_url = dashboard_url
    s.propietario_telegram_ids = "999"
    s.dev_telegram_ids = ""
    s.socios_desde = datetime.date(2026, 9, 1)
    return s


@pytest.mark.asyncio
async def test_propietario_ve_seccion_split() -> None:
    """Owner sees the 'Divisiones de socios' section appended to dashboard text."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=999)
    split_service = _make_split_service()
    context = _make_context(
        resumen_ventas_service=_make_resumen_ventas_service(),
        split_socios_service=split_service,
    )

    with (
        patch("garay.infraestructura.telegram.handlers_reportes.es_propietario", return_value=True),
        patch("garay.config.settings.obtener_settings", return_value=_fake_settings()),
    ):
        await cmd_dashboard_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    sent_text = update.effective_message.reply_text.call_args[0][0]
    assert "Divisiones de socios" in sent_text


@pytest.mark.asyncio
async def test_admin_no_propietario_no_ve_split() -> None:
    """Non-owner admin does NOT see the split section."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=456)
    split_service = _make_split_service()
    context = _make_context(
        resumen_ventas_service=_make_resumen_ventas_service(),
        split_socios_service=split_service,
    )

    with (
        patch(
            "garay.infraestructura.telegram.handlers_reportes.es_propietario",
            return_value=False,
        ),
        patch("garay.config.settings.obtener_settings", return_value=_fake_settings()),
    ):
        await cmd_dashboard_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    sent_text = update.effective_message.reply_text.call_args[0][0]
    assert "Divisiones de socios" not in sent_text


@pytest.mark.asyncio
async def test_sin_socios_no_aparece_seccion() -> None:
    """When calcular_acumulado() returns empty por_socio, the section is not shown."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=999)
    empty_resumen = ResumenSplitSocios(por_socio=(), total_agencia=Dinero(0))
    split_service = _make_split_service(resumen=empty_resumen)
    context = _make_context(
        resumen_ventas_service=_make_resumen_ventas_service(),
        split_socios_service=split_service,
    )

    with (
        patch("garay.infraestructura.telegram.handlers_reportes.es_propietario", return_value=True),
        patch("garay.config.settings.obtener_settings", return_value=_fake_settings()),
    ):
        await cmd_dashboard_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    sent_text = update.effective_message.reply_text.call_args[0][0]
    assert "Divisiones de socios" not in sent_text


@pytest.mark.asyncio
async def test_formato_split_montos() -> None:
    """Formatted amounts for each partner appear in the sent text."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=999)
    split_service = _make_split_service()
    context = _make_context(
        resumen_ventas_service=_make_resumen_ventas_service(),
        split_socios_service=split_service,
    )

    with (
        patch("garay.infraestructura.telegram.handlers_reportes.es_propietario", return_value=True),
        patch("garay.config.settings.obtener_settings", return_value=_fake_settings()),
    ):
        await cmd_dashboard_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    sent_text = update.effective_message.reply_text.call_args[0][0]
    # Verify the total agencia amount appears (2.000.000 formatted COP)
    assert "$2.000.000" in sent_text
    # Verify at least one partner's acumulado appears ($1.000.000)
    assert "$1.000.000" in sent_text


def test_formatear_split_socios_estructura() -> None:
    """_formatear_split_socios returns expected header and partner lines."""
    from garay.infraestructura.telegram.handlers_reportes import _formatear_split_socios

    resumen = _make_resumen_split()
    resultado = _formatear_split_socios(resumen)

    assert "Divisiones de socios" in resultado
    assert "Agencia total" in resultado
    # All three partner names should appear
    assert "empresa" in resultado.lower() or "Empresa" in resultado
    assert "garay" in resultado.lower() or "Garay" in resultado
    assert "ryan" in resultado.lower() or "Ryan" in resultado
    # Key money labels
    assert "acum." in resultado
    assert "pagado" in resultado
    assert "pendiente" in resultado


@pytest.mark.asyncio
async def test_calcular_acumulado_filtra_desde_sep_2026() -> None:
    """calcular_acumulado is called with desde=date(2026, 9, 1), not all-time."""
    import datetime

    from garay.infraestructura.telegram.handlers_reportes import cmd_dashboard_ventas

    update = _make_update(user_id=999)
    split_service = _make_split_service()
    context = _make_context(
        resumen_ventas_service=_make_resumen_ventas_service(),
        split_socios_service=split_service,
    )

    with (
        patch("garay.infraestructura.telegram.handlers_reportes.es_propietario", return_value=True),
        patch("garay.config.settings.obtener_settings", return_value=_fake_settings()),
    ):
        await cmd_dashboard_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    split_service.calcular_acumulado.assert_called_once_with(desde=datetime.date(2026, 9, 1))


@pytest.mark.asyncio
async def test_cb_dashboard_filtra_desde_sep_2026() -> None:
    """cb_dashboard_ventas also passes desde=date(2026, 9, 1) to calcular_acumulado."""
    import datetime

    from garay.infraestructura.telegram.handlers_reportes import cb_dashboard_ventas

    query = AsyncMock()
    query.data = "rep_v:2026-9"
    query.message = AsyncMock()
    update = _make_update(user_id=999)
    update.callback_query = query

    split_service = _make_split_service()
    context = _make_context(
        resumen_ventas_service=_make_resumen_ventas_service(),
        split_socios_service=split_service,
    )

    with (
        patch("garay.infraestructura.telegram.handlers_reportes.es_propietario", return_value=True),
        patch("garay.config.settings.obtener_settings", return_value=_fake_settings()),
    ):
        await cb_dashboard_ventas(update, context)

    split_service.calcular_acumulado.assert_called_once_with(desde=datetime.date(2026, 9, 1))
