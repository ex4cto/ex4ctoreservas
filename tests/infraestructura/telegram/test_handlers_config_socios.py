"""Tests for /config_socios ConversationHandler — E6 (TDD)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.socios.entidades import SocioConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOCIOS_DEFAULT = [
    SocioConfig(nombre="empresa", porcentaje=Decimal("50"), telegram_id=None),
    SocioConfig(nombre="garay", porcentaje=Decimal("25"), telegram_id=123456789),
    SocioConfig(nombre="ryan", porcentaje=Decimal("25"), telegram_id=987654321),
]


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


def _make_context(
    socios: list[SocioConfig] | None = None,
    user_data: dict | None = None,  # type: ignore[type-arg]
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = (
        socios if socios is not None else list(_SOCIOS_DEFAULT)
    )

    ctx.bot_data = {
        "socios_config_repo": socios_config_repo,
    }
    return ctx


def _fake_settings(propietario_ids: str = "999") -> MagicMock:
    s = MagicMock()
    s.propietario_telegram_ids = propietario_ids
    s.dev_telegram_ids = ""
    return s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConfigSociosFlujo:
    @pytest.mark.asyncio
    async def test_entry_muestra_config_actual(self) -> None:
        """/config_socios shows each partner name and percentage."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_MENU,
            cmd_config_socios,
        )

        update = _make_update(user_id=999)
        ctx = _make_context()

        with patch(
            "garay.config.settings.obtener_settings",
            return_value=_fake_settings(propietario_ids="999"),
        ):
            result = await cmd_config_socios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == CS_MENU
        assert update.effective_message.reply_text.call_count == 1
        sent_text: str = update.effective_message.reply_text.call_args[0][0]
        assert "empresa" in sent_text.lower() or "Empresa" in sent_text
        assert "50" in sent_text
        assert "garay" in sent_text.lower() or "Garay" in sent_text
        assert "25" in sent_text

    @pytest.mark.asyncio
    async def test_entry_sin_socios_muestra_advertencia(self) -> None:
        """When listar() returns [], message contains 'No hay socios'."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_MENU,
            cmd_config_socios,
        )

        update = _make_update(user_id=999)
        ctx = _make_context(socios=[])

        with patch(
            "garay.config.settings.obtener_settings",
            return_value=_fake_settings(propietario_ids="999"),
        ):
            result = await cmd_config_socios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == CS_MENU
        sent_text: str = update.effective_message.reply_text.call_args[0][0]
        assert "No hay socios" in sent_text

    @pytest.mark.asyncio
    async def test_editar_porc_pide_input(self) -> None:
        """Callback 'cs_editar_porc' edits the message and returns CS_PORC_INPUT."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_PORC_INPUT,
            handle_cs_editar_porc,
        )

        update = _make_update(callback_data="cs_editar_porc")
        ctx = _make_context()

        result = await handle_cs_editar_porc(update, ctx)

        assert result == CS_PORC_INPUT
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
        edit_text: str = update.callback_query.edit_message_text.call_args[0][0]
        assert "empresa" in edit_text.lower() or "porcentaje" in edit_text.lower()

    @pytest.mark.asyncio
    async def test_porc_invalido_formato(self) -> None:
        """Text 'abc' stays in CS_PORC_INPUT state."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_PORC_INPUT,
            handle_cs_porc_input,
        )

        update = _make_update(text="abc")
        ctx = _make_context()

        result = await handle_cs_porc_input(update, ctx)

        assert result == CS_PORC_INPUT
        ctx.bot_data["socios_config_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_porc_invalido_suma(self) -> None:
        """Text '40,30,20' (sums to 90) stays in CS_PORC_INPUT."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_PORC_INPUT,
            handle_cs_porc_input,
        )

        update = _make_update(text="40,30,20")
        ctx = _make_context()

        result = await handle_cs_porc_input(update, ctx)

        assert result == CS_PORC_INPUT
        ctx.bot_data["socios_config_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_porc_valido_guarda_y_termina(self) -> None:
        """Text '50,25,25' calls guardar 3 times and returns END."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            handle_cs_porc_input,
        )

        update = _make_update(text="50,25,25")
        ctx = _make_context()

        result = await handle_cs_porc_input(update, ctx)

        assert result == ConversationHandler.END
        assert ctx.bot_data["socios_config_repo"].guardar.call_count == 3
        # Confirm success message
        update.effective_message.reply_text.assert_called_once()
        sent_text: str = update.effective_message.reply_text.call_args[0][0]
        assert "✅" in sent_text

    @pytest.mark.asyncio
    async def test_editar_tg_muestra_picker(self) -> None:
        """Callback 'cs_editar_tg' shows partner buttons and returns CS_TG_SELECCION."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_TG_SELECCION,
            handle_cs_editar_tg,
        )

        update = _make_update(callback_data="cs_editar_tg")
        ctx = _make_context()

        result = await handle_cs_editar_tg(update, ctx)

        assert result == CS_TG_SELECCION
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_seleccion_socio_tg_pide_input(self) -> None:
        """Callback 'cs_tg:garay' saves user_data and returns CS_TG_INPUT."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_TG_INPUT,
            handle_cs_tg_seleccion,
        )

        update = _make_update(callback_data="cs_tg:garay")
        ctx = _make_context()

        result = await handle_cs_tg_seleccion(update, ctx)

        assert result == CS_TG_INPUT
        assert ctx.user_data.get("cs_socio_editando") == "garay"
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_tg_invalido_repregunta(self) -> None:
        """Text 'no-es-numero' stays in CS_TG_INPUT."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            CS_TG_INPUT,
            handle_cs_tg_input,
        )

        update = _make_update(text="no-es-numero")
        ctx = _make_context(user_data={"cs_socio_editando": "garay"})

        result = await handle_cs_tg_input(update, ctx)

        assert result == CS_TG_INPUT
        ctx.bot_data["socios_config_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_tg_none_borra_id(self) -> None:
        """Text 'none' saves SocioConfig with telegram_id=None and returns END."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            handle_cs_tg_input,
        )

        # Set up buscar_por_nombre to return a real SocioConfig
        update = _make_update(text="none")
        ctx = _make_context(user_data={"cs_socio_editando": "garay"})
        ctx.bot_data["socios_config_repo"].buscar_por_nombre.return_value = SocioConfig(
            nombre="garay", porcentaje=Decimal("25"), telegram_id=123456789
        )

        result = await handle_cs_tg_input(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["socios_config_repo"].guardar.assert_called_once()
        saved: SocioConfig = ctx.bot_data["socios_config_repo"].guardar.call_args[0][0]
        assert saved.telegram_id is None

    @pytest.mark.asyncio
    async def test_tg_entero_valido_guarda(self) -> None:
        """Text '123456' saves SocioConfig with telegram_id=123456 and returns END."""
        from garay.infraestructura.telegram.handlers_config_socios import (
            handle_cs_tg_input,
        )

        update = _make_update(text="123456")
        ctx = _make_context(user_data={"cs_socio_editando": "ryan"})
        ctx.bot_data["socios_config_repo"].buscar_por_nombre.return_value = SocioConfig(
            nombre="ryan", porcentaje=Decimal("25"), telegram_id=None
        )

        result = await handle_cs_tg_input(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["socios_config_repo"].guardar.assert_called_once()
        saved: SocioConfig = ctx.bot_data["socios_config_repo"].guardar.call_args[0][0]
        assert saved.telegram_id == 123456
