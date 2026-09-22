"""Tests for the _notificar_edicion helper — Phase 2.9 RED."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    *,
    grupo_id: str | None = "-1001234567890",
    mensaje_grupo_id: int | None = None,
    socios: list[object] | None = None,
    propietario_ids: str = "100,200",
) -> MagicMock:
    """Build a minimal context mock for _notificar_edicion."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    context.bot.delete_message = AsyncMock()

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = socios if socios is not None else []
    context.bot_data = {
        "grupo_id": grupo_id,
        "socios_config_repo": socios_config_repo,
        "venta_repo": MagicMock(),
    }

    settings = MagicMock()
    settings.propietario_telegram_ids = propietario_ids
    with patch(
        "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
        return_value=settings,
    ):
        pass  # settings used inside the helper

    return context


def _make_venta(mensaje_grupo_id: int | None = None) -> MagicMock:
    venta = MagicMock()
    venta.id = uuid.uuid4()
    venta.mensaje_grupo_id = mensaje_grupo_id
    return venta


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNotificarEdicion:
    @pytest.mark.asyncio
    async def test_deletes_old_message_when_mensaje_grupo_id_set(self) -> None:
        """Should call bot.delete_message when venta.mensaje_grupo_id is not None."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
        context.bot_data = {
            "grupo_id": "-100123",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=42)

        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Venta actualizada",
            campo_label="Neto",
            es_financiero=False,
        )

        context.bot.delete_message.assert_awaited_once_with(
            chat_id="-100123", message_id=42
        )

    @pytest.mark.asyncio
    async def test_skips_delete_when_mensaje_grupo_id_none(self) -> None:
        """Should NOT call bot.delete_message when venta.mensaje_grupo_id is None."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
        context.bot_data = {
            "grupo_id": "-100123",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=None)

        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Venta actualizada",
            campo_label="Neto",
            es_financiero=False,
        )

        context.bot.delete_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sends_group_message(self) -> None:
        """Should call bot.send_message with the grupo_id and the message text."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        sent_msg = MagicMock()
        sent_msg.message_id = 777
        context.bot.send_message = AsyncMock(return_value=sent_msg)
        context.bot_data = {
            "grupo_id": "-100999",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=None)

        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Test group message",
            campo_label="Neto",
            es_financiero=False,
        )

        context.bot.send_message.assert_awaited()
        call_kwargs = context.bot.send_message.await_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_persists_new_mensaje_grupo_id_to_venta(self) -> None:
        """After sending, should update venta.mensaje_grupo_id and call venta_repo.guardar."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        venta_repo = MagicMock()
        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        sent_msg = MagicMock()
        sent_msg.message_id = 555
        context.bot.send_message = AsyncMock(return_value=sent_msg)
        context.bot_data = {
            "grupo_id": "-100999",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": venta_repo,
        }

        venta = _make_venta(mensaje_grupo_id=None)

        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Test message",
            campo_label="Neto",
            es_financiero=False,
        )

        assert venta.mensaje_grupo_id == 555
        venta_repo.guardar.assert_called_once_with(venta)

    @pytest.mark.asyncio
    async def test_delete_failure_does_not_raise(self) -> None:
        """delete_message failure must be swallowed — best-effort semantics."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock(side_effect=Exception("Telegram error"))
        sent_msg = MagicMock()
        sent_msg.message_id = 111
        context.bot.send_message = AsyncMock(return_value=sent_msg)
        context.bot_data = {
            "grupo_id": "-100123",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=99)

        # Must not raise even though delete_message failed.
        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Group msg",
            campo_label="Canal",
            es_financiero=False,
        )
        # send_message should still be called despite the delete failure.
        context.bot.send_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_send_message_failure_does_not_raise(self) -> None:
        """send_message failure must be swallowed — best-effort."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.send_message = AsyncMock(side_effect=Exception("Network error"))
        context.bot_data = {
            "grupo_id": "-100123",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=None)

        # Must not raise.
        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Group msg",
            campo_label="Canal",
            es_financiero=False,
        )

    @pytest.mark.asyncio
    async def test_dms_socios_on_financial_edit(self) -> None:
        """For financial edits, should DM socios with configured telegram_ids."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        socio1 = MagicMock()
        socio1.telegram_id = 101
        socio2 = MagicMock()
        socio2.telegram_id = None  # No telegram_id — should be skipped.
        socio3 = MagicMock()
        socio3.telegram_id = 102

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        sent_msg = MagicMock()
        sent_msg.message_id = 1
        context.bot.send_message = AsyncMock(return_value=sent_msg)
        context.bot_data = {
            "grupo_id": "-100123",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[socio1, socio2, socio3])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=None)

        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Group msg",
            campo_label="Neto",
            es_financiero=True,
            dm_socios_text="Tu parte actualizada",
        )

        # send_message called: 1 group + 2 socios (socio2 skipped) + possible admins
        calls = context.bot.send_message.await_args_list
        dm_targets = [c.kwargs.get("chat_id") or c.args[0] for c in calls if c]
        assert 101 in dm_targets
        assert 102 in dm_targets
        assert None not in dm_targets

    @pytest.mark.asyncio
    async def test_no_dm_socios_on_non_financial_edit(self) -> None:
        """For non-financial edits, should NOT DM socios."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        socio1 = MagicMock()
        socio1.telegram_id = 101

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        sent_msg = MagicMock()
        sent_msg.message_id = 1
        context.bot.send_message = AsyncMock(return_value=sent_msg)
        context.bot_data = {
            "grupo_id": "-100123",
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[socio1])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=None)

        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Group msg",
            campo_label="Fecha",
            es_financiero=False,
        )

        # Only the group message should be sent (no socio DM).
        calls = context.bot.send_message.await_args_list
        dm_targets = [c.kwargs.get("chat_id") or (c.args[0] if c.args else None) for c in calls]
        assert 101 not in dm_targets

    @pytest.mark.asyncio
    async def test_grupo_id_none_skips_group_send(self) -> None:
        """If grupo_id is absent in bot_data, group notification is skipped gracefully."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _notificar_edicion,
        )

        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
        context.bot_data = {
            "grupo_id": None,
            "socios_config_repo": MagicMock(listar=MagicMock(return_value=[])),
            "venta_repo": MagicMock(),
        }

        venta = _make_venta(mensaje_grupo_id=None)

        # Must not raise.
        await _notificar_edicion(
            context=context,
            venta=venta,
            mensaje_grupo="Group msg",
            campo_label="Neto",
            es_financiero=False,
        )
