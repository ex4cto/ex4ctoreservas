"""Unit tests for the contacts editor in /editar_tour (EDC states 245-247)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.servicios.entidades import ContactoReserva, Servicio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _servicio(
    nombre: str = "CITY TOUR",
    categoria: str = "CARTAGENA",
    contactos: list[ContactoReserva] | None = None,
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre=nombre,
        categoria=categoria,
        contactos_reserva=contactos or [],
    )


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=123, full_name="Admin")
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
    servicios: list[Servicio] | None = None,
    user_data: dict[str, object] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    repo = MagicMock()
    if servicios is not None:
        repo.listar.return_value = servicios
        repo.listar_activos.return_value = [s for s in servicios if s.activo]
    else:
        repo.listar.return_value = []
        repo.listar_activos.return_value = []
    fsm = MagicMock()
    ctx.bot_data = {"servicio_repo": repo, "fsm": fsm}
    return ctx


# ---------------------------------------------------------------------------
# Imports under test — fail RED until implementation
# ---------------------------------------------------------------------------

from garay.infraestructura.telegram.handlers_tours import (  # noqa: E402
    _CAMPOS_EDITABLES,
    EDC_AGREGAR_NOMBRE,
    EDC_AGREGAR_NUMERO,
    EDC_LISTA,
    EDF_FICHA,
    _render_ficha,
    _teclado_contactos,
    handle_edc_agregar_nombre,
    handle_edc_agregar_numero,
    handle_edc_lista,
    handle_edt_ficha,
)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

class TestEdcStateConstants:
    def test_edc_lista_equals_245(self) -> None:
        assert EDC_LISTA == 245

    def test_edc_agregar_nombre_equals_246(self) -> None:
        assert EDC_AGREGAR_NOMBRE == 246

    def test_edc_agregar_numero_equals_247(self) -> None:
        assert EDC_AGREGAR_NUMERO == 247

    def test_constants_unique(self) -> None:
        assert len({EDC_LISTA, EDC_AGREGAR_NOMBRE, EDC_AGREGAR_NUMERO}) == 3


# ---------------------------------------------------------------------------
# _CAMPOS_EDITABLES
# ---------------------------------------------------------------------------

class TestCamposEditablesContactos:
    def test_contactos_reserva_en_campos_editables(self) -> None:
        campos = [campo for campo, _label in _CAMPOS_EDITABLES]
        assert "contactos_reserva" in campos


# ---------------------------------------------------------------------------
# _render_ficha with contactos
# ---------------------------------------------------------------------------

class TestRenderFichaContactos:
    def test_sin_contactos_muestra_guion(self) -> None:
        s = _servicio(contactos=[])
        assert "—" in _render_ficha(s)

    def test_con_un_contacto_muestra_nombre_y_numero(self) -> None:
        s = _servicio(contactos=[ContactoReserva(nombre="MARINATOUR", numero="3043752759")])
        ficha = _render_ficha(s)
        assert "MARINATOUR" in ficha
        assert "3043752759" in ficha

    def test_con_dos_contactos_muestra_ambos(self) -> None:
        s = _servicio(contactos=[
            ContactoReserva(nombre="MARINATOUR", numero="3043752759"),
            ContactoReserva(nombre="CTG TOURS", numero="3021295767"),
        ])
        ficha = _render_ficha(s)
        assert "MARINATOUR" in ficha
        assert "CTG TOURS" in ficha


# ---------------------------------------------------------------------------
# _teclado_contactos
# ---------------------------------------------------------------------------

class TestTecladoContactos:
    def test_lista_vacia_tiene_tres_filas(self) -> None:
        markup = _teclado_contactos([])
        assert len(markup.inline_keyboard) == 3

    def test_lista_vacia_tiene_agregar_atras_cancelar(self) -> None:
        markup = _teclado_contactos([])
        callbacks = [row[0].callback_data for row in markup.inline_keyboard]
        assert "edc_agregar" in callbacks
        assert "edc_atras" in callbacks
        assert "edc_cancelar" in callbacks

    def test_un_contacto_tiene_cuatro_filas(self) -> None:
        contactos = [ContactoReserva(nombre="MARINATOUR", numero="3043752759")]
        markup = _teclado_contactos(contactos)
        assert len(markup.inline_keyboard) == 4

    def test_boton_quitar_callback_correcto(self) -> None:
        contactos = [ContactoReserva(nombre="MARINATOUR", numero="3043752759")]
        markup = _teclado_contactos(contactos)
        assert markup.inline_keyboard[0][0].callback_data == "edc_quitar:0"

    def test_dos_contactos_indices_correctos(self) -> None:
        contactos = [
            ContactoReserva(nombre="A", numero="3000000001"),
            ContactoReserva(nombre="B", numero="3000000002"),
        ]
        markup = _teclado_contactos(contactos)
        assert markup.inline_keyboard[0][0].callback_data == "edc_quitar:0"
        assert markup.inline_keyboard[1][0].callback_data == "edc_quitar:1"

    def test_agregar_callback(self) -> None:
        markup = _teclado_contactos([])
        callbacks = [row[0].callback_data for row in markup.inline_keyboard]
        assert "edc_agregar" in callbacks

    def test_atras_callback(self) -> None:
        markup = _teclado_contactos([])
        callbacks = [row[0].callback_data for row in markup.inline_keyboard]
        assert "edc_atras" in callbacks

    def test_cancelar_callback(self) -> None:
        markup = _teclado_contactos([])
        callbacks = [row[0].callback_data for row in markup.inline_keyboard]
        assert "edc_cancelar" in callbacks


# ---------------------------------------------------------------------------
# handle_edt_ficha — campo contactos_reserva
# ---------------------------------------------------------------------------

class TestHandleEdtFichaContactos:
    @pytest.mark.asyncio
    async def test_campo_contactos_abre_editor(self) -> None:
        s = _servicio()
        update = _make_update(callback_data="edt_campo:contactos_reserva")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edt_ficha(update, ctx)

        assert result == EDC_LISTA

    @pytest.mark.asyncio
    async def test_campo_contactos_envia_teclado(self) -> None:
        from telegram import InlineKeyboardMarkup

        s = _servicio()
        update = _make_update(callback_data="edt_campo:contactos_reserva")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        await handle_edt_ficha(update, ctx)

        call_args = update.effective_message.reply_text.call_args_list
        keyboards = [
            c.kwargs.get("reply_markup") or (c.args[1] if len(c.args) > 1 else None)
            for c in call_args
        ]
        assert any(isinstance(k, InlineKeyboardMarkup) for k in keyboards)


# ---------------------------------------------------------------------------
# handle_edc_lista
# ---------------------------------------------------------------------------

class TestHandleEdcLista:
    @pytest.mark.asyncio
    async def test_edc_agregar_va_a_agregar_nombre(self) -> None:
        s = _servicio()
        update = _make_update(callback_data="edc_agregar")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_lista(update, ctx)

        assert result == EDC_AGREGAR_NOMBRE

    @pytest.mark.asyncio
    async def test_edc_atras_va_a_edf_ficha(self) -> None:
        s = _servicio()
        update = _make_update(callback_data="edc_atras")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_lista(update, ctx)

        assert result == EDF_FICHA

    @pytest.mark.asyncio
    async def test_edc_cancelar_termina_flujo(self) -> None:
        s = _servicio()
        update = _make_update(callback_data="edc_cancelar")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_lista(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_edc_quitar_elimina_contacto_y_guarda(self) -> None:
        contacto = ContactoReserva(nombre="MARINATOUR", numero="3043752759")
        s = _servicio(contactos=[contacto])
        update = _make_update(callback_data="edc_quitar:0")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_lista(update, ctx)

        assert result == EDC_LISTA
        ctx.bot_data["servicio_repo"].guardar.assert_called_once()
        saved = ctx.bot_data["servicio_repo"].guardar.call_args[0][0]
        assert saved.contactos_reserva == []

    @pytest.mark.asyncio
    async def test_edc_quitar_deja_el_otro_contacto(self) -> None:
        c1 = ContactoReserva(nombre="A", numero="3000000001")
        c2 = ContactoReserva(nombre="B", numero="3000000002")
        s = _servicio(contactos=[c1, c2])
        update = _make_update(callback_data="edc_quitar:0")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_lista(update, ctx)

        assert result == EDC_LISTA
        saved = ctx.bot_data["servicio_repo"].guardar.call_args[0][0]
        assert len(saved.contactos_reserva) == 1
        assert saved.contactos_reserva[0].nombre == "B"


# ---------------------------------------------------------------------------
# handle_edc_agregar_nombre
# ---------------------------------------------------------------------------

class TestHandleEdcAgregarNombre:
    @pytest.mark.asyncio
    async def test_nombre_vacio_queda_en_estado(self) -> None:
        update = _make_update(text="")
        ctx = _make_context()

        result = await handle_edc_agregar_nombre(update, ctx)

        assert result == EDC_AGREGAR_NOMBRE
        assert "edc_nombre_pendiente" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_solo_espacios_queda_en_estado(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_edc_agregar_nombre(update, ctx)

        assert result == EDC_AGREGAR_NOMBRE

    @pytest.mark.asyncio
    async def test_nombre_valido_guarda_y_avanza(self) -> None:
        update = _make_update(text="MARINATOUR CARTAGENA")
        ctx = _make_context()

        result = await handle_edc_agregar_nombre(update, ctx)

        assert result == EDC_AGREGAR_NUMERO
        assert ctx.user_data["edc_nombre_pendiente"] == "MARINATOUR CARTAGENA"


# ---------------------------------------------------------------------------
# handle_edc_agregar_numero
# ---------------------------------------------------------------------------

class TestHandleEdcAgregarNumero:
    @pytest.mark.asyncio
    async def test_numero_vacio_queda_en_estado(self) -> None:
        s = _servicio()
        update = _make_update(text="")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_agregar_numero(update, ctx)

        assert result == EDC_AGREGAR_NUMERO
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_numero_letras_rechazado(self) -> None:
        s = _servicio()
        update = _make_update(text="abc")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_agregar_numero(update, ctx)

        assert result == EDC_AGREGAR_NUMERO
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_numero_muy_corto_rechazado(self) -> None:
        s = _servicio()
        update = _make_update(text="123456")  # 6 digits, min is 7
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_agregar_numero(update, ctx)

        assert result == EDC_AGREGAR_NUMERO
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_numero_valido_guarda_y_vuelve_a_lista(self) -> None:
        s = _servicio()
        update = _make_update(text="3001234567")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_agregar_numero(update, ctx)

        assert result == EDC_LISTA
        ctx.bot_data["servicio_repo"].guardar.assert_called_once()

    @pytest.mark.asyncio
    async def test_numero_con_prefijo_mas_valido(self) -> None:
        s = _servicio()
        update = _make_update(text="+573001234567")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        result = await handle_edc_agregar_numero(update, ctx)

        assert result == EDC_LISTA

    @pytest.mark.asyncio
    async def test_numero_valido_limpia_nombre_pendiente(self) -> None:
        s = _servicio()
        update = _make_update(text="3001234567")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        await handle_edc_agregar_numero(update, ctx)

        assert "edc_nombre_pendiente" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_numero_valido_agrega_contacto_reserva(self) -> None:
        s = _servicio()
        update = _make_update(text="3001234567")
        ctx = _make_context(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edc_nombre_pendiente": "MARINATOUR"},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s

        await handle_edc_agregar_numero(update, ctx)

        saved = ctx.bot_data["servicio_repo"].guardar.call_args[0][0]
        assert len(saved.contactos_reserva) == 1
        assert saved.contactos_reserva[0].nombre == "MARINATOUR"
        assert saved.contactos_reserva[0].numero == "3001234567"


# ---------------------------------------------------------------------------
# Bot wiring
# ---------------------------------------------------------------------------

class TestEdcStatesBotWiring:
    def _get_editar_conv(self) -> object:
        from unittest.mock import MagicMock, patch

        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.bot import crear_aplicacion

        with patch("garay.infraestructura.telegram.bot.obtener_settings") as ms:
            settings = MagicMock()
            settings.propietario_telegram_ids = ""
            settings.dev_telegram_ids = ""
            ms.return_value = settings
            app = crear_aplicacion("fake:token")

        for _group, handlers in app.handlers.items():
            for h in handlers:
                if isinstance(h, ConversationHandler):
                    for ep in h.entry_points:
                        if hasattr(ep, "commands") and "editar_tour" in ep.commands:
                            return h
        return None

    def test_edc_lista_registered(self) -> None:
        from telegram.ext import ConversationHandler

        conv = self._get_editar_conv()
        assert conv is not None
        assert isinstance(conv, ConversationHandler)
        assert EDC_LISTA in conv.states

    def test_edc_agregar_nombre_registered(self) -> None:
        from telegram.ext import ConversationHandler

        conv = self._get_editar_conv()
        assert conv is not None
        assert isinstance(conv, ConversationHandler)
        assert EDC_AGREGAR_NOMBRE in conv.states

    def test_edc_agregar_numero_registered(self) -> None:
        from telegram.ext import ConversationHandler

        conv = self._get_editar_conv()
        assert conv is not None
        assert isinstance(conv, ConversationHandler)
        assert EDC_AGREGAR_NUMERO in conv.states

    def test_edc_agregar_nombre_tiene_un_solo_message_handler(self) -> None:
        from telegram.ext import ConversationHandler, MessageHandler

        conv = self._get_editar_conv()
        assert conv is not None
        assert isinstance(conv, ConversationHandler)
        handlers_list = conv.states.get(EDC_AGREGAR_NOMBRE, [])
        text_handlers = [h for h in handlers_list if isinstance(h, MessageHandler)]
        assert len(text_handlers) == 1

    def test_edc_agregar_numero_tiene_un_solo_message_handler(self) -> None:
        from telegram.ext import ConversationHandler, MessageHandler

        conv = self._get_editar_conv()
        assert conv is not None
        assert isinstance(conv, ConversationHandler)
        handlers_list = conv.states.get(EDC_AGREGAR_NUMERO, [])
        text_handlers = [h for h in handlers_list if isinstance(h, MessageHandler)]
        assert len(text_handlers) == 1
