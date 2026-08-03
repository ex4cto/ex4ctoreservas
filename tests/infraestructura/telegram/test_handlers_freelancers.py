"""Unit tests for freelancer management handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.infraestructura.telegram.handlers_freelancers import (
    EF_CONFIRMAR,
    EF_SELECCIONAR,
    FL_CEDULA,
    FL_CONFIRMACION,
    FL_DISPLAY_OVERRIDE,
    FL_NOMBRE_COMPLETO,
    FL_NOMBRE_CORTO,
    FL_TELEGRAM_ID,
    cmd_eliminar_freelancer,
    cmd_listar_freelancers,
    cmd_nuevo_freelancer,
    handle_ef_confirmar,
    handle_ef_seleccionar,
    handle_fl_cedula,
    handle_fl_confirmacion,
    handle_fl_display_override,
    handle_fl_nombre_completo,
    handle_fl_nombre_corto,
    handle_fl_skip_tg,
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
    user_data: dict[str, object] | None = None,
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
# /nuevo_freelancer — new A1 flow
# ---------------------------------------------------------------------------


class TestCmdNuevoFreelancer:
    @pytest.mark.asyncio
    async def test_entry_pide_nombre_completo(self) -> None:
        update = _make_update()
        ctx = _make_context()

        result = await cmd_nuevo_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == FL_NOMBRE_COMPLETO
        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "nombre" in msg.lower()


class TestHandleFlNombreCompleto:
    @pytest.mark.asyncio
    async def test_vacio_permanece_en_estado(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_fl_nombre_completo(update, ctx)

        assert result == FL_NOMBRE_COMPLETO

    @pytest.mark.asyncio
    async def test_valido_almacena_y_avanza_a_cedula(self) -> None:
        update = _make_update(text="Bryan Castro Gomez")
        ctx = _make_context()

        result = await handle_fl_nombre_completo(update, ctx)

        assert result == FL_CEDULA
        assert ctx.user_data["fl_nombre_completo"] == "Bryan Castro Gomez"
        # default short name = first token
        assert ctx.user_data["fl_nombre"] == "Bryan"

    @pytest.mark.asyncio
    async def test_nombre_completo_un_token_prefill_es_el_mismo(self) -> None:
        update = _make_update(text="Madonna")
        ctx = _make_context()

        result = await handle_fl_nombre_completo(update, ctx)

        assert result == FL_CEDULA
        assert ctx.user_data["fl_nombre"] == "Madonna"


class TestHandleFlCedula:
    @pytest.mark.asyncio
    async def test_cedula_invalida_permanece_en_estado(self) -> None:
        update = _make_update(text="123")
        ctx = _make_context(user_data={"fl_nombre_completo": "Bryan C", "fl_nombre": "Bryan"})

        result = await handle_fl_cedula(update, ctx)

        assert result == FL_CEDULA

    @pytest.mark.asyncio
    async def test_cedula_duplicada_permanece_en_estado(self) -> None:
        update = _make_update(text="12345678")
        ctx = _make_context(user_data={"fl_nombre_completo": "Bryan C", "fl_nombre": "Bryan"})
        ctx.bot_data["freelancer_repo"].buscar_por_cedula.return_value = _freelancer("Otro")

        result = await handle_fl_cedula(update, ctx)

        assert result == FL_CEDULA

    @pytest.mark.asyncio
    async def test_cedula_valida_almacena_y_avanza_a_nombre_corto(self) -> None:
        update = _make_update(text="12345678")
        ctx = _make_context(user_data={"fl_nombre_completo": "Bryan Castro", "fl_nombre": "Bryan"})
        ctx.bot_data["freelancer_repo"].buscar_por_cedula.return_value = None

        result = await handle_fl_cedula(update, ctx)

        assert result == FL_NOMBRE_CORTO
        assert ctx.user_data["fl_cedula"] == "12345678"


class TestHandleFlNombreCorto:
    @pytest.mark.asyncio
    async def test_texto_vacio_usa_prefill(self) -> None:
        update = _make_update(text="")
        ctx = _make_context(
            user_data={
                "fl_nombre_completo": "Bryan Castro",
                "fl_nombre": "Bryan",
                "fl_cedula": "12345678",
            }
        )

        result = await handle_fl_nombre_corto(update, ctx)

        # empty text → keep prefill → advance (FL_DISPLAY_OVERRIDE)
        assert result == FL_DISPLAY_OVERRIDE
        assert ctx.user_data["fl_nombre"] == "Bryan"

    @pytest.mark.asyncio
    async def test_texto_provisto_sobreescribe_prefill(self) -> None:
        update = _make_update(text="Bry")
        ctx = _make_context(
            user_data={
                "fl_nombre_completo": "Bryan Castro",
                "fl_nombre": "Bryan",
                "fl_cedula": "12345678",
            }
        )

        result = await handle_fl_nombre_corto(update, ctx)

        assert result == FL_DISPLAY_OVERRIDE
        assert ctx.user_data["fl_nombre"] == "Bry"


class TestHandleFlDisplayOverride:
    @pytest.mark.asyncio
    async def test_vacio_usa_display_auto(self) -> None:
        update = _make_update(text="")
        ctx = _make_context(
            user_data={
                "fl_nombre_completo": "Bryan Castro",
                "fl_nombre": "Bryan",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
            }
        )

        result = await handle_fl_display_override(update, ctx)

        assert result == FL_TELEGRAM_ID
        assert ctx.user_data["fl_display"] == "Bryan C."

    @pytest.mark.asyncio
    async def test_texto_provisto_sobreescribe_display(self) -> None:
        update = _make_update(text="B. Castro")
        ctx = _make_context(
            user_data={
                "fl_nombre_completo": "Bryan Castro",
                "fl_nombre": "Bryan",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
            }
        )

        result = await handle_fl_display_override(update, ctx)

        assert result == FL_TELEGRAM_ID
        assert ctx.user_data["fl_display"] == "B. Castro"


class TestHandleFlTelegramId:
    @pytest.mark.asyncio
    async def test_invalido_permanece_en_estado(self) -> None:
        update = _make_update(text="abc")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
            }
        )

        result = await handle_fl_telegram_id(update, ctx)

        assert result == FL_TELEGRAM_ID

    @pytest.mark.asyncio
    async def test_duplicado_permanece_en_estado(self) -> None:
        update = _make_update(text="99999")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
            }
        )
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value = _freelancer("Otro")

        result = await handle_fl_telegram_id(update, ctx)

        assert result == FL_TELEGRAM_ID

    @pytest.mark.asyncio
    async def test_valido_avanza_a_confirmacion(self) -> None:
        update = _make_update(text="12345678")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
            }
        )
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value = None

        result = await handle_fl_telegram_id(update, ctx)

        assert result == FL_CONFIRMACION
        assert ctx.user_data["fl_telegram_id"] == 12345678


class TestHandleFlSkipTg:
    @pytest.mark.asyncio
    async def test_skip_establece_telegram_none_y_avanza(self) -> None:
        update = _make_update(callback_data="fl_skip_tg")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
            }
        )

        result = await handle_fl_skip_tg(update, ctx)

        assert result == FL_CONFIRMACION
        assert ctx.user_data["fl_telegram_id"] is None


class TestHandleFlConfirmacion:
    @pytest.mark.asyncio
    async def test_confirmar_crea_freelancer_con_todos_los_campos(self) -> None:
        update = _make_update(callback_data="fl_confirmar")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
                "fl_telegram_id": 100,
            }
        )

        result = await handle_fl_confirmacion(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["freelancer_repo"].guardar.assert_called_once()
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.nombre == "Bryan"
        assert saved.nombre_completo == "Bryan Castro"
        assert saved.cedula == "12345678"
        assert saved.display == "Bryan C."
        assert saved.telegram_user_id == 100
        # user_data cleaned
        assert "fl_nombre" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_con_telegram_none(self) -> None:
        update = _make_update(callback_data="fl_confirmar")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
                "fl_telegram_id": None,
            }
        )

        result = await handle_fl_confirmacion(update, ctx)

        assert result == ConversationHandler.END
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.telegram_user_id is None

    @pytest.mark.asyncio
    async def test_cancelar_no_guarda_y_termina(self) -> None:
        update = _make_update(callback_data="fl_cancelar")
        ctx = _make_context(
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
                "fl_telegram_id": 100,
            }
        )

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

    @pytest.mark.asyncio
    async def test_seleccionar_con_callback_data_none_retorna_estado(self) -> None:
        """Regression: callback_query present but data=None must NOT crash (AttributeError)."""
        update = MagicMock()
        update.effective_message = AsyncMock()
        query = AsyncMock()
        query.data = None
        query.answer = AsyncMock()
        update.callback_query = query
        ctx = _make_context()

        result = await handle_ef_seleccionar(update, ctx)

        assert result == EF_SELECCIONAR
        ctx.bot_data["freelancer_repo"].buscar_por_id.assert_not_called()
        update.effective_message.edit_message_text = AsyncMock()
        update.effective_message.reply_text.assert_not_called()
