"""Tests for /gestionar_ventas ConversationHandler — B2 + B3 (TDD)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_CONFIRMAR,
    GV_DETALLE,
    GV_EDIT_CAMPO,
    GV_EDIT_FECHA,
    GV_EDIT_VALOR,
    GV_MOTIVO,
    GV_SELECCIONAR,
    cmd_gestionar_ventas,
    handle_gv_confirmar,
    handle_gv_detalle,
    handle_gv_edit_campo,
    handle_gv_edit_fecha,
    handle_gv_edit_valor,
    handle_gv_motivo,
    handle_gv_seleccionar,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_venta(
    venta_id: uuid.UUID | None = None,
    cliente_id: uuid.UUID | None = None,
    fecha: datetime.date | None = None,
    valor_monto: float = 500_000,
    vendedor_nombre: str | None = "Ana",
    cerrador_nombre: str | None = "Luis",
) -> MagicMock:
    from garay.dominio.comun.tipos import TipoCliente
    v = MagicMock()
    v.id = venta_id or uuid.uuid4()
    v.cliente_id = cliente_id or uuid.uuid4()
    v.servicio_ids = [uuid.uuid4()]
    v.fecha = fecha or datetime.date(2026, 8, 1)
    v.valor_venta = Dinero(Decimal(str(int(valor_monto))), "COP")
    v.neto = Decimal("400000")
    v.ganancia = Decimal("100000")
    v.abono = None
    v.adultos = 1
    v.ninos = 0
    v.metodo_pago = None
    v.registrado_en = None
    v.tipo_cliente = TipoCliente.EXTERNO
    v.canal_origen = None
    v.participantes = MagicMock()
    v.participantes.vendedor_nombre = vendedor_nombre
    v.participantes.cerrador_nombre = cerrador_nombre
    v.participantes.punto_de_venta_id = None
    return v


def _make_update(
    user_id: int = 123,
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


def _make_admin_freelancer() -> MagicMock:
    f = MagicMock()
    f.es_admin = True
    f.nombre = "Admin"
    return f


def _make_context(
    ventas: list[MagicMock] | None = None,
    freelancer: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}

    # bot must be an AsyncMock so _notificar_edicion can await bot.send_message.
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    ctx.bot.delete_message = AsyncMock()

    venta_repo = MagicMock()
    ventas_list = ventas or []
    venta_repo.listar_para_gestion.return_value = ventas_list
    venta_repo.listar_por_periodo.return_value = ventas_list

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer or _make_admin_freelancer()

    cliente_repo = MagicMock()
    cliente = MagicMock()
    cliente.nombre = "Juan Perez"
    cliente_repo.buscar_por_id.return_value = cliente

    servicio_repo = MagicMock()
    servicio = MagicMock()
    servicio.nombre = "Tour Isla"
    servicio_repo.buscar_por_id.return_value = servicio

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = []

    anular_service = MagicMock()
    editar_fecha_service = MagicMock()
    editar_cliente_service = MagicMock()
    notificador = MagicMock()

    comision_registrada_repo = MagicMock()
    comision_registrada_repo.buscar_por_venta_id.return_value = None
    tiquetera_repo = MagicMock()
    tiquetera_repo.buscar_por_venta_id.return_value = None

    ctx.bot_data = {
        "venta_repo": venta_repo,
        "freelancer_repo": freelancer_repo,
        "cliente_repo": cliente_repo,
        "servicio_repo": servicio_repo,
        "anular_venta_service": anular_service,
        "editar_fecha_venta_service": editar_fecha_service,
        "editar_cliente_venta_service": editar_cliente_service,
        "notificador": notificador,
        "grupo_id": "-1001234567",
        "socios_config_repo": socios_config_repo,
        "comision_registrada_repo": comision_registrada_repo,
        "tiquetera_repo": tiquetera_repo,
    }
    return ctx


# ---------------------------------------------------------------------------
# cmd_gestionar_ventas
# ---------------------------------------------------------------------------


class TestCmdGestionarVentas:
    @pytest.mark.asyncio
    async def test_sin_ventas_reply_y_end(self) -> None:
        # Entry now shows the filter screen regardless of ventas — END only after
        # the user selects a filter and the list is empty. Here we just check that
        # the entry returns GV_FILTRO and shows the filter keyboard.
        update = _make_update()
        ctx = _make_context(ventas=[])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_FILTRO

        assert result == GV_FILTRO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_con_ventas_muestra_botones_y_retorna_gv_seleccionar(self) -> None:
        # Entry now shows the filter screen, not the venta list directly.
        ventas = [_make_venta(), _make_venta()]
        update = _make_update()
        ctx = _make_context(ventas=ventas)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_FILTRO

        assert result == GV_FILTRO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_admin_no_propietario_devuelve_end(self) -> None:
        no_admin = MagicMock()
        no_admin.es_admin = False
        update = _make_update(user_id=999)
        ctx = _make_context(freelancer=no_admin)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == ConversationHandler.END
        # repo must NOT have been called because auth denied early
        ctx.bot_data["venta_repo"].listar_para_gestion.assert_not_called()
        ctx.bot_data["venta_repo"].listar_por_periodo.assert_not_called()


# ---------------------------------------------------------------------------
# Button label — vendedor / cerrador / fecha / monto
# ---------------------------------------------------------------------------


def _extract_buttons(update: MagicMock) -> list:  # type: ignore[type-arg]
    """Flatten the InlineKeyboardMarkup rows from the reply_text call."""
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    return [btn for row in markup.inline_keyboard for btn in row]


def _extract_buttons_from_edit(update: MagicMock) -> list:  # type: ignore[type-arg]
    """Flatten the InlineKeyboardMarkup rows from the edit_message_text call."""
    markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    return [btn for row in markup.inline_keyboard for btn in row]


class TestCmdGestionarVentasBotonLabel:
    @pytest.mark.asyncio
    async def test_boton_incluye_vendedor_cerrador_fecha_y_monto(self) -> None:
        # Entry now shows the filter screen; venta buttons appear after filter selection.
        # This test now verifies the filter keyboard is shown at entry.
        venta = _make_venta(
            fecha=datetime.date(2026, 8, 15),
            valor_monto=750_000,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        update = _make_update()
        ctx = _make_context(ventas=[venta])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            await cmd_gestionar_ventas(update, ctx)

        buttons = _extract_buttons(update)
        callback_datas = [b.callback_data for b in buttons]
        # Filter screen shown at entry — at least the 4 filter + 1 cancel buttons
        assert "gv_f_7d" in callback_datas
        assert "gv_f_mes" in callback_datas
        assert "gv_f_mes_ant" in callback_datas
        assert "gv_f_rango" in callback_datas

    @pytest.mark.asyncio
    async def test_boton_sin_participantes_usa_guion(self) -> None:
        """A venta with no vendedor/cerrador snapshot must fall back to '—'.
        Now checked via the _construir_teclado_ventas helper directly.
        """
        from garay.infraestructura.telegram.handlers_gestion_ventas import _construir_teclado_ventas

        venta = _make_venta(vendedor_nombre=None, cerrador_nombre=None)
        markup = _construir_teclado_ventas([venta])
        # First button is the venta; last row has Atrás/Cancelar
        (button,) = markup.inline_keyboard[0]
        assert "—" in button.text


# ---------------------------------------------------------------------------
# Item D: list by REGISTRATION recency (últimos 2 días), not tour date
# ---------------------------------------------------------------------------


class TestCmdGestionarVentasPorRegistro:
    @pytest.mark.asyncio
    async def test_usa_listar_para_gestion_con_ventana_de_2_dias(self) -> None:
        """Entry point now shows the filter screen; repo is called after filter selection.
        After choosing gv_f_7d, the repo is called with hoy - 7 days.
        """
        from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_filtro

        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context(ventas=[_make_venta()])

        await handle_gv_filtro(update, ctx)

        venta_repo = ctx.bot_data["venta_repo"]
        esperado_desde = datetime.date.today() - datetime.timedelta(days=7)
        venta_repo.listar_para_gestion.assert_called_once_with(esperado_desde)
        venta_repo.listar_por_periodo.assert_not_called()

    @pytest.mark.asyncio
    async def test_teclado_preserva_el_orden_del_repo(self) -> None:
        """Keyboard must keep the repo's registration-recency order, not re-sort by tour fecha.

        After filter selection, the button order must match the incoming list order.
        The last row (Atrás/Cancelar) is excluded from the order check.
        """
        from garay.infraestructura.telegram.handlers_gestion_ventas import _construir_teclado_ventas

        primera = _make_venta(fecha=datetime.date(2026, 1, 1), vendedor_nombre="Primera")
        segunda = _make_venta(fecha=datetime.date(2026, 12, 31), vendedor_nombre="Segunda")
        markup = _construir_teclado_ventas([primera, segunda])
        # First two rows are ventas; last row is Atrás/Cancelar
        buttons = [markup.inline_keyboard[0][0], markup.inline_keyboard[1][0]]
        assert "Primera" in buttons[0].text
        assert "Segunda" in buttons[1].text


# ---------------------------------------------------------------------------
# handle_gv_seleccionar
# ---------------------------------------------------------------------------


class TestHandleGvSeleccionar:
    @pytest.mark.asyncio
    async def test_seleccionar_venta_valida_retorna_gv_detalle(self) -> None:
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_seleccionar(update, ctx)

        assert result == GV_DETALLE
        assert ctx.user_data["gv_venta_id"] == str(venta.id)

    @pytest.mark.asyncio
    async def test_seleccionar_venta_no_encontrada_retorna_end(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data=f"gv_sel:{venta_id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = None

        result = await handle_gv_seleccionar(update, ctx)

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# #4: seleccionar edits the list message (hides list) + Atrás button
# ---------------------------------------------------------------------------


class TestHandleGvSeleccionarHidesList:
    @pytest.mark.asyncio
    async def test_seleccionar_edita_mensaje_en_vez_de_reply(self) -> None:
        """Selecting a venta must EDIT the list message (hide list), not send a new one."""
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_seleccionar(update, ctx)

        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_detalle_incluye_boton_atras(self) -> None:
        """The detail keyboard must include an Atrás button (callback gv_atras)."""
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_seleccionar(update, ctx)

        callbacks = [b.callback_data for b in _extract_buttons_from_edit(update)]
        assert "gv_atras" in callbacks


class TestGvDetallePatternCoversKeyboard:
    def test_todos_los_callbacks_del_detalle_matchean_el_patron(self) -> None:
        """Every detail-keyboard callback_data must be routed by GV_DETALLE_PATTERN.

        Regression guard: the Atrás button (gv_atras) once shipped unrouted because
        the pattern did not cover it.
        """
        import re

        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_DETALLE_PATTERN,
            _construir_teclado_detalle,
        )

        markup = _construir_teclado_detalle()
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]

        assert "gv_atras" in callbacks  # the button that regressed
        for cb in callbacks:
            assert re.match(GV_DETALLE_PATTERN, str(cb)), f"{cb} no matchea el patrón"


class TestHandleGvAtras:
    @pytest.mark.asyncio
    async def test_atras_vuelve_a_gv_seleccionar(self) -> None:
        """Pressing Atrás must rebuild the list and return to GV_SELECCIONAR."""
        ventas = [_make_venta(), _make_venta()]
        update = _make_update(callback_data="gv_atras")
        ctx = _make_context(ventas=ventas)

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_SELECCIONAR

    @pytest.mark.asyncio
    async def test_atras_muestra_lista_de_ventas(self) -> None:
        """Atrás must edit the message back to the ventas list (gv_sel buttons).

        The list now also includes gv_atras and gv_cancelar navigation buttons at the end.
        """
        ventas = [_make_venta(), _make_venta()]
        update = _make_update(callback_data="gv_atras")
        ctx = _make_context(ventas=ventas)

        await handle_gv_detalle(update, ctx)

        callbacks = [b.callback_data for b in _extract_buttons_from_edit(update)]
        # Venta buttons + navigation buttons (gv_atras + gv_cancelar)
        venta_callbacks = [cb for cb in callbacks if cb.startswith("gv_sel:")]
        assert len(venta_callbacks) == 2
        assert "gv_atras" in callbacks
        assert "gv_cancelar" in callbacks


# ---------------------------------------------------------------------------
# handle_gv_detalle
# ---------------------------------------------------------------------------


class TestHandleGvDetalle:
    @pytest.mark.asyncio
    async def test_gv_anular_retorna_gv_motivo(self) -> None:
        update = _make_update(callback_data="gv_anular")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_MOTIVO

    @pytest.mark.asyncio
    async def test_gv_anular_edita_mensaje_en_lugar_sin_dejar_botones(self) -> None:
        """Anular must EDIT the detail message in place (drop its buttons), not leave them."""
        update = _make_update(callback_data="gv_anular")
        ctx = _make_context()

        await handle_gv_detalle(update, ctx)

        # The detail message is edited (buttons gone), no new reply_text with the old keyboard.
        update.callback_query.edit_message_text.assert_called_once()
        update.effective_message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_gv_cancelar_retorna_end(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# handle_gv_motivo
# ---------------------------------------------------------------------------


class TestHandleGvMotivo:
    @pytest.mark.asyncio
    async def test_motivo_vacio_stays_en_gv_motivo(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_MOTIVO

    @pytest.mark.asyncio
    async def test_motivo_vacio_reply_error(self) -> None:
        update = _make_update(text="")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_MOTIVO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_motivo_valido_guarda_y_retorna_gv_confirmar(self) -> None:
        update = _make_update(text="Cliente cambio de planes")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_CONFIRMAR
        assert ctx.user_data["gv_motivo"] == "Cliente cambio de planes"

    @pytest.mark.asyncio
    async def test_motivo_editar_branch_retorna_gv_confirmar_con_confirmar_editar(self) -> None:
        """FIX 2: editar branch must return GV_CONFIRMAR and reply with confirmar_editar text."""
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        nueva_fecha = datetime.datetime(2026, 9, 20, 10, 30)
        update = _make_update(text="Pasajero cambio de disponibilidad")
        ctx = _make_context()
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha.isoformat()
        ctx.user_data["gv_venta_id"] = str(venta_id)

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_CONFIRMAR
        expected_text = obtener_mensaje("gestion_ventas.confirmar_editar").format(
            fecha=f"{nueva_fecha:%d/%m/%Y %H:%M}",
            motivo="Pasajero cambio de disponibilidad",
        )
        update.effective_message.reply_text.assert_called_once_with(
            expected_text,
            reply_markup=update.effective_message.reply_text.call_args[1]["reply_markup"],
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# handle_gv_confirmar
# ---------------------------------------------------------------------------


class TestHandleGvConfirmar:
    @pytest.mark.asyncio
    async def test_cancelar_retorna_end(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancelar_limpia_user_data(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = "some-id"
        ctx.user_data["gv_motivo"] = "some-motivo"

        await handle_gv_confirmar(update, ctx)

        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_llama_servicio_y_retorna_end(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"
        ctx.user_data["gv_accion"] = "anular"

        from garay.aplicacion.ventas.comandos import AnularVentaComando

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        service = ctx.bot_data["anular_venta_service"]
        service.ejecutar.assert_called_once()
        cmd: AnularVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.motivo == "Motivo de prueba"
        assert cmd.realizada_por_telegram_id == 123

    @pytest.mark.asyncio
    async def test_confirmar_exitoso_limpia_user_data(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"
        ctx.user_data["gv_accion"] = "anular"

        await handle_gv_confirmar(update, ctx)

        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_venta_ya_anulada_reply_error_y_end(self) -> None:
        from garay.dominio.ventas.errores import VentaYaAnulada

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = VentaYaAnulada("ya anulada")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_venta_no_encontrada_reply_error_y_end(self) -> None:
        from garay.dominio.ventas.errores import VentaNoEncontrada

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = VentaNoEncontrada("no")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_generic_exception_reply_error_generico_y_end(self) -> None:
        """FIX 3: a generic RuntimeError must reply error_generico and return END."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = RuntimeError("DB exploded")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()


class TestAnularDmSocios:
    """K — cancellation must DM socios and admins, not only the group."""

    @pytest.mark.asyncio
    async def test_anular_exitoso_dm_a_socio_con_telegram_id(self) -> None:
        venta_id = uuid.uuid4()
        socio = MagicMock()
        socio.telegram_id = 7777

        ctx = _make_context()
        ctx.bot_data["socios_config_repo"] = MagicMock(listar=MagicMock(return_value=[socio]))
        venta = MagicMock()
        venta.mensaje_grupo_id = None
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Viaje cancelado"
        ctx.user_data["gv_accion"] = "anular"

        update = _make_update(callback_data="gv_confirmar")
        await handle_gv_confirmar(update, ctx)

        chat_ids = [
            c.kwargs.get("chat_id") or (c.args[0] if c.args else None)
            for c in ctx.bot.send_message.call_args_list
        ]
        assert 7777 in chat_ids

    @pytest.mark.asyncio
    async def test_anular_exitoso_no_dm_a_socio_sin_telegram_id(self) -> None:
        venta_id = uuid.uuid4()
        socio = MagicMock()
        socio.telegram_id = None

        ctx = _make_context()
        ctx.bot_data["socios_config_repo"] = MagicMock(listar=MagicMock(return_value=[socio]))
        venta = MagicMock()
        venta.mensaje_grupo_id = None
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Sin telegram"
        ctx.user_data["gv_accion"] = "anular"

        update = _make_update(callback_data="gv_confirmar")
        await handle_gv_confirmar(update, ctx)

        chat_ids = [
            c.kwargs.get("chat_id") or (c.args[0] if c.args else None)
            for c in ctx.bot.send_message.call_args_list
        ]
        assert None not in chat_ids


class TestCmdGestionarVentasClearsStaleKeys:
    @pytest.mark.asyncio
    async def test_entry_clears_stale_gv_keys(self) -> None:
        """FIX 2: cmd_gestionar_ventas must pop stale gv_* keys before listing ventas."""
        ventas = [_make_venta()]
        update = _make_update()
        ctx = _make_context(ventas=ventas)
        # Pre-seed stale keys from a previous conversation run.
        ctx.user_data["gv_venta_id"] = "old-id"
        ctx.user_data["gv_motivo"] = "old-motivo"

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            await cmd_gestionar_ventas(update, ctx)

        # Keys must be absent regardless of conversation outcome.
        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data


# ---------------------------------------------------------------------------
# B3: handle_gv_detalle — gv_editar branch
# ---------------------------------------------------------------------------


class TestHandleGvDetalleEditar:
    @pytest.mark.asyncio
    async def test_gv_editar_muestra_submenu_de_campos(self) -> None:
        """gv_editar swaps only the keyboard (detail text stays) and returns GV_EDIT_CAMPO."""
        venta = _make_venta()
        update = _make_update(callback_data="gv_editar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_EDIT_CAMPO
        # edit_message_reply_markup is used (not edit_message_text) to keep detail visible
        markup = update.callback_query.edit_message_reply_markup.call_args.kwargs[
            "reply_markup"
        ]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "gv_campo:fecha" in callbacks
        assert "gv_campo:telefono" in callbacks
        assert "gv_volver_detalle" in callbacks

    @pytest.mark.asyncio
    async def test_gv_anular_sets_accion_anular(self) -> None:
        """Regression: gv_anular still goes to GV_MOTIVO and sets gv_accion='anular'."""
        update = _make_update(callback_data="gv_anular")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_accion") == "anular"


# ---------------------------------------------------------------------------
# B3: handle_gv_edit_fecha
# ---------------------------------------------------------------------------


class TestHandleGvEditFecha:
    @pytest.mark.asyncio
    async def test_fecha_invalida_stays_gv_edit_fecha(self) -> None:
        """Non-parseable text must reply fecha_invalida and stay in GV_EDIT_FECHA."""
        update = _make_update(text="no es una fecha")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_EDIT_FECHA
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_fecha_invalida_formato_incorrecto(self) -> None:
        """Triangulation: another bad format also stays in GV_EDIT_FECHA."""
        update = _make_update(text="2026-09-20")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_EDIT_FECHA

    @pytest.mark.asyncio
    async def test_fecha_valida_guarda_y_retorna_gv_motivo(self) -> None:
        """Valid date text must store gv_nueva_fecha (ISO) and return GV_MOTIVO."""
        update = _make_update(text="20/09/2026 10:30")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_MOTIVO
        assert "gv_nueva_fecha" in ctx.user_data

    @pytest.mark.asyncio
    async def test_fecha_valida_sin_hora_retorna_gv_motivo(self) -> None:
        """Triangulation: DD/MM/YYYY (no time) must also advance to GV_MOTIVO."""
        update = _make_update(text="20/09/2026")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_MOTIVO
        assert "gv_nueva_fecha" in ctx.user_data

    @pytest.mark.asyncio
    async def test_fecha_valida_iso_stored_correctly(self) -> None:
        """The stored gv_nueva_fecha must be parseable back to datetime."""
        update = _make_update(text="20/09/2026 14:00")
        ctx = _make_context()

        await handle_gv_edit_fecha(update, ctx)

        stored = ctx.user_data.get("gv_nueva_fecha")
        assert stored is not None
        parsed = datetime.datetime.fromisoformat(stored)
        assert parsed.year == 2026
        assert parsed.month == 9
        assert parsed.day == 20

    @pytest.mark.asyncio
    async def test_fecha_valida_reply_usa_pedir_motivo_editar(self) -> None:
        """FIX 1: valid fecha must reply with pedir_motivo_editar text, not pedir_motivo."""
        from garay.mensajes.catalogo import obtener_mensaje

        update = _make_update(text="20/09/2026")
        ctx = _make_context()

        await handle_gv_edit_fecha(update, ctx)

        expected_text = obtener_mensaje("gestion_ventas.pedir_motivo_editar")
        update.effective_message.reply_text.assert_called_once_with(
            expected_text,
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# B3: handle_gv_confirmar — editar branch
# ---------------------------------------------------------------------------


class TestHandleGvConfirmarEditar:
    @pytest.mark.asyncio
    async def test_confirmar_editar_llama_servicio_y_retorna_end(self) -> None:
        """Confirm edit: editar_fecha_venta_service.ejecutar called with correct command."""
        from garay.aplicacion.ventas.comandos import EditarFechaVentaComando

        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cambio de plan"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        service = ctx.bot_data["editar_fecha_venta_service"]
        service.ejecutar.assert_called_once()
        cmd: EditarFechaVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.nueva_fecha == datetime.datetime.fromisoformat(nueva_fecha_str)
        assert cmd.motivo == "Cambio de plan"
        assert cmd.realizada_por_telegram_id == 123

    @pytest.mark.asyncio
    async def test_confirmar_editar_limpia_user_data(self) -> None:
        """After successful edit confirm, all gv_* keys must be cleaned up."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cambio de plan"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"

        await handle_gv_confirmar(update, ctx)

        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data
        assert "gv_nueva_fecha" not in ctx.user_data
        assert "gv_accion" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_editar_venta_ya_anulada_reply_error_y_end(self) -> None:
        """TOCTOU: if venta was anulada after selection, must reply ya_anulada + END."""
        from garay.dominio.ventas.errores import VentaYaAnulada

        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.bot_data["editar_fecha_venta_service"].ejecutar.side_effect = VentaYaAnulada("ya")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_editar_limite_ediciones_reply_y_end(self) -> None:
        """If the service raises LimiteEdicionesAlcanzado, reply limite_ediciones + END."""
        from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.bot_data["editar_fecha_venta_service"].ejecutar.side_effect = (
            LimiteEdicionesAlcanzado("tope alcanzado")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.limite_ediciones") in calls

    @pytest.mark.asyncio
    async def test_confirmar_anular_path_regression(self) -> None:
        """Regression: anular path still works when gv_accion='anular'."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"
        ctx.user_data["gv_accion"] = "anular"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["anular_venta_service"].ejecutar.assert_called_once()


# ---------------------------------------------------------------------------
# B3: _limpiar clears gv_accion and gv_nueva_fecha
# ---------------------------------------------------------------------------


class TestLimpiarClearsB3Keys:
    @pytest.mark.asyncio
    async def test_limpiar_clears_gv_accion_and_gv_nueva_fecha(self) -> None:
        """_limpiar must pop gv_accion and gv_nueva_fecha (B3 keys)."""
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_nueva_fecha"] = "2026-09-20T10:30:00"
        ctx.user_data["gv_venta_id"] = "some-id"
        ctx.user_data["gv_motivo"] = "some-motivo"

        await handle_gv_confirmar(update, ctx)

        assert "gv_accion" not in ctx.user_data
        assert "gv_nueva_fecha" not in ctx.user_data


# ---------------------------------------------------------------------------
# C2: handle_gv_seleccionar — stash cliente/tour names
# ---------------------------------------------------------------------------


class TestHandleGvSeleccionarStashNames:
    @pytest.mark.asyncio
    async def test_seleccionar_stashes_cliente_nombre(self) -> None:
        """handle_gv_seleccionar must store gv_cliente_nombre in user_data."""
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_seleccionar(update, ctx)

        assert ctx.user_data.get("gv_cliente_nombre") == "Juan Perez"

    @pytest.mark.asyncio
    async def test_seleccionar_stashes_tours_str(self) -> None:
        """handle_gv_seleccionar must store gv_tours in user_data."""
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_seleccionar(update, ctx)

        assert ctx.user_data.get("gv_tours") == "Tour Isla"

    @pytest.mark.asyncio
    async def test_limpiar_clears_gv_cliente_nombre_and_gv_tours(self) -> None:
        """_limpiar (via cancelar) must pop gv_cliente_nombre and gv_tours."""
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        ctx.user_data["gv_venta_id"] = "some-id"
        ctx.user_data["gv_motivo"] = "some-motivo"

        await handle_gv_confirmar(update, ctx)

        assert "gv_cliente_nombre" not in ctx.user_data
        assert "gv_tours" not in ctx.user_data


# ---------------------------------------------------------------------------
# C2: group notification on anular
# ---------------------------------------------------------------------------


class TestNotificarGrupoAnular:
    @pytest.mark.asyncio
    async def test_anular_success_calls_notificador_once(self) -> None:
        """On successful anular, group notification must be sent (via bot.send_message)."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cliente cancelo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        # Notification now goes via bot.send_message (delete-and-replace path).
        group_calls = [
            c for c in ctx.bot.send_message.call_args_list
            if (c.kwargs.get("chat_id") or (c.args[0] if c.args else None)) == "-1001234567"
        ]
        assert len(group_calls) >= 1

    @pytest.mark.asyncio
    async def test_anular_notificador_message_contains_cliente_tour_motivo(self) -> None:
        """Notification message must include cliente, tour, and motivo."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cliente cancelo el viaje"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        await handle_gv_confirmar(update, ctx)

        group_calls = [
            c for c in ctx.bot.send_message.call_args_list
            if (c.kwargs.get("chat_id") or (c.args[0] if c.args else None)) == "-1001234567"
        ]
        assert group_calls, "expected at least one send_message to the group"
        mensaje_arg: str = group_calls[0].kwargs.get("text") or group_calls[0].args[1]

        assert "Juan Perez" in mensaje_arg
        assert "Tour Isla" in mensaje_arg
        assert "Cliente cancelo el viaje" in mensaje_arg

    @pytest.mark.asyncio
    async def test_anular_notificador_escapes_html_in_dynamic_values(self) -> None:
        """Dynamic values must be HTML-escaped so Telegram HTML mode never breaks."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Se fue con Juan & Pedro <urgente>"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "O'Hara & Sons"
        ctx.user_data["gv_tours"] = "Tour Isla"

        await handle_gv_confirmar(update, ctx)

        group_calls = [
            c for c in ctx.bot.send_message.call_args_list
            if (c.kwargs.get("chat_id") or (c.args[0] if c.args else None)) == "-1001234567"
        ]
        assert group_calls, "expected at least one send_message to the group"
        mensaje_arg: str = group_calls[0].kwargs.get("text") or group_calls[0].args[1]

        assert "&amp;" in mensaje_arg
        assert "&lt;urgente&gt;" in mensaje_arg
        # Raw unescaped angle brackets from user input must not leak through.
        assert "<urgente>" not in mensaje_arg

    @pytest.mark.asyncio
    async def test_anular_notificador_raises_flow_still_ends(self) -> None:
        """Notification failure must NOT break the anular flow — still returns END + reply."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        ctx.bot_data["notificador"].notificar.side_effect = RuntimeError("Telegram down")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_anular_notificador_absent_from_bot_data_no_crash(self) -> None:
        """If notificador is missing from bot_data, anular still succeeds."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        del ctx.bot_data["notificador"]

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_anular_still_replies_anulada_message(self) -> None:
        """Even with notification, user still receives the anulada reply."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo test"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        from garay.mensajes.catalogo import obtener_mensaje
        await handle_gv_confirmar(update, ctx)

        expected = obtener_mensaje("gestion_ventas.anulada")
        # First reply is the confirmation; cerrar_flujo then adds the submenu.
        assert update.effective_message.reply_text.call_args_list[0].args[0] == expected


# ---------------------------------------------------------------------------
# C2: group notification on editar fecha
# ---------------------------------------------------------------------------


class TestNotificarGrupoEditar:
    @pytest.mark.asyncio
    async def test_editar_success_calls_notificador_once(self) -> None:
        """On successful editar, group notification must be sent via bot.send_message."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Pasajero cambio disponibilidad"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        # Notification now goes through _notificar_edicion → bot.send_message.
        ctx.bot.send_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_editar_notificador_message_contains_cliente_tour_fecha_motivo(self) -> None:
        """Notification message must include cliente, tour, new fecha, and motivo."""
        venta_id = uuid.uuid4()
        nueva_fecha = datetime.datetime(2026, 9, 20, 10, 30)
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cambio de plan del pasajero"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha.isoformat()
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            await handle_gv_confirmar(update, ctx)

        # Notification now goes via bot.send_message; verify message content.
        ctx.bot.send_message.assert_awaited()
        call_kwargs = ctx.bot.send_message.await_args
        assert call_kwargs is not None
        # Extract the text argument (first positional or keyword).
        text_arg: str = (
            call_kwargs.kwargs.get("text") or
            (call_kwargs.args[1] if len(call_kwargs.args) > 1 else "")
        )
        chat_id_arg = call_kwargs.kwargs.get("chat_id") or (
            call_kwargs.args[0] if call_kwargs.args else ""
        )
        assert "Juan Perez" in text_arg
        assert "Tour Isla" in text_arg
        assert "20/09/2026" in text_arg
        assert "Cambio de plan del pasajero" in text_arg
        assert chat_id_arg == "-1001234567"

    @pytest.mark.asyncio
    async def test_editar_notificador_raises_flow_still_ends(self) -> None:
        """Notification failure must NOT break the editar flow."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        ctx.bot_data["notificador"].notificar.side_effect = RuntimeError("Network error")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_editar_notificador_absent_from_bot_data_no_crash(self) -> None:
        """If notificador is missing from bot_data, editar still succeeds."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        del ctx.bot_data["notificador"]

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_editar_still_replies_editada_message(self) -> None:
        """Even with notification, user still receives the editada reply."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo test"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        from garay.mensajes.catalogo import obtener_mensaje
        await handle_gv_confirmar(update, ctx)

        expected = obtener_mensaje("gestion_ventas.editada")
        # First reply is the confirmation; cerrar_flujo then adds the submenu.
        assert update.effective_message.reply_text.call_args_list[0].args[0] == expected


# ---------------------------------------------------------------------------
# C3: regenerar factura after editar fecha
# ---------------------------------------------------------------------------


def _editar_ctx(venta_id: uuid.UUID | None = None) -> MagicMock:
    """Return a context pre-wired for a successful editar flow including C3 keys."""
    from garay.aplicacion.factura.regenerar_factura import ResultadoRegenerarFactura

    ctx = _make_context()
    regenerar_mock = MagicMock()
    regenerar_mock.ejecutar.return_value = ResultadoRegenerarFactura.REENVIADA
    ctx.bot_data["regenerar_factura_service"] = regenerar_mock
    _vid = venta_id or uuid.uuid4()
    ctx.user_data["gv_venta_id"] = str(_vid)
    ctx.user_data["gv_motivo"] = "Cambio de plan"
    ctx.user_data["gv_nueva_fecha"] = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
    ctx.user_data["gv_accion"] = "editar"
    ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
    ctx.user_data["gv_tours"] = "Tour Isla"
    return ctx


class TestRegenerarFacturaTrasEditar:
    @pytest.mark.asyncio
    async def test_editar_calls_regenerar_service_with_venta_id(self) -> None:
        """On successful editar, regenerar_factura_service.ejecutar must be called with venta_id."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _editar_ctx(venta_id=venta_id)

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        svc = ctx.bot_data["regenerar_factura_service"]
        svc.ejecutar.assert_called_once_with(venta_id)

    @pytest.mark.asyncio
    async def test_reenviada_reply_includes_factura_reenviada(self) -> None:
        """When resultado is REENVIADA, reply factura_reenviada in addition to editada."""
        from garay.aplicacion.factura.regenerar_factura import ResultadoRegenerarFactura
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _editar_ctx(venta_id=venta_id)
        ctx.bot_data["regenerar_factura_service"].ejecutar.return_value = (
            ResultadoRegenerarFactura.REENVIADA
        )

        await handle_gv_confirmar(update, ctx)

        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.editada") in calls
        assert obtener_mensaje("gestion_ventas.factura_reenviada") in calls

    @pytest.mark.asyncio
    async def test_error_envio_reply_includes_factura_error(self) -> None:
        """When resultado is ERROR_ENVIO, reply factura_error message."""
        from garay.aplicacion.factura.regenerar_factura import ResultadoRegenerarFactura
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _editar_ctx(venta_id=venta_id)
        ctx.bot_data["regenerar_factura_service"].ejecutar.return_value = (
            ResultadoRegenerarFactura.ERROR_ENVIO
        )

        await handle_gv_confirmar(update, ctx)

        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.editada") in calls
        assert obtener_mensaje("gestion_ventas.factura_error") in calls

    @pytest.mark.asyncio
    async def test_sin_factura_no_extra_reply(self) -> None:
        """SIN_FACTURA result must not add any extra reply beyond editada."""
        from garay.aplicacion.factura.regenerar_factura import ResultadoRegenerarFactura
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _editar_ctx(venta_id=venta_id)
        ctx.bot_data["regenerar_factura_service"].ejecutar.return_value = (
            ResultadoRegenerarFactura.SIN_FACTURA
        )

        await handle_gv_confirmar(update, ctx)

        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.editada") in calls
        assert obtener_mensaje("gestion_ventas.factura_reenviada") not in calls
        assert obtener_mensaje("gestion_ventas.factura_error") not in calls

    @pytest.mark.asyncio
    async def test_regenerar_raises_flow_continues_and_editada_sent(self) -> None:
        """If regenerar_service.ejecutar raises, the exception must be swallowed and
        the user still receives the editada confirmation."""
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _editar_ctx(venta_id=venta_id)
        ctx.bot_data["regenerar_factura_service"].ejecutar.side_effect = RuntimeError(
            "DB error"
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.editada") in calls

    @pytest.mark.asyncio
    async def test_regenerar_absent_from_bot_data_no_crash(self) -> None:
        """If regenerar_factura_service is not in bot_data, flow still completes."""
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _editar_ctx(venta_id=venta_id)
        del ctx.bot_data["regenerar_factura_service"]

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.editada") in calls


# ---------------------------------------------------------------------------
# Slice 3: field submenu + client-field edit flow
# ---------------------------------------------------------------------------


class TestGvEditCampoPatternCoversKeyboard:
    def test_todos_los_callbacks_del_submenu_matchean_el_patron(self) -> None:
        import re

        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_CAMPO_PATTERN,
            _construir_teclado_campos,
        )

        markup = _construir_teclado_campos()
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "gv_campo:fecha" in callbacks
        assert "gv_volver_detalle" in callbacks
        for cb in callbacks:
            assert re.match(GV_EDIT_CAMPO_PATTERN, str(cb)), f"{cb} no matchea"


class TestHandleGvEditCampo:
    @pytest.mark.asyncio
    async def test_campo_fecha_muestra_fecha_actual(self) -> None:
        venta = _make_venta(fecha=datetime.date(2026, 8, 15))
        update = _make_update(callback_data="gv_campo:fecha")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_edit_campo(update, ctx)

        assert result == GV_EDIT_FECHA
        assert ctx.user_data.get("gv_accion") == "editar"
        prompt = update.callback_query.edit_message_text.call_args.args[0]
        assert "15/08/2026" in prompt

    @pytest.mark.asyncio
    async def test_campo_cliente_muestra_valor_actual(self) -> None:
        venta = _make_venta()
        update = _make_update(callback_data="gv_campo:telefono")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        cliente = MagicMock()
        cliente.telefono = "3001112233"
        ctx.bot_data["cliente_repo"].buscar_por_id.return_value = cliente

        result = await handle_gv_edit_campo(update, ctx)

        assert result == GV_EDIT_VALOR
        assert ctx.user_data.get("gv_accion") == "editar_cliente"
        assert ctx.user_data.get("gv_campo") == "telefono"
        assert ctx.user_data.get("gv_valor_anterior") == "3001112233"
        prompt = update.callback_query.edit_message_text.call_args.args[0]
        assert "3001112233" in prompt

    @pytest.mark.asyncio
    async def test_campo_cliente_sin_valor_muestra_placeholder(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje

        venta = _make_venta()
        update = _make_update(callback_data="gv_campo:hotel")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        cliente = MagicMock()
        cliente.hotel = None
        ctx.bot_data["cliente_repo"].buscar_por_id.return_value = cliente

        await handle_gv_edit_campo(update, ctx)

        assert ctx.user_data.get("gv_valor_anterior") == obtener_mensaje(
            "gestion_ventas.sin_dato"
        )

    @pytest.mark.asyncio
    async def test_volver_detalle_regresa_a_gv_detalle(self) -> None:
        venta = _make_venta()
        update = _make_update(callback_data="gv_volver_detalle")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_edit_campo(update, ctx)

        assert result == GV_DETALLE


class TestHandleGvEditValor:
    @pytest.mark.asyncio
    async def test_valor_vacio_stays(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_gv_edit_valor(update, ctx)

        assert result == GV_EDIT_VALOR

    @pytest.mark.asyncio
    async def test_valor_valido_guarda_y_va_a_gv_motivo(self) -> None:
        update = _make_update(text="3009998877")
        ctx = _make_context()

        result = await handle_gv_edit_valor(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_nuevo_valor") == "3009998877"


class TestGvMotivoConfirmEditarCliente:
    @pytest.mark.asyncio
    async def test_confirmacion_muestra_antes_y_despues(self) -> None:
        update = _make_update(text="Cliente pidió corrección")
        ctx = _make_context()
        ctx.user_data["gv_accion"] = "editar_cliente"
        ctx.user_data["gv_campo"] = "telefono"
        ctx.user_data["gv_valor_anterior"] = "3001112233"
        ctx.user_data["gv_nuevo_valor"] = "3009998877"

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_CONFIRMAR
        confirm_text = update.effective_message.reply_text.call_args.args[0]
        assert "3001112233" in confirm_text  # antes
        assert "3009998877" in confirm_text  # después


class TestHandleGvConfirmarEditarCliente:
    @pytest.mark.asyncio
    async def test_confirmar_editar_cliente_llama_servicio(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarClienteVentaComando
        from garay.dominio.clientes.entidades import CampoCliente

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_cliente"
        ctx.user_data["gv_campo"] = "telefono"
        ctx.user_data["gv_nuevo_valor"] = "3009998877"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        service = ctx.bot_data["editar_cliente_venta_service"]
        service.ejecutar.assert_called_once()
        cmd: EditarClienteVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.campo == CampoCliente.TELEFONO
        assert cmd.nuevo_valor == "3009998877"
        assert cmd.motivo == "Corrección"

    @pytest.mark.asyncio
    async def test_confirmar_editar_cliente_reply_cliente_editado(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_cliente"
        ctx.user_data["gv_campo"] = "email"
        ctx.user_data["gv_nuevo_valor"] = "a@b.com"

        await handle_gv_confirmar(update, ctx)

        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.cliente_editado") in calls

    @pytest.mark.asyncio
    async def test_confirmar_editar_cliente_limite_reply_limite(self) -> None:
        from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_cliente"
        ctx.user_data["gv_campo"] = "telefono"
        ctx.user_data["gv_nuevo_valor"] = "300"
        ctx.bot_data["editar_cliente_venta_service"].ejecutar.side_effect = (
            LimiteEdicionesAlcanzado("tope")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.limite_ediciones") in calls


# ---------------------------------------------------------------------------
# Task-15 RED: GV_EDIT_CANAL_TIPO, GV_EDIT_CANAL_PUNTO constants and routing
# ---------------------------------------------------------------------------


class TestEditarCanalConstants:
    """GV_EDIT_CANAL_TIPO = 229 and GV_EDIT_CANAL_PUNTO = 230 must exist."""

    def test_gv_edit_canal_tipo_constant(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_CANAL_TIPO

        assert GV_EDIT_CANAL_TIPO == 229

    def test_gv_edit_canal_punto_constant(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_CANAL_PUNTO

        assert GV_EDIT_CANAL_PUNTO == 230


class TestTecladoCamposIncludeCanal:
    """_construir_teclado_campos must include canal button with gv_campo:tipo_cliente."""

    def test_teclado_campos_has_canal_button(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import _construir_teclado_campos

        markup = _construir_teclado_campos()
        all_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "gv_campo:tipo_cliente" in all_data


class TestRoutingGvCampoTipoCliente:
    """handle_gv_edit_campo routing: gv_campo:tipo_cliente sets gv_accion=editar_canal."""

    @pytest.mark.asyncio
    async def test_tipo_cliente_sets_accion_editar_canal(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_CANAL_TIPO,
            handle_gv_edit_campo,
        )

        venta = _make_venta()
        update = _make_update(callback_data="gv_campo:tipo_cliente")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_edit_campo(update, ctx)

        assert result == GV_EDIT_CANAL_TIPO
        assert ctx.user_data.get("gv_accion") == "editar_canal"

    @pytest.mark.asyncio
    async def test_tipo_cliente_shows_canal_keyboard(self) -> None:
        """When routing to editar_canal, a keyboard with canal type options is shown."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_edit_campo,
        )

        venta = _make_venta()
        update = _make_update(callback_data="gv_campo:tipo_cliente")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_edit_campo(update, ctx)

        update.callback_query.edit_message_text.assert_called_once()


# ---------------------------------------------------------------------------
# Task-17 RED: handle_gv_edit_canal_tipo and handle_gv_edit_canal_punto
# ---------------------------------------------------------------------------


def _make_context_canal(
    ventas: list[MagicMock] | None = None,
) -> MagicMock:
    """Context with pdv_repo (puntos de venta) wired for canal tests."""
    ctx = _make_context(ventas=ventas)
    # puntos stored as "pdv_repo" in bot_data
    punto1 = MagicMock()
    punto1.id = uuid.uuid4()
    punto1.nombre = "Punto A"
    punto2 = MagicMock()
    punto2.id = uuid.uuid4()
    punto2.nombre = "Crespo"
    pdv_repo = MagicMock()
    pdv_repo.listar.return_value = [punto1, punto2]
    ctx.bot_data["pdv_repo"] = pdv_repo
    editar_canal_service = MagicMock()
    ctx.bot_data["editar_canal_venta_service"] = editar_canal_service
    return ctx


class TestHandleGvEditCanalTipo:
    """handle_gv_edit_canal_tipo state handler."""

    @pytest.mark.asyncio
    async def test_interno_stores_tipo_and_returns_canal_punto(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_CANAL_PUNTO,
            handle_gv_edit_canal_tipo,
        )

        update = _make_update(callback_data="gv_canal:INTERNO")
        ctx = _make_context_canal()

        result = await handle_gv_edit_canal_tipo(update, ctx)

        assert result == GV_EDIT_CANAL_PUNTO
        assert ctx.user_data.get("gv_nuevo_tipo") == "INTERNO"

    @pytest.mark.asyncio
    async def test_interno_shows_punto_selector(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_edit_canal_tipo,
        )

        update = _make_update(callback_data="gv_canal:INTERNO")
        ctx = _make_context_canal()

        await handle_gv_edit_canal_tipo(update, ctx)

        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_externo_clears_punto_prompts_motivo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_MOTIVO,
            handle_gv_edit_canal_tipo,
        )

        update = _make_update(callback_data="gv_canal:EXTERNO")
        ctx = _make_context_canal()
        ctx.user_data["gv_punto_id"] = str(uuid.uuid4())  # pre-existing, must be cleared

        result = await handle_gv_edit_canal_tipo(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_punto_id") is None

    @pytest.mark.asyncio
    async def test_digital_clears_punto_returns_motivo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_MOTIVO,
            handle_gv_edit_canal_tipo,
        )

        update = _make_update(callback_data="gv_canal:DIGITAL")
        ctx = _make_context_canal()

        result = await handle_gv_edit_canal_tipo(update, ctx)

        assert result == GV_MOTIVO


class TestHandleGvEditCanalPunto:
    """handle_gv_edit_canal_punto state handler."""

    @pytest.mark.asyncio
    async def test_stores_punto_id_returns_motivo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_MOTIVO,
            handle_gv_edit_canal_punto,
        )

        pid = uuid.uuid4()
        update = _make_update(callback_data=f"gv_punto:{pid}")
        ctx = _make_context_canal()

        result = await handle_gv_edit_canal_punto(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_punto_id") == str(pid)

    @pytest.mark.asyncio
    async def test_prompts_motivo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_edit_canal_punto,
        )

        pid = uuid.uuid4()
        update = _make_update(callback_data=f"gv_punto:{pid}")
        ctx = _make_context_canal()

        await handle_gv_edit_canal_punto(update, ctx)

        update.effective_message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Task-19 RED: _handle_confirmar_editar_canal dispatch and exception mapping
# ---------------------------------------------------------------------------


class TestHandleGvConfirmarEditarCanal:
    """handle_gv_confirmar with gv_accion="editar_canal"."""

    @pytest.mark.asyncio
    async def test_dispatches_to_editar_canal(self) -> None:
        """With gv_accion=editar_canal, the service must be called."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "EXTERNO"
        ctx.user_data["gv_punto_id"] = None

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["editar_canal_venta_service"].ejecutar.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_shows_canal_editado(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "DIGITAL"
        ctx.user_data["gv_punto_id"] = None

        await handle_gv_confirmar(update, ctx)

        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.canal_editado") in calls

    @pytest.mark.asyncio
    async def test_success_calls_notificar_grupo(self) -> None:
        """On success, group notification is sent via bot.send_message (delete+send)."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "DIGITAL"
        ctx.user_data["gv_punto_id"] = None

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            await handle_gv_confirmar(update, ctx)

        # Notification now goes via _notificar_edicion → bot.send_message.
        ctx.bot.send_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_mismo_canal_shows_canal_igual(self) -> None:
        from garay.dominio.ventas.errores import MismoCanal
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "EXTERNO"
        ctx.user_data["gv_punto_id"] = None
        ctx.bot_data["editar_canal_venta_service"].ejecutar.side_effect = MismoCanal("mismo")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert any("canal" in str(c).lower() or "ya es" in str(c) for c in calls) or any(
            obtener_mensaje("gestion_ventas.canal_igual").format(canal="EXTERNO") in str(c)
            or "canal" in str(c).lower()
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_punto_requerido_shows_message(self) -> None:
        from garay.dominio.ventas.errores import PuntoDeVentaRequerido
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "INTERNO"
        ctx.user_data["gv_punto_id"] = None
        ctx.bot_data["editar_canal_venta_service"].ejecutar.side_effect = (
            PuntoDeVentaRequerido("requerido")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        expected = obtener_mensaje("gestion_ventas.punto_requerido")
        assert expected in calls

    @pytest.mark.asyncio
    async def test_venta_ya_anulada_shows_ya_anulada(self) -> None:
        from garay.dominio.ventas.errores import VentaYaAnulada
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "DIGITAL"
        ctx.user_data["gv_punto_id"] = None
        ctx.bot_data["editar_canal_venta_service"].ejecutar.side_effect = (
            VentaYaAnulada("anulada")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.ya_anulada") in calls

    @pytest.mark.asyncio
    async def test_limite_ediciones_shows_limite(self) -> None:
        from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "DIGITAL"
        ctx.user_data["gv_punto_id"] = None
        ctx.bot_data["editar_canal_venta_service"].ejecutar.side_effect = (
            LimiteEdicionesAlcanzado("limite")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.limite_ediciones") in calls

    @pytest.mark.asyncio
    async def test_venta_no_encontrada_shows_no_encontrada(self) -> None:
        from garay.dominio.ventas.errores import VentaNoEncontrada
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "DIGITAL"
        ctx.user_data["gv_punto_id"] = None
        ctx.bot_data["editar_canal_venta_service"].ejecutar.side_effect = (
            VentaNoEncontrada("no found")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.no_encontrada") in calls

    @pytest.mark.asyncio
    async def test_motivo_requerido_shows_motivo_vacio(self) -> None:
        from garay.dominio.ventas.errores import MotivoRequerido
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_canal()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_canal"
        ctx.user_data["gv_nuevo_tipo"] = "DIGITAL"
        ctx.user_data["gv_punto_id"] = None
        ctx.bot_data["editar_canal_venta_service"].ejecutar.side_effect = (
            MotivoRequerido("vacio")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.motivo_vacio") in calls


# ---------------------------------------------------------------------------
# Editar participantes (vendedor/cerrador) — handler tests
# ---------------------------------------------------------------------------


def _make_context_participantes(
    ventas: list[MagicMock] | None = None,
) -> MagicMock:
    ctx = _make_context(ventas=ventas)
    editar_participantes_service = MagicMock()
    ctx.bot_data["editar_participantes_venta_service"] = editar_participantes_service

    fl1 = MagicMock()
    fl1.id = uuid.uuid4()
    fl1.nombre = "Pedro"
    fl2 = MagicMock()
    fl2.id = uuid.uuid4()
    fl2.nombre = "Carlos"
    freelancer_repo = MagicMock()
    freelancer_repo.listar_activos.return_value = [fl1, fl2]
    freelancer_repo.buscar_por_id.return_value = fl1
    freelancer_repo.buscar_por_telegram_id.return_value = _make_admin_freelancer()
    ctx.bot_data["freelancer_repo"] = freelancer_repo
    return ctx


class TestEditarParticipantesConstant:
    """GV_EDIT_PARTICIPANTE = 231 must exist."""

    def test_gv_edit_participante_constant(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_PARTICIPANTE

        assert GV_EDIT_PARTICIPANTE == 231


class TestTecladoCamposWithVendedor:
    """_construir_teclado_campos(venta) shows vendedor/cerrador when non-null."""

    def test_teclado_sin_venta_no_tiene_vendedor(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import _construir_teclado_campos

        markup = _construir_teclado_campos(None)
        all_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "gv_campo:vendedor" not in all_data
        assert "gv_campo:cerrador" not in all_data

    def test_teclado_con_venta_vendedor_nonnull_tiene_boton(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import _construir_teclado_campos

        venta = _make_venta(vendedor_nombre="Ana", cerrador_nombre=None)
        venta.participantes.vendedor_nombre = "Ana"
        venta.participantes.cerrador_nombre = None

        markup = _construir_teclado_campos(venta)
        all_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "gv_campo:vendedor" in all_data
        assert "gv_campo:cerrador" not in all_data

    def test_teclado_con_venta_cerrador_nonnull_tiene_boton(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import _construir_teclado_campos

        venta = _make_venta(vendedor_nombre=None, cerrador_nombre="Luis")
        venta.participantes.vendedor_nombre = None
        venta.participantes.cerrador_nombre = "Luis"

        markup = _construir_teclado_campos(venta)
        all_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "gv_campo:vendedor" not in all_data
        assert "gv_campo:cerrador" in all_data


class TestRoutingGvCampoVendedor:
    """handle_gv_edit_campo routing: gv_campo:vendedor → GV_EDIT_PARTICIPANTE."""

    @pytest.mark.asyncio
    async def test_vendedor_sets_accion_editar_vendedor(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_PARTICIPANTE,
            handle_gv_edit_campo,
        )

        venta = _make_venta(vendedor_nombre="Ana", cerrador_nombre="Luis")
        venta.participantes.vendedor_nombre = "Ana"
        venta.participantes.cerrador_nombre = "Luis"

        update = _make_update(callback_data="gv_campo:vendedor")
        ctx = _make_context_participantes()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_edit_campo(update, ctx)

        assert result == GV_EDIT_PARTICIPANTE
        assert ctx.user_data.get("gv_accion") == "editar_vendedor"

    @pytest.mark.asyncio
    async def test_cerrador_sets_accion_editar_cerrador(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_PARTICIPANTE,
            handle_gv_edit_campo,
        )

        venta = _make_venta(vendedor_nombre="Ana", cerrador_nombre="Luis")
        venta.participantes.vendedor_nombre = "Ana"
        venta.participantes.cerrador_nombre = "Luis"

        update = _make_update(callback_data="gv_campo:cerrador")
        ctx = _make_context_participantes()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_edit_campo(update, ctx)

        assert result == GV_EDIT_PARTICIPANTE
        assert ctx.user_data.get("gv_accion") == "editar_cerrador"


class TestHandleGvEditParticipante:
    """handle_gv_edit_participante state handler."""

    @pytest.mark.asyncio
    async def test_volver_detalle_returns_edit_campo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_CAMPO,
            handle_gv_edit_participante,
        )

        venta = _make_venta()
        update = _make_update(callback_data="gv_volver_detalle")
        ctx = _make_context_participantes()
        ctx.user_data["gv_venta_id"] = str(venta.id)
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_edit_participante(update, ctx)

        assert result == GV_EDIT_CAMPO

    @pytest.mark.asyncio
    async def test_freelancer_selected_stores_data_and_prompts_motivo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_MOTIVO,
            handle_gv_edit_participante,
        )

        fl_id = uuid.uuid4()
        fl = MagicMock()
        fl.id = fl_id
        fl.nombre = "Pedro"

        update = _make_update(callback_data=f"gv_freelancer:{fl_id}")
        ctx = _make_context_participantes()
        ctx.bot_data["freelancer_repo"].buscar_por_id.return_value = fl
        ctx.user_data["gv_venta_id"] = str(uuid.uuid4())

        result = await handle_gv_edit_participante(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_nuevo_freelancer_id") == str(fl_id)
        assert ctx.user_data.get("gv_nuevo_freelancer_nombre") == "Pedro"
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_end(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_edit_participante,
        )

        update = _make_update(callback_data="gv_freelancer:not-a-uuid")
        ctx = _make_context_participantes()

        result = await handle_gv_edit_participante(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_freelancer_not_found_returns_end(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_edit_participante,
        )

        fl_id = uuid.uuid4()
        update = _make_update(callback_data=f"gv_freelancer:{fl_id}")
        ctx = _make_context_participantes()
        ctx.bot_data["freelancer_repo"].buscar_por_id.return_value = None

        result = await handle_gv_edit_participante(update, ctx)

        assert result == ConversationHandler.END


class TestHandleGvConfirmarEditarParticipante:
    """handle_gv_confirmar with gv_accion="editar_vendedor" / "editar_cerrador"."""

    @pytest.mark.asyncio
    async def test_dispatches_editar_vendedor_calls_service(self) -> None:
        venta = _make_venta()
        venta.participantes.vendedor_id = uuid.uuid4()
        venta.participantes.vendedor_nombre = "Ana"
        venta.participantes.cerrador_id = uuid.uuid4()
        venta.participantes.cerrador_nombre = "Luis"

        nuevo_fl_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_participantes()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        ctx.user_data["gv_venta_id"] = str(uuid.uuid4())
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_vendedor"
        ctx.user_data["gv_nuevo_freelancer_id"] = str(nuevo_fl_id)
        ctx.user_data["gv_nuevo_freelancer_nombre"] = "Pedro"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["editar_participantes_venta_service"].ejecutar.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_shows_participante_editado(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje

        venta = _make_venta()
        venta.participantes.vendedor_id = uuid.uuid4()
        venta.participantes.vendedor_nombre = "Ana"
        venta.participantes.cerrador_id = uuid.uuid4()
        venta.participantes.cerrador_nombre = "Luis"

        nuevo_fl_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_participantes()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        ctx.user_data["gv_venta_id"] = str(uuid.uuid4())
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_cerrador"
        ctx.user_data["gv_nuevo_freelancer_id"] = str(nuevo_fl_id)
        ctx.user_data["gv_nuevo_freelancer_nombre"] = "Carlos"

        await handle_gv_confirmar(update, ctx)

        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.participante_editado") in calls

    @pytest.mark.asyncio
    async def test_mismos_participantes_shows_mismo_participante(self) -> None:
        from garay.dominio.ventas.errores import MismosParticipantes
        from garay.mensajes.catalogo import obtener_mensaje

        venta = _make_venta()
        venta.participantes.vendedor_id = uuid.uuid4()
        nuevo_fl_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_participantes()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        ctx.user_data["gv_venta_id"] = str(uuid.uuid4())
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_vendedor"
        ctx.user_data["gv_nuevo_freelancer_id"] = str(nuevo_fl_id)
        ctx.user_data["gv_nuevo_freelancer_nombre"] = "Pedro"
        ctx.bot_data["editar_participantes_venta_service"].ejecutar.side_effect = (
            MismosParticipantes("mismos")
        )

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        calls = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert obtener_mensaje("gestion_ventas.mismo_participante") in calls

    @pytest.mark.asyncio
    async def test_success_calls_notificar_grupo(self) -> None:
        """On success, notification is sent via bot.send_message (delete+send)."""
        venta = _make_venta()
        venta.participantes.vendedor_id = uuid.uuid4()
        venta.participantes.vendedor_nombre = "Ana"
        venta.participantes.cerrador_id = uuid.uuid4()
        venta.participantes.cerrador_nombre = "Luis"

        nuevo_fl_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context_participantes()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        ctx.user_data["gv_venta_id"] = str(uuid.uuid4())
        ctx.user_data["gv_motivo"] = "Corrección"
        ctx.user_data["gv_accion"] = "editar_vendedor"
        ctx.user_data["gv_nuevo_freelancer_id"] = str(nuevo_fl_id)
        ctx.user_data["gv_nuevo_freelancer_nombre"] = "Pedro"

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            await handle_gv_confirmar(update, ctx)

        # Notification now goes via _notificar_edicion → bot.send_message.
        ctx.bot.send_message.assert_awaited()
