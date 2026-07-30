"""Unit tests for freelancer management handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.infraestructura.telegram.handlers_freelancers import (
    EF_CONFIRMAR,
    EF_SELECCIONAR,
    FL_CONFIRMACION,
    FL_NOMBRE,
    FL_TELEGRAM_ID,
    cmd_eliminar_freelancer,
    cmd_listar_freelancers,
    cmd_nuevo_freelancer,
    handle_ef_confirmar,
    handle_ef_seleccionar,
    handle_fl_confirmacion,
    handle_fl_nombre,
    handle_fl_telegram_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _freelancer(nombre: str = "Ana", activo: bool = True, es_admin: bool = True) -> Freelancer:
    return Freelancer(
        id=uuid.uuid4(),
        nombre=nombre,
        activo=activo,
        telegram_user_id=None,
        es_admin=es_admin,
    )


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=123)
    update.effective_message = AsyncMock()
    if text is not None:
        update.effective_message.text = text
    if callback_data is not None:
        query = AsyncMock()
        query.data = callback_data
        query.answer = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None
    return update


def _make_context(
    freelancers: list[Freelancer] | None = None,
    user_data: dict | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data or {}
    repo = MagicMock()
    if freelancers is not None:
        repo.listar_todos.return_value = freelancers
        repo.listar_activos.return_value = [f for f in freelancers if f.activo]
    ctx.bot_data = {"freelancer_repo": repo}
    return ctx


# ---------------------------------------------------------------------------
# /listar_freelancers
# ---------------------------------------------------------------------------


class TestCmdListarFreelancers:
    @pytest.mark.asyncio
    async def test_muestra_freelancers_activos_e_inactivos(self) -> None:
        fa = _freelancer("Activo", activo=True)
        fi = _freelancer("Inactivo", activo=False)
        update = _make_update()
        ctx = _make_context(freelancers=[fa, fi])

        # bypass requiere_admin guard
        await cmd_listar_freelancers.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Activo" in msg
        assert "Inactivo" in msg

    @pytest.mark.asyncio
    async def test_lista_vacia_muestra_mensaje(self) -> None:
        update = _make_update()
        ctx = _make_context(freelancers=[])

        await cmd_listar_freelancers.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "No hay freelancers" in msg


# ---------------------------------------------------------------------------
# /nuevo_freelancer
# ---------------------------------------------------------------------------


class TestCmdNuevoFreelancer:
    @pytest.mark.asyncio
    async def test_entry_pide_nombre(self) -> None:
        update = _make_update()
        ctx = _make_context()

        result = await cmd_nuevo_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == FL_NOMBRE
        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "nombre" in msg.lower()

    @pytest.mark.asyncio
    async def test_nombre_vacio_permanece_en_estado(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_fl_nombre(update, ctx)

        assert result == FL_NOMBRE

    @pytest.mark.asyncio
    async def test_nombre_duplicado_permanece_en_estado(self) -> None:
        update = _make_update(text="Ana")
        ctx = _make_context()
        ctx.bot_data["freelancer_repo"].buscar_por_nombre.return_value = _freelancer("Ana")

        result = await handle_fl_nombre(update, ctx)

        assert result == FL_NOMBRE
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "duplicado" in msg.lower() or "existe" in msg.lower()

    @pytest.mark.asyncio
    async def test_nombre_valido_avanza_a_telegram_id(self) -> None:
        update = _make_update(text="Pedro")
        ctx = _make_context()
        ctx.bot_data["freelancer_repo"].buscar_por_nombre.return_value = None

        result = await handle_fl_nombre(update, ctx)

        assert result == FL_TELEGRAM_ID
        assert ctx.user_data["fl_nombre"] == "Pedro"

    @pytest.mark.asyncio
    async def test_telegram_id_invalido_permanece_en_estado(self) -> None:
        update = _make_update(text="abc")
        ctx = _make_context(user_data={"fl_nombre": "Pedro"})

        result = await handle_fl_telegram_id(update, ctx)

        assert result == FL_TELEGRAM_ID

    @pytest.mark.asyncio
    async def test_telegram_id_duplicado_permanece_en_estado(self) -> None:
        update = _make_update(text="99999")
        ctx = _make_context(user_data={"fl_nombre": "Pedro"})
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value = _freelancer("Pedro")

        result = await handle_fl_telegram_id(update, ctx)

        assert result == FL_TELEGRAM_ID

    @pytest.mark.asyncio
    async def test_telegram_id_valido_avanza_a_confirmacion(self) -> None:
        update = _make_update(text="12345678")
        ctx = _make_context(user_data={"fl_nombre": "Pedro"})
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value = None

        result = await handle_fl_telegram_id(update, ctx)

        assert result == FL_CONFIRMACION
        assert ctx.user_data["fl_telegram_id"] == 12345678

    @pytest.mark.asyncio
    async def test_confirmacion_crear_guarda_y_termina(self) -> None:
        update = _make_update(callback_data="fl_confirmar")
        ctx = _make_context(user_data={"fl_nombre": "Pedro", "fl_telegram_id": 12345678})

        result = await handle_fl_confirmacion(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["freelancer_repo"].guardar.assert_called_once()
        # user_data cleaned up
        assert "fl_nombre" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmacion_cancelar_termina(self) -> None:
        update = _make_update(callback_data="fl_cancelar")
        ctx = _make_context(user_data={"fl_nombre": "Pedro", "fl_telegram_id": 12345678})

        result = await handle_fl_confirmacion(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["freelancer_repo"].guardar.assert_not_called()


# ---------------------------------------------------------------------------
# /eliminar_freelancer
# ---------------------------------------------------------------------------


class TestCmdEliminarFreelancer:
    @pytest.mark.asyncio
    async def test_entry_muestra_lista_activos(self) -> None:
        fa = _freelancer("Ana", activo=True)
        update = _make_update()
        ctx = _make_context(freelancers=[fa])

        result = await cmd_eliminar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EF_SELECCIONAR
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_entry_sin_activos_termina(self) -> None:
        update = _make_update()
        ctx = _make_context(freelancers=[])

        result = await cmd_eliminar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_seleccion_pide_confirmacion(self) -> None:
        f = _freelancer("Ana")
        update = _make_update(callback_data=f"ef_sel:{f.id}")
        ctx = _make_context()
        ctx.bot_data["freelancer_repo"].buscar_por_id.return_value = f

        result = await handle_ef_seleccionar(update, ctx)

        assert result == EF_CONFIRMAR
        assert ctx.user_data["ef_freelancer_nombre"] == "Ana"

    @pytest.mark.asyncio
    async def test_confirmar_desactiva_y_termina(self) -> None:
        f = _freelancer("Ana")
        f_id = str(f.id)
        update = _make_update(callback_data="ef_confirmar")
        ctx = _make_context(
            user_data={"ef_freelancer_id": f_id, "ef_freelancer_nombre": "Ana"}
        )
        ctx.bot_data["freelancer_repo"].buscar_por_id.return_value = f

        result = await handle_ef_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["freelancer_repo"].guardar.assert_called_once()
        # freelancer was deactivated
        saved_freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved_freelancer.activo is False

    @pytest.mark.asyncio
    async def test_cancelar_termina(self) -> None:
        update = _make_update(callback_data="ef_cancelar")
        ctx = _make_context(
            user_data={"ef_freelancer_id": str(uuid.uuid4()), "ef_freelancer_nombre": "Ana"}
        )

        result = await handle_ef_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["freelancer_repo"].guardar.assert_not_called()
