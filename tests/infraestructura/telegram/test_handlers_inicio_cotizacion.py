"""Tests for cotizacion entry point — keyboard structure and auth gate.

SC-F01: Admin sees Cotizacion button.
SC-F02: Non-admin does NOT see Cotizacion button.
SC-F03: Stale keyboard press from non-admin → ConversationHandler.END, no flow.
SC-F04: Freelancer never sees Cotizacion button (same as SC-F02 via param).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers_inicio_venta import _teclado_inicio


class TestTecladoInicioConCotizacion:
    """SC-F01 / SC-F02: _teclado_inicio mostrar_cotizacion flag."""

    def test_admin_ve_boton_cotizacion(self) -> None:
        """SC-F01: mostrar_cotizacion=True → keyboard has 'inicio_cotizacion' button."""
        markup = _teclado_inicio(mostrar_otra_fecha=True, mostrar_cotizacion=True)
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "inicio_cotizacion" in flat_data

    def test_no_admin_no_ve_boton_cotizacion(self) -> None:
        """SC-F02: mostrar_cotizacion=False → no 'inicio_cotizacion' button."""
        markup = _teclado_inicio(mostrar_otra_fecha=False, mostrar_cotizacion=False)
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "inicio_cotizacion" not in flat_data

    def test_freelancer_no_ve_boton_cotizacion(self) -> None:
        """SC-F04: Freelancer (not admin) → same as SC-F02."""
        markup = _teclado_inicio(mostrar_otra_fecha=False, mostrar_cotizacion=False)
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "inicio_cotizacion" not in flat_data

    def test_default_no_muestra_cotizacion(self) -> None:
        """mostrar_cotizacion defaults to False — backward compat."""
        markup = _teclado_inicio(mostrar_otra_fecha=False)
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "inicio_cotizacion" not in flat_data


class TestHandleInicioCotizacionAuthGate:
    """SC-F03: handle_inicio_cotizacion rejects non-admin silently."""

    @pytest.mark.asyncio
    async def test_no_admin_recibe_end(self) -> None:
        """Non-admin pressing inicio_cotizacion → returns ConversationHandler.END."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_inicio_cotizacion,
        )

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 99999
        update.effective_user.full_name = "Stranger"
        cq = AsyncMock()
        cq.data = "inicio_cotizacion"
        cq.answer = AsyncMock()
        update.callback_query = cq
        update.effective_chat = MagicMock()
        update.effective_message = AsyncMock()

        context = MagicMock()
        context.user_data = {}
        context.bot_data = {
            "freelancer_repo": MagicMock(),
            "servicio_repo": MagicMock(),
        }
        context.bot = AsyncMock()

        with patch(
            "garay.infraestructura.telegram.auth.es_admin_o_propietario",
            new=AsyncMock(return_value=False),
        ):
            result = await handle_inicio_cotizacion(update, context)

        assert result == ConversationHandler.END
