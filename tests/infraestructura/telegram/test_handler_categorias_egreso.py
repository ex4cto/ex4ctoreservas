"""Tests for /categorias_egreso handlers (category management UI)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.conciliacion.entidades import CategoriaEgreso
from garay.dominio.conciliacion.errores import CategoriaEgresoProtegida
from garay.infraestructura.telegram.handlers_egresos import (
    CAT_ACCIONES,
    CAT_EDIT_DESC,
    CAT_MENU,
    CAT_NUEVA_NOMBRE,
    CAT_NUEVA_PARECIDO,
    CB_CAT_ATRAS,
    CB_CAT_CANCELAR,
    CB_CAT_CERRAR,
    CB_CAT_CREAR_IGUAL,
    CB_CAT_EDIT_DESC,
    CB_CAT_NUEVA,
    CB_CAT_TOGGLE,
    CB_CAT_USAR_EXISTENTE,
    PREFIJO_CATSEL,
    cmd_categorias_egreso,
    handle_cat_acciones,
    handle_cat_edit_desc,
    handle_cat_menu,
    handle_cat_nueva_nombre,
    handle_cat_nueva_parecido,
)


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    if text is not None:
        update.message = MagicMock()
        update.message.text = text
        update.callback_query = None
    elif callback_data is not None:
        update.message = None
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
    else:
        update.message = None
        update.callback_query = None
    return update


def _cat(nombre: str, activo: bool = True, orden: int = 1) -> CategoriaEgreso:
    return CategoriaEgreso(nombre=nombre, descripcion="", activo=activo, orden=orden)


def _make_admin_repo() -> MagicMock:
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = True
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_context(categorias: list[CategoriaEgreso] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    service = MagicMock()
    service.listar_todas.return_value = categorias or [
        _cat("comisiones", orden=1),
        _cat("marketing", orden=2),
        _cat("transporte", orden=3),
    ]
    service.sugerir_parecida.return_value = None
    ctx.bot_data = {
        "categoria_service": service,
        "freelancer_repo": _make_admin_repo(),
    }
    return ctx


class TestCmdCategorias:
    @pytest.mark.asyncio
    async def test_lista_categorias_y_abre_menu(self) -> None:
        update = _make_update()
        ctx = _make_context()
        result = await cmd_categorias_egreso(update, ctx)
        assert result == CAT_MENU
        update.effective_message.reply_text.assert_called_once()
        markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        labels = [btn.text for row in markup.inline_keyboard for btn in row]
        assert any("comisiones" in lbl for lbl in labels)

    @pytest.mark.asyncio
    async def test_no_admin_denegado(self) -> None:
        update = _make_update()
        ctx = _make_context()
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value.es_admin = False
        result = await cmd_categorias_egreso(update, ctx)
        assert result == ConversationHandler.END


class TestMenu:
    @pytest.mark.asyncio
    async def test_boton_nueva_pide_nombre(self) -> None:
        update = _make_update(callback_data=CB_CAT_NUEVA)
        ctx = _make_context()
        result = await handle_cat_menu(update, ctx)
        assert result == CAT_NUEVA_NOMBRE

    @pytest.mark.asyncio
    async def test_cerrar_termina(self) -> None:
        update = _make_update(callback_data=CB_CAT_CERRAR)
        ctx = _make_context()
        result = await handle_cat_menu(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_seleccionar_categoria_abre_acciones(self) -> None:
        ctx = _make_context()
        # El menu guarda el mapa indice->nombre; seleccionamos el indice 0.
        await cmd_categorias_egreso(_make_update(), ctx)
        update = _make_update(callback_data=f"{PREFIJO_CATSEL}0")
        result = await handle_cat_menu(update, ctx)
        assert result == CAT_ACCIONES
        assert ctx.user_data["cat_sel_nombre"] == "comisiones"


class TestNuevaCategoria:
    @pytest.mark.asyncio
    async def test_nombre_unico_crea_y_vuelve_al_menu(self) -> None:
        update = _make_update(text="Papelería")
        ctx = _make_context()
        result = await handle_cat_nueva_nombre(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].crear.assert_called_once()

    @pytest.mark.asyncio
    async def test_nombre_duplicado_no_crea_y_repite(self) -> None:
        update = _make_update(text="Comisiones")  # ya existe "comisiones"
        ctx = _make_context()
        result = await handle_cat_nueva_nombre(update, ctx)
        assert result == CAT_NUEVA_NOMBRE
        ctx.bot_data["categoria_service"].crear.assert_not_called()

    @pytest.mark.asyncio
    async def test_nombre_parecido_pide_confirmacion(self) -> None:
        update = _make_update(text="markting")  # se parece a "marketing"
        ctx = _make_context()
        result = await handle_cat_nueva_nombre(update, ctx)
        assert result == CAT_NUEVA_PARECIDO
        ctx.bot_data["categoria_service"].crear.assert_not_called()
        assert ctx.user_data["cat_nueva_pendiente"] == "markting"

    @pytest.mark.asyncio
    async def test_parecido_crear_igual(self) -> None:
        update = _make_update(callback_data=CB_CAT_CREAR_IGUAL)
        ctx = _make_context()
        ctx.user_data["cat_nueva_pendiente"] = "markting"
        result = await handle_cat_nueva_parecido(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].crear.assert_called_once_with("markting")

    @pytest.mark.asyncio
    async def test_parecido_usar_existente_no_crea(self) -> None:
        update = _make_update(callback_data=CB_CAT_USAR_EXISTENTE)
        ctx = _make_context()
        ctx.user_data["cat_nueva_pendiente"] = "markting"
        result = await handle_cat_nueva_parecido(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].crear.assert_not_called()

    @pytest.mark.asyncio
    async def test_parecido_cancelar_no_crea(self) -> None:
        update = _make_update(callback_data=CB_CAT_CANCELAR)
        ctx = _make_context()
        ctx.user_data["cat_nueva_pendiente"] = "markting"
        result = await handle_cat_nueva_parecido(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].crear.assert_not_called()


class TestAcciones:
    @pytest.mark.asyncio
    async def test_desactivar_llama_servicio(self) -> None:
        update = _make_update(callback_data=CB_CAT_TOGGLE)
        ctx = _make_context()
        ctx.user_data.update(
            {"cat_sel_nombre": "marketing", "cat_sel_activo": True, "cat_sel_protegida": False}
        )
        result = await handle_cat_acciones(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].desactivar.assert_called_once_with("marketing")

    @pytest.mark.asyncio
    async def test_activar_llama_servicio(self) -> None:
        update = _make_update(callback_data=CB_CAT_TOGGLE)
        ctx = _make_context()
        ctx.user_data.update(
            {"cat_sel_nombre": "marketing", "cat_sel_activo": False, "cat_sel_protegida": False}
        )
        result = await handle_cat_acciones(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].activar.assert_called_once_with("marketing")

    @pytest.mark.asyncio
    async def test_desactivar_protegida_muestra_aviso(self) -> None:
        update = _make_update(callback_data=CB_CAT_TOGGLE)
        ctx = _make_context()
        ctx.user_data.update(
            {"cat_sel_nombre": "transporte", "cat_sel_activo": True, "cat_sel_protegida": True}
        )
        service = ctx.bot_data["categoria_service"]
        service.desactivar.side_effect = CategoriaEgresoProtegida("protegida")
        # No debe reventar; vuelve al menu.
        result = await handle_cat_acciones(update, ctx)
        assert result == CAT_MENU

    @pytest.mark.asyncio
    async def test_atras_vuelve_al_menu(self) -> None:
        update = _make_update(callback_data=CB_CAT_ATRAS)
        ctx = _make_context()
        result = await handle_cat_acciones(update, ctx)
        assert result == CAT_MENU

    @pytest.mark.asyncio
    async def test_editar_desc_pide_texto(self) -> None:
        update = _make_update(callback_data=CB_CAT_EDIT_DESC)
        ctx = _make_context()
        ctx.user_data["cat_sel_nombre"] = "marketing"
        result = await handle_cat_acciones(update, ctx)
        assert result == CAT_EDIT_DESC


class TestEditarDescripcion:
    @pytest.mark.asyncio
    async def test_guarda_descripcion_y_vuelve(self) -> None:
        update = _make_update(text="Publicidad y redes")
        ctx = _make_context()
        ctx.user_data["cat_sel_nombre"] = "marketing"
        result = await handle_cat_edit_desc(update, ctx)
        assert result == CAT_MENU
        ctx.bot_data["categoria_service"].editar_descripcion.assert_called_once_with(
            "marketing", "Publicidad y redes"
        )
