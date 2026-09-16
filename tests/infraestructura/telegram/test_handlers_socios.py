"""Tests for /liquidar_socio ConversationHandler — E5 (TDD)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

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
                pagado=Dinero(0),
                pendiente=Dinero(500_000),
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


def _make_update(
    user_id: int = 999,
    callback_data: str | None = None,
    text: str | None = None,
) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.message = None
    elif text is not None:
        update.callback_query = None
        update.message = MagicMock()
        update.message.text = text
    else:
        update.callback_query = None
        update.message = None
    return update


def _make_socios_config() -> list[MagicMock]:
    """Return three SocioConfig-like mocks."""
    socios = []
    for nombre in ("empresa", "garay", "ryan"):
        s = MagicMock()
        s.nombre = nombre
        socios.append(s)
    return socios


def _make_context(
    socios: list[MagicMock] | None = None,
    split_resumen: ResumenSplitSocios | None = None,
    user_data: dict | None = None,  # type: ignore[type-arg]
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = socios if socios is not None else _make_socios_config()

    pagos_socio_repo = MagicMock()

    split_service = MagicMock()
    split_service.calcular_acumulado.return_value = (
        split_resumen if split_resumen is not None else _make_resumen_split()
    )

    ctx.bot_data = {
        "socios_config_repo": socios_config_repo,
        "pagos_socio_repo": pagos_socio_repo,
        "split_socios_service": split_service,
    }
    return ctx


def _fake_settings(propietario_ids: str = "999") -> MagicMock:
    s = MagicMock()
    s.propietario_telegram_ids = propietario_ids
    s.dev_telegram_ids = ""
    return s


# ---------------------------------------------------------------------------
# TestLiquidarSocioFlujo
# ---------------------------------------------------------------------------


class TestLiquidarSocioFlujo:
    @pytest.mark.asyncio
    async def test_entry_muestra_botones_socios(self) -> None:
        """'/liquidar_socio' shows buttons with partner names from socios_config_repo."""
        from garay.infraestructura.telegram.handlers_socios import (
            LQ_SELECCION,
            cmd_liquidar_socio,
        )

        update = _make_update(user_id=999)
        ctx = _make_context()

        with patch(
            "garay.config.settings.obtener_settings",
            return_value=_fake_settings(propietario_ids="999"),
        ):
            result = await cmd_liquidar_socio.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == LQ_SELECCION
        assert update.effective_message.reply_text.called
        # Just verify the handler replied with some markup
        assert update.effective_message.reply_text.call_count == 1

    @pytest.mark.asyncio
    async def test_seleccion_socio_guarda_nombre_y_muestra_tipo(self) -> None:
        """Callback 'lq_socio:garay' saves to user_data and shows total/partial buttons."""
        from garay.infraestructura.telegram.handlers_socios import (
            LQ_TIPO,
            handle_lq_seleccion,
        )

        update = _make_update(callback_data="lq_socio:garay")
        ctx = _make_context()

        result = await handle_lq_seleccion(update, ctx)

        assert result == LQ_TIPO
        assert ctx.user_data.get("lq_socio") == "garay"
        assert update.effective_message.reply_text.called

    @pytest.mark.asyncio
    async def test_total_establece_monto_pendiente(self) -> None:
        """Callback 'lq_total' sets lq_monto to the pending amount from split_service."""
        from garay.infraestructura.telegram.handlers_socios import (
            LQ_CONFIRMAR,
            handle_lq_tipo,
        )

        update = _make_update(callback_data="lq_total")
        ctx = _make_context(
            user_data={"lq_socio": "garay"},
        )

        result = await handle_lq_tipo(update, ctx)

        assert result == LQ_CONFIRMAR
        # garay has pendiente=500_000 in the default resumen
        lq_monto: Dinero = ctx.user_data["lq_monto"]
        assert lq_monto == Dinero(500_000)
        assert ctx.user_data.get("lq_tipo") == "total"

    @pytest.mark.asyncio
    async def test_parcial_pide_monto_texto(self) -> None:
        """Callback 'lq_parcial' asks for the amount and returns LQ_MONTO."""
        from garay.infraestructura.telegram.handlers_socios import (
            LQ_MONTO,
            handle_lq_tipo,
        )

        update = _make_update(callback_data="lq_parcial")
        ctx = _make_context(user_data={"lq_socio": "garay"})

        result = await handle_lq_tipo(update, ctx)

        assert result == LQ_MONTO
        assert update.effective_message.reply_text.called

    @pytest.mark.asyncio
    async def test_monto_invalido_repregunta(self) -> None:
        """Invalid amount text stays in LQ_MONTO state."""
        from garay.infraestructura.telegram.handlers_socios import (
            LQ_MONTO,
            handle_lq_monto,
        )

        update = _make_update(text="no_es_un_numero")
        ctx = _make_context(user_data={"lq_socio": "garay"})

        result = await handle_lq_monto(update, ctx)

        assert result == LQ_MONTO
        # pagos_socio_repo.guardar should NOT have been called
        assert not ctx.bot_data["pagos_socio_repo"].guardar.called

    @pytest.mark.asyncio
    async def test_monto_valido_va_a_confirmar(self) -> None:
        """Valid amount text transitions to LQ_CONFIRMAR."""
        from garay.infraestructura.telegram.handlers_socios import (
            LQ_CONFIRMAR,
            handle_lq_monto,
        )

        update = _make_update(text="500000")
        ctx = _make_context(user_data={"lq_socio": "garay"})

        result = await handle_lq_monto(update, ctx)

        assert result == LQ_CONFIRMAR
        assert ctx.user_data.get("lq_tipo") == "parcial"
        assert isinstance(ctx.user_data.get("lq_monto"), Dinero)

    @pytest.mark.asyncio
    async def test_confirmar_guarda_pago_y_termina(self) -> None:
        """Callback 'lq_confirmar' calls pagos_socio_repo.guardar and returns END."""
        from garay.infraestructura.telegram.handlers_socios import handle_lq_confirmar

        update = _make_update(callback_data="lq_confirmar")
        ctx = _make_context(
            user_data={
                "lq_socio": "garay",
                "lq_tipo": "total",
                "lq_monto": Dinero(500_000),
            }
        )

        result = await handle_lq_confirmar(update, ctx)

        assert result == ConversationHandler.END
        assert ctx.bot_data["pagos_socio_repo"].guardar.called
        # user_data should be cleaned up
        assert "lq_socio" not in ctx.user_data
        assert "lq_tipo" not in ctx.user_data
        assert "lq_monto" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_cancelar_termina_sin_guardar(self) -> None:
        """Callback 'lq_cancelar' returns END without calling guardar."""
        from garay.infraestructura.telegram.handlers_socios import handle_lq_cancelar

        update = _make_update(callback_data="lq_cancelar")
        ctx = _make_context(
            user_data={
                "lq_socio": "garay",
                "lq_tipo": "total",
                "lq_monto": Dinero(100_000),
            }
        )

        result = await handle_lq_cancelar(update, ctx)

        assert result == ConversationHandler.END
        assert not ctx.bot_data["pagos_socio_repo"].guardar.called
