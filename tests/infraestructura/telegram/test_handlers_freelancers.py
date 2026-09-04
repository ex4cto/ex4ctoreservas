"""Unit tests for freelancer management handlers."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.infraestructura.telegram.handlers_freelancers import (
    EDITAR_CAMPO,
    EDITAR_CONFIRMAR,
    EDITAR_SELECCIONAR,
    EDITAR_VALOR,
    EF_CONFIRMAR,
    EF_SELECCIONAR,
    FL_CEDULA,
    FL_CONFIRMACION,
    FL_DISPLAY_OVERRIDE,
    FL_EMAIL,
    FL_NOMBRE_COMPLETO,
    FL_NOMBRE_CORTO,
    FL_TELEGRAM_ID,
    _render_ficha,
    cmd_editar_freelancer,
    cmd_eliminar_freelancer,
    cmd_listar_freelancers,
    cmd_nuevo_freelancer,
    handle_edf_activo_toggle,
    handle_edf_campo,
    handle_edf_confirmar,
    handle_edf_seleccionar,
    handle_edf_valor,
    handle_ef_confirmar,
    handle_ef_seleccionar,
    handle_fl_cedula,
    handle_fl_confirmacion,
    handle_fl_display_override,
    handle_fl_email,
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

        assert result == FL_EMAIL
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

        assert result == FL_EMAIL
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


# ---------------------------------------------------------------------------
# A2 state constants
# ---------------------------------------------------------------------------


class TestEditorFreelancerStateConstants:
    def test_editar_seleccionar_valor(self) -> None:
        assert EDITAR_SELECCIONAR == 210

    def test_editar_campo_valor(self) -> None:
        assert EDITAR_CAMPO == 211

    def test_editar_valor_valor(self) -> None:
        assert EDITAR_VALOR == 212

    def test_editar_confirmar_valor(self) -> None:
        assert EDITAR_CONFIRMAR == 213

    def test_no_collision_with_a1_constants(self) -> None:
        a1 = {FL_TELEGRAM_ID, FL_CONFIRMACION, FL_NOMBRE_CORTO, FL_DISPLAY_OVERRIDE,
               EF_SELECCIONAR, EF_CONFIRMAR, FL_NOMBRE_COMPLETO, FL_CEDULA, FL_EMAIL}
        a2 = {EDITAR_SELECCIONAR, EDITAR_CAMPO, EDITAR_VALOR, EDITAR_CONFIRMAR}
        assert a1.isdisjoint(a2), f"Collision: {a1 & a2}"


# ---------------------------------------------------------------------------
# A2 helpers
# ---------------------------------------------------------------------------


def _make_freelancer(
    nombre: str = "Ana",
    activo: bool = True,
    cedula: str | None = "1234567",
    telegram_user_id: int | None = None,
    nombre_completo: str | None = "Ana Garcia",
) -> Freelancer:
    return Freelancer(
        id=uuid.uuid4(),
        nombre=nombre,
        activo=activo,
        telegram_user_id=telegram_user_id,
        es_admin=False,
        cedula=cedula,
        nombre_completo=nombre_completo,
        display=None,
    )


def _make_context_edf(
    freelancers: list[Freelancer] | None = None,
    user_data: Mapping[str, object] | None = None,
    buscar_por_id_result: Freelancer | None = None,
    buscar_por_cedula_result: Freelancer | None = None,
    buscar_por_telegram_result: Freelancer | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data or {}
    repo = MagicMock()
    if freelancers is not None:
        repo.listar_todos.return_value = freelancers
    repo.buscar_por_id.return_value = buscar_por_id_result
    repo.buscar_por_cedula.return_value = buscar_por_cedula_result
    repo.buscar_por_telegram_id_cualquier_estado.return_value = buscar_por_telegram_result
    ctx.bot_data = {"freelancer_repo": repo}
    return ctx


# ---------------------------------------------------------------------------
# cmd_editar_freelancer
# ---------------------------------------------------------------------------


class TestCmdEditarFreelancer:
    @pytest.mark.asyncio
    async def test_roster_no_vacio_retorna_editar_seleccionar(self) -> None:
        f = _make_freelancer()
        update = _make_update()
        ctx = _make_context_edf(freelancers=[f])

        result = await cmd_editar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EDITAR_SELECCIONAR
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_roster_vacio_retorna_end(self) -> None:
        update = _make_update()
        ctx = _make_context_edf(freelancers=[])

        result = await cmd_editar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_inactivo_marcado_en_etiqueta(self) -> None:
        fi = _make_freelancer("Inactivo", activo=False)
        update = _make_update()
        ctx = _make_context_edf(freelancers=[fi])

        await cmd_editar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        call_kwargs = update.effective_message.reply_text.call_args
        # The reply_markup kwarg should contain the [inactivo] marker
        markup = call_kwargs.kwargs.get("reply_markup") or call_kwargs[1].get("reply_markup")
        buttons_text = " ".join(
            btn.text for row in markup.inline_keyboard for btn in row
        )
        assert "[inactivo]" in buttons_text.lower()


# ---------------------------------------------------------------------------
# handle_edf_seleccionar
# ---------------------------------------------------------------------------


class TestHandleEdfSeleccionar:
    @pytest.mark.asyncio
    async def test_activo_almacena_id_y_retorna_editar_campo(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data=f"edf_sel:{f.id}")
        ctx = _make_context_edf()

        result = await handle_edf_seleccionar(update, ctx)

        assert result == EDITAR_CAMPO
        assert ctx.user_data["edf_target_id"] == str(f.id)

    @pytest.mark.asyncio
    async def test_inactivo_tambien_seleccionable(self) -> None:
        fi = _make_freelancer(activo=False)
        update = _make_update(callback_data=f"edf_sel:{fi.id}")
        ctx = _make_context_edf()

        result = await handle_edf_seleccionar(update, ctx)

        assert result == EDITAR_CAMPO
        assert ctx.user_data["edf_target_id"] == str(fi.id)

    @pytest.mark.asyncio
    async def test_menu_campo_enviado_con_boton_listo(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data=f"edf_sel:{f.id}")
        ctx = _make_context_edf()

        await handle_edf_seleccionar(update, ctx)

        update.effective_message.reply_text.assert_called_once()
        call_kwargs = update.effective_message.reply_text.call_args
        markup = call_kwargs.kwargs.get("reply_markup") or call_kwargs[1].get("reply_markup")
        buttons_cb = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "edf_listo" in buttons_cb


# ---------------------------------------------------------------------------
# handle_edf_campo
# ---------------------------------------------------------------------------


class TestHandleEdfCampo:
    @pytest.mark.asyncio
    async def test_nombre_completo_retorna_editar_valor(self) -> None:
        update = _make_update(callback_data="edf_campo:nombre_completo")
        ctx = _make_context_edf()

        result = await handle_edf_campo(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_cedula_retorna_editar_valor(self) -> None:
        update = _make_update(callback_data="edf_campo:cedula")
        ctx = _make_context_edf()

        result = await handle_edf_campo(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_nombre_retorna_editar_valor(self) -> None:
        update = _make_update(callback_data="edf_campo:nombre")
        ctx = _make_context_edf()

        result = await handle_edf_campo(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_telegram_id_retorna_editar_valor(self) -> None:
        update = _make_update(callback_data="edf_campo:telegram_id")
        ctx = _make_context_edf()

        result = await handle_edf_campo(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_activo_retorna_editar_confirmar(self) -> None:
        f = _make_freelancer()
        target_id = str(f.id)
        update = _make_update(callback_data="edf_campo:activo")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={"edf_target_id": target_id},
        )

        result = await handle_edf_campo(update, ctx)

        assert result == EDITAR_CONFIRMAR

    @pytest.mark.asyncio
    async def test_edf_listo_termina_conversacion(self) -> None:
        update = _make_update(callback_data="edf_listo")
        ctx = _make_context_edf(user_data={
            "edf_target_id": str(uuid.uuid4()),
            "edf_campo": "nombre",
        })

        result = await handle_edf_campo(update, ctx)

        assert result == ConversationHandler.END
        # keys cleared
        assert "edf_target_id" not in ctx.user_data


# ---------------------------------------------------------------------------
# handle_edf_valor — cedula path
# ---------------------------------------------------------------------------


class TestHandleEdfValorCedula:
    @pytest.mark.asyncio
    async def test_cedula_invalida_permanece_en_editar_valor(self) -> None:
        update = _make_update(text="123")
        ud = {"edf_campo": "cedula", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_cedula_duplicada_otro_permanece_en_editar_valor(self) -> None:
        otro = _make_freelancer("Otro")
        target_id = str(uuid.uuid4())
        update = _make_update(text="9876543")
        ctx = _make_context_edf(
            buscar_por_cedula_result=otro,  # different id from target
            user_data={"edf_campo": "cedula", "edf_target_id": target_id},
        )

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_cedula_propia_no_es_duplicado(self) -> None:
        """CRITICAL EDGE: own current cedula must NOT be treated as duplicate."""
        f = _make_freelancer(cedula="9876543")
        update = _make_update(text="9876543")
        ctx = _make_context_edf(
            buscar_por_cedula_result=f,  # same freelancer
            user_data={"edf_campo": "cedula", "edf_target_id": str(f.id)},
        )

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR

    @pytest.mark.asyncio
    async def test_cedula_nueva_valida_avanza_a_confirmar(self) -> None:
        update = _make_update(text="9876543")
        ctx = _make_context_edf(
            buscar_por_cedula_result=None,
            user_data={"edf_campo": "cedula", "edf_target_id": str(uuid.uuid4())},
        )

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR


# ---------------------------------------------------------------------------
# handle_edf_valor — telegram_id path
# ---------------------------------------------------------------------------


class TestHandleEdfValorTelegramId:
    @pytest.mark.asyncio
    async def test_no_int_permanece_en_editar_valor(self) -> None:
        update = _make_update(text="abc")
        ud = {"edf_campo": "telegram_id", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_duplicado_otro_permanece_en_editar_valor(self) -> None:
        otro = _make_freelancer("Otro", telegram_user_id=99887766)
        target_id = str(uuid.uuid4())
        update = _make_update(text="99887766")
        ctx = _make_context_edf(
            buscar_por_telegram_result=otro,
            user_data={"edf_campo": "telegram_id", "edf_target_id": target_id},
        )

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_telegram_id_propio_no_es_duplicado(self) -> None:
        """CRITICAL EDGE: own current telegram_id must NOT be treated as duplicate."""
        f = _make_freelancer(telegram_user_id=11223344)
        update = _make_update(text="11223344")
        ctx = _make_context_edf(
            buscar_por_telegram_result=f,  # same freelancer
            user_data={"edf_campo": "telegram_id", "edf_target_id": str(f.id)},
        )

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR

    @pytest.mark.asyncio
    async def test_edf_tg_none_establece_none_y_avanza(self) -> None:
        update = _make_update(callback_data="edf_tg_none")
        ud = {"edf_campo": "telegram_id", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR
        assert ctx.user_data.get("edf_valor") is None

    @pytest.mark.asyncio
    async def test_telegram_id_nuevo_valido_avanza(self) -> None:
        update = _make_update(text="55667788")
        ctx = _make_context_edf(
            buscar_por_telegram_result=None,
            user_data={"edf_campo": "telegram_id", "edf_target_id": str(uuid.uuid4())},
        )

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR


# ---------------------------------------------------------------------------
# handle_edf_valor — nombre_completo + nombre paths
# ---------------------------------------------------------------------------


class TestHandleEdfValorNombre:
    @pytest.mark.asyncio
    async def test_nombre_completo_vacio_permanece_en_editar_valor(self) -> None:
        update = _make_update(text="   ")
        ud = {"edf_campo": "nombre_completo", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_nombre_completo_valido_avanza(self) -> None:
        update = _make_update(text="Bryan Castro")
        ud = {"edf_campo": "nombre_completo", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR
        assert ctx.user_data["edf_valor"] == "Bryan Castro"

    @pytest.mark.asyncio
    async def test_nombre_vacio_permanece_en_editar_valor(self) -> None:
        update = _make_update(text="")
        ud = {"edf_campo": "nombre", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_nombre_valido_avanza(self) -> None:
        update = _make_update(text="Bryan")
        ud = {"edf_campo": "nombre", "edf_target_id": str(uuid.uuid4())}
        ctx = _make_context_edf(user_data=ud)

        result = await handle_edf_valor(update, ctx)

        assert result == EDITAR_CONFIRMAR


# ---------------------------------------------------------------------------
# handle_edf_activo_toggle
# ---------------------------------------------------------------------------


class TestHandleEdfActivoToggle:
    @pytest.mark.asyncio
    async def test_activo_true_almacena_true(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data="edf_activo:true")
        ctx = _make_context_edf(user_data={"edf_target_id": str(f.id), "edf_campo": "activo"})

        result = await handle_edf_activo_toggle(update, ctx)

        assert result == EDITAR_CONFIRMAR
        assert ctx.user_data["edf_activo"] is True

    @pytest.mark.asyncio
    async def test_activo_false_almacena_false(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data="edf_activo:false")
        ctx = _make_context_edf(user_data={"edf_target_id": str(f.id), "edf_campo": "activo"})

        result = await handle_edf_activo_toggle(update, ctx)

        assert result == EDITAR_CONFIRMAR
        assert ctx.user_data["edf_activo"] is False


# ---------------------------------------------------------------------------
# handle_edf_confirmar
# ---------------------------------------------------------------------------


class TestHandleEdfConfirmar:
    @pytest.mark.asyncio
    async def test_confirmar_nombre_completo_actualiza_display_y_retorna_campo(self) -> None:
        f = _make_freelancer()
        target_id = str(f.id)
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": target_id,
                "edf_campo": "nombre_completo",
                "edf_valor": "Bryan Castro Gomez",
            },
        )

        result = await handle_edf_confirmar(update, ctx)

        # Returns to field menu, NOT END
        assert result == EDITAR_CAMPO
        # guardar called once
        ctx.bot_data["freelancer_repo"].guardar.assert_called_once()
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.nombre_completo == "Bryan Castro Gomez"
        # display re-derived
        assert saved.display is not None
        # edf_target_id persists for next loop
        assert ctx.user_data.get("edf_target_id") == target_id

    @pytest.mark.asyncio
    async def test_confirmar_activo_modifica_y_retorna_campo(self) -> None:
        f = _make_freelancer(activo=True)
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "activo",
                "edf_activo": False,
            },
        )

        result = await handle_edf_confirmar(update, ctx)

        assert result == EDITAR_CAMPO
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.activo is False

    @pytest.mark.asyncio
    async def test_cancelar_no_guarda_y_termina(self) -> None:
        update = _make_update(callback_data="edf_cancelar")
        ctx = _make_context_edf(
            user_data={
                "edf_target_id": str(uuid.uuid4()),
                "edf_campo": "cedula",
                "edf_valor": "9999999",
            },
        )

        result = await handle_edf_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["freelancer_repo"].guardar.assert_not_called()
        # all edf_* keys cleared on cancel
        assert "edf_target_id" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_cedula_retorna_campo(self) -> None:
        f = _make_freelancer(cedula="1234567")
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "cedula",
                "edf_valor": "9876543",
            },
        )

        result = await handle_edf_confirmar(update, ctx)

        assert result == EDITAR_CAMPO
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.cedula == "9876543"

    @pytest.mark.asyncio
    async def test_confirmar_nombre_retorna_campo(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "nombre",
                "edf_valor": "Brayan",
            },
        )

        result = await handle_edf_confirmar(update, ctx)

        assert result == EDITAR_CAMPO
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.nombre == "Brayan"

    @pytest.mark.asyncio
    async def test_confirmar_telegram_id_none_guarda_none(self) -> None:
        f = _make_freelancer(telegram_user_id=11223344)
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "telegram_id",
                "edf_valor": None,
            },
        )

        result = await handle_edf_confirmar(update, ctx)

        assert result == EDITAR_CAMPO
        saved: Freelancer = ctx.bot_data["freelancer_repo"].guardar.call_args[0][0]
        assert saved.telegram_user_id is None

    @pytest.mark.asyncio
    async def test_target_id_persists_after_confirm(self) -> None:
        """CRITICAL EDGE: edf_target_id must survive confirm for multi-edit loop."""
        f = _make_freelancer(nombre="Test")
        target_id = str(f.id)
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": target_id,
                "edf_campo": "nombre",
                "edf_valor": "TestNew",
            },
        )

        await handle_edf_confirmar(update, ctx)

        assert ctx.user_data.get("edf_target_id") == target_id


# ---------------------------------------------------------------------------
# _render_ficha + freelancer detail card on select / after edit
# ---------------------------------------------------------------------------


def _reply_texts(update: MagicMock) -> list[str]:
    """Collect the first positional arg of every reply_text call."""
    return [
        call.args[0]
        for call in update.effective_message.reply_text.call_args_list
        if call.args
    ]


class TestRenderFicha:
    def test_incluye_todos_los_campos(self) -> None:
        f = _make_freelancer(
            nombre="Ana",
            nombre_completo="Ana Maria Garcia",
            cedula="1234567",
            activo=True,
        )

        ficha = _render_ficha(f)

        assert "Ana Maria Garcia" in ficha  # nombre completo
        assert "Ana" in ficha  # nombre corto
        assert "1234567" in ficha  # cedula
        assert "Activo" in ficha  # estado

    def test_campos_vacios_muestran_guion(self) -> None:
        f = _make_freelancer(nombre="Solo", nombre_completo=None, cedula=None, activo=False)

        ficha = _render_ficha(f)

        assert "—" in ficha
        assert "Inactivo" in ficha


class TestFichaEnSeleccionar:
    @pytest.mark.asyncio
    async def test_muestra_ficha_al_seleccionar(self) -> None:
        f = _make_freelancer(nombre="Ana", nombre_completo="Ana Maria Garcia")
        update = _make_update(callback_data=f"edf_sel:{f.id}")
        ctx = _make_context_edf(buscar_por_id_result=f)

        result = await handle_edf_seleccionar(update, ctx)

        assert result == EDITAR_CAMPO
        textos = _reply_texts(update)
        assert any("Ana Maria Garcia" in t for t in textos)


class TestFichaEnConfirmar:
    @pytest.mark.asyncio
    async def test_ecoa_ficha_con_nombre_completo_nuevo(self) -> None:
        f = _make_freelancer(nombre="Ana", nombre_completo="Ana Garcia")
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "nombre_completo",
                "edf_valor": "Ana Maria Garcia Lopez",
            },
        )

        await handle_edf_confirmar(update, ctx)

        textos = _reply_texts(update)
        assert any("Ana Maria Garcia Lopez" in t for t in textos)


# ---------------------------------------------------------------------------
# Roster refresh: mutating a freelancer must refresh the sale-flow FSM roster
# ---------------------------------------------------------------------------


class TestFreelancerRefrescaFSM:
    @pytest.mark.asyncio
    async def test_crear_refresca_fsm(self) -> None:
        update = _make_update(callback_data="fl_confirmar")
        ctx = _make_context(
            freelancers=[_freelancer("Bryan")],
            user_data={
                "fl_nombre": "Bryan",
                "fl_nombre_completo": "Bryan Castro",
                "fl_cedula": "12345678",
                "fl_display": "Bryan C.",
                "fl_telegram_id": 100,
            },
        )
        fsm = MagicMock()
        ctx.bot_data["fsm"] = fsm

        await handle_fl_confirmacion(update, ctx)

        fsm.refrescar_freelancers.assert_called_once()

    @pytest.mark.asyncio
    async def test_eliminar_refresca_fsm(self) -> None:
        f = _freelancer("Ana")
        update = _make_update(callback_data="ef_confirmar")
        ctx = _make_context(
            freelancers=[f],
            user_data={"ef_freelancer_id": str(f.id), "ef_freelancer_nombre": "Ana"},
        )
        ctx.bot_data["freelancer_repo"].buscar_por_id.return_value = f
        fsm = MagicMock()
        ctx.bot_data["fsm"] = fsm

        await handle_ef_confirmar(update, ctx)

        fsm.refrescar_freelancers.assert_called_once()

    @pytest.mark.asyncio
    async def test_editar_refresca_fsm(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            freelancers=[f],
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "nombre",
                "edf_valor": "Ana Maria",
            },
        )
        fsm = MagicMock()
        ctx.bot_data["fsm"] = fsm

        await handle_edf_confirmar(update, ctx)

        fsm.refrescar_freelancers.assert_called_once()


class TestEmailFreelancer:
    """E2: email en crear (/nuevo_freelancer) y editar (/editar_freelancer)."""

    @pytest.mark.asyncio
    async def test_crear_email_valido_avanza_confirmacion(self) -> None:
        update = _make_update(text="cerrador@garay.com")
        ctx = _make_context(user_data={"fl_nombre": "Bryan", "fl_cedula": "12345678"})
        result = await handle_fl_email(update, ctx)
        assert result == FL_CONFIRMACION
        assert ctx.user_data["fl_email"] == "cerrador@garay.com"

    @pytest.mark.asyncio
    async def test_crear_email_no_omite(self) -> None:
        update = _make_update(text="no")
        ctx = _make_context(user_data={"fl_nombre": "Bryan", "fl_cedula": "12345678"})
        result = await handle_fl_email(update, ctx)
        assert result == FL_CONFIRMACION
        assert ctx.user_data["fl_email"] is None

    @pytest.mark.asyncio
    async def test_crear_email_invalido_repregunta(self) -> None:
        update = _make_update(text="malito")
        ctx = _make_context(user_data={})
        result = await handle_fl_email(update, ctx)
        assert result == FL_EMAIL
        assert "fl_email" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_editar_email_valido(self) -> None:
        update = _make_update(text="cerr@garay.com")
        ctx = _make_context_edf(
            user_data={"edf_campo": "email", "edf_target_id": str(uuid.uuid4())}
        )
        result = await handle_edf_valor(update, ctx)
        assert result == EDITAR_CONFIRMAR
        assert ctx.user_data["edf_valor"] == "cerr@garay.com"

    @pytest.mark.asyncio
    async def test_editar_email_invalido(self) -> None:
        update = _make_update(text="malito")
        ctx = _make_context_edf(
            user_data={"edf_campo": "email", "edf_target_id": str(uuid.uuid4())}
        )
        result = await handle_edf_valor(update, ctx)
        assert result == EDITAR_VALOR

    @pytest.mark.asyncio
    async def test_editar_email_se_guarda(self) -> None:
        f = _make_freelancer()
        update = _make_update(callback_data="edf_confirmar")
        ctx = _make_context_edf(
            buscar_por_id_result=f,
            user_data={
                "edf_target_id": str(f.id),
                "edf_campo": "email",
                "edf_valor": "cerr@garay.com",
            },
        )
        await handle_edf_confirmar(update, ctx)
        assert f.email == "cerr@garay.com"
