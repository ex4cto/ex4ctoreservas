"""Tests for /gestionar_ventas editar-tour flow (FASE 5 + 6).

TDD: these tests are written BEFORE the implementation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CallbackQueryHandler, ConversationHandler, MessageHandler

from garay.dominio.comun.dinero import Dinero

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_servicio(
    servicio_id: uuid.UUID | None = None,
    nombre: str = "Tour Isla",
    categoria: str = "Islas",
    precio_neto_adulto: Decimal | None = Decimal("50000"),
) -> MagicMock:
    s = MagicMock()
    s.id = servicio_id or uuid.uuid4()
    s.nombre = nombre
    s.categoria = categoria
    s.activo = True
    s.precio_neto_adulto = precio_neto_adulto
    s.precio_neto_nino = None
    s.neto_para_horario.return_value = precio_neto_adulto
    return s


def _make_venta(
    servicio_id: uuid.UUID | None = None,
    num_servicios: int = 1,
) -> MagicMock:
    import datetime

    v = MagicMock()
    v.id = uuid.uuid4()
    v.cliente_id = uuid.uuid4()

    sid = servicio_id or uuid.uuid4()
    if num_servicios == 1:
        v.servicio_ids = [sid]
    else:
        v.servicio_ids = [uuid.uuid4() for _ in range(num_servicios)]

    v.fecha = datetime.date(2026, 8, 1)
    v.valor_venta = Dinero(Decimal("600000"), "COP")
    v.neto = Dinero(Decimal("400000"), "COP")
    v.ganancia = Dinero(Decimal("200000"), "COP")
    v.abono = None
    v.adultos = 2
    v.ninos = 0
    v.horarios_por_servicio = {sid: "08:00"}
    v.mensaje_grupo_id = None

    from garay.dominio.comun.tipos import TipoCliente

    v.tipo_cliente = TipoCliente.EXTERNO
    v.canal_origen = None
    v.metodo_pago = None
    v.registrado_en = None
    v.participantes = MagicMock()
    v.participantes.vendedor_nombre = "Ana"
    v.participantes.cerrador_nombre = "Luis"
    v.participantes.punto_de_venta_id = None
    return v


def _make_update(callback_data: str | None = None, text: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.callback_query.from_user = MagicMock()
        update.callback_query.from_user.id = 123
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
    venta: MagicMock | None = None,
    servicios: list[MagicMock] | None = None,
    user_data: dict | None = None,  # type: ignore[type-arg]
    editar_servicio_svc: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    ctx.bot.delete_message = AsyncMock()

    _venta = venta or _make_venta()

    venta_repo = MagicMock()
    venta_repo.buscar_por_id.return_value = _venta

    servicio_repo = MagicMock()
    _servicios = servicios if servicios is not None else [_make_servicio()]
    servicio_repo.listar_activos.return_value = _servicios
    servicio_repo.buscar_por_id.side_effect = lambda sid: next(
        (s for s in _servicios if s.id == sid), None
    )

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = MagicMock(nombre="Admin")

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = []

    comision_registrada_repo = MagicMock()
    comision_registrada_repo.buscar_por_venta_id.return_value = None

    ctx.bot_data = {
        "venta_repo": venta_repo,
        "servicio_repo": servicio_repo,
        "freelancer_repo": freelancer_repo,
        "socios_config_repo": socios_config_repo,
        "comision_registrada_repo": comision_registrada_repo,
        "grupo_id": "-1001234567",
        "notificador": MagicMock(),
        "editar_servicio_svc": editar_servicio_svc or MagicMock(),
    }
    return ctx


# ---------------------------------------------------------------------------
# FASE 5.3: Tour button appears in _construir_teclado_campos
# ---------------------------------------------------------------------------


class TestCampoTourButton:
    def test_campo_tour_button_present_when_admin(self) -> None:
        """Admin keyboard must include a 'tour' campo button."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _construir_teclado_campos,
        )

        venta = _make_venta()
        markup = _construir_teclado_campos(venta, es_admin=True)
        callback_datas = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "gv_campo:tour" in callback_datas, (
            f"gv_campo:tour not found in {callback_datas}"
        )

    def test_campo_tour_button_not_present_when_not_admin(self) -> None:
        """Non-admin keyboard must NOT include the tour campo button."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _construir_teclado_campos,
        )

        venta = _make_venta()
        markup = _construir_teclado_campos(venta, es_admin=False)
        callback_datas = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "gv_campo:tour" not in callback_datas


# ---------------------------------------------------------------------------
# FASE 5.5: handle_gv_iniciar_edicion_tour — multiples guard
# ---------------------------------------------------------------------------


class TestIniciarEdicionTour:
    @pytest.mark.asyncio
    async def test_tour_multiples_blocked(self) -> None:
        """Venta with 2 servicio_ids must show tour_multiples and return GV_DETALLE."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_DETALLE,
            handle_gv_iniciar_edicion_tour,
        )

        venta = _make_venta(num_servicios=2)
        ctx = _make_context(venta=venta)
        ctx.user_data["gv_venta_id"] = str(venta.id)
        update = _make_update(callback_data="gv_campo:tour")

        result = await handle_gv_iniciar_edicion_tour(update, ctx)

        assert result == GV_DETALLE
        update.callback_query.edit_message_text.assert_called_once()
        call_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "múltiples" in call_text or "multiple" in call_text.lower()

    @pytest.mark.asyncio
    async def test_single_tour_shows_familia_picker(self) -> None:
        """Venta with 1 tour must show family selection keyboard."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_FAMILIA,
            handle_gv_iniciar_edicion_tour,
        )

        s1 = _make_servicio(nombre="Tour Isla", categoria="Islas")
        s2 = _make_servicio(nombre="Tour Ciudad", categoria="Ciudad")
        venta = _make_venta()
        ctx = _make_context(venta=venta, servicios=[s1, s2])
        ctx.user_data["gv_venta_id"] = str(venta.id)
        update = _make_update(callback_data="gv_campo:tour")

        result = await handle_gv_iniciar_edicion_tour(update, ctx)

        assert result == GV_EDIT_FAMILIA
        update.callback_query.edit_message_text.assert_called_once()
        # familia_tour data stored
        assert "gv_familias_tour" in ctx.user_data


# ---------------------------------------------------------------------------
# FASE 5.6: handle_gv_edit_familia — shows tours in a family
# ---------------------------------------------------------------------------


class TestHandleGvEditFamilia:
    @pytest.mark.asyncio
    async def test_handle_gv_edit_familia_shows_tours(self) -> None:
        """Selecting a family must show the tours in that family."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_SERVICIO,
            handle_gv_edit_familia,
        )

        s1 = _make_servicio(nombre="Tour Isla", categoria="Islas")
        s2 = _make_servicio(nombre="Tour Mar", categoria="Islas")
        ctx = _make_context(servicios=[s1, s2])
        ctx.user_data["gv_familias_tour"] = {"Islas": [s1, s2]}
        update = _make_update(callback_data="gv_familia_Islas")

        result = await handle_gv_edit_familia(update, ctx)

        assert result == GV_EDIT_SERVICIO
        update.callback_query.edit_message_text.assert_called_once()
        # family was stored
        assert ctx.user_data.get("gv_familia_seleccionada") == "Islas"


# ---------------------------------------------------------------------------
# FASE 5.7: handle_gv_edit_servicio — same tour guard
# ---------------------------------------------------------------------------


class TestHandleGvEditServicio:
    @pytest.mark.asyncio
    async def test_mismo_tour_guard(self) -> None:
        """Selecting the same tour must show mismo_tour message and return GV_DETALLE."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_DETALLE,
            handle_gv_edit_servicio,
        )

        sid = uuid.uuid4()
        venta = _make_venta(servicio_id=sid)
        ctx = _make_context(venta=venta)
        ctx.user_data["gv_venta_id"] = str(venta.id)
        update = _make_update(callback_data=f"gv_tour_{sid}")

        result = await handle_gv_edit_servicio(update, ctx)

        assert result == GV_DETALLE
        update.callback_query.edit_message_text.assert_called_once()
        call_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "ya es ese" in call_text or "mismo" in call_text.lower()

    @pytest.mark.asyncio
    async def test_tour_sin_precio_guard(self) -> None:
        """calcular_neto_tour returning None must show tour_sin_precio."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_SERVICIO,
            handle_gv_edit_servicio,
        )

        sid_actual = uuid.uuid4()
        sid_nuevo = uuid.uuid4()
        venta = _make_venta(servicio_id=sid_actual)
        venta.horarios_por_servicio = {sid_actual: None}

        servicio_sin_precio = _make_servicio(
            servicio_id=sid_nuevo, nombre="Tour Sin Precio", precio_neto_adulto=None
        )
        servicio_sin_precio.neto_para_horario.return_value = None

        ctx = _make_context(venta=venta, servicios=[servicio_sin_precio])
        ctx.user_data["gv_venta_id"] = str(venta.id)
        # Clear the side_effect so return_value is used instead.
        ctx.bot_data["servicio_repo"].buscar_por_id.side_effect = None
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = servicio_sin_precio
        update = _make_update(callback_data=f"gv_tour_{sid_nuevo}")

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.calcular_neto_tour",
            return_value=None,
        ):
            result = await handle_gv_edit_servicio(update, ctx)

        assert result == GV_EDIT_SERVICIO
        update.callback_query.edit_message_text.assert_called_once()
        call_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "precio" in call_text.lower() or "sin precio" in call_text.lower()

    @pytest.mark.asyncio
    async def test_valid_tour_stores_data_and_asks_valor_venta(self) -> None:
        """Selecting a different tour with price must store data and return GV_EDIT_TOUR_VALOR."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_TOUR_VALOR,
            handle_gv_edit_servicio,
        )

        sid_actual = uuid.uuid4()
        sid_nuevo = uuid.uuid4()
        venta = _make_venta(servicio_id=sid_actual)
        nuevo_servicio = _make_servicio(servicio_id=sid_nuevo, nombre="Tour Playas")

        ctx = _make_context(venta=venta)
        ctx.user_data["gv_venta_id"] = str(venta.id)
        # Clear the side_effect so return_value is used instead.
        ctx.bot_data["servicio_repo"].buscar_por_id.side_effect = None
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = nuevo_servicio
        update = _make_update(callback_data=f"gv_tour_{sid_nuevo}")

        neto_calculado = Dinero(Decimal("100000"), "COP")
        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.calcular_neto_tour",
            return_value=neto_calculado,
        ):
            result = await handle_gv_edit_servicio(update, ctx)

        assert result == GV_EDIT_TOUR_VALOR
        assert ctx.user_data.get("gv_nuevo_servicio_id") == sid_nuevo
        assert ctx.user_data.get("gv_nuevo_servicio_nombre") == "Tour Playas"
        assert ctx.user_data.get("gv_nuevo_neto") == neto_calculado


# ---------------------------------------------------------------------------
# FASE 5.8: handle_gv_edit_tour_valor — valor_venta change paths
# ---------------------------------------------------------------------------


class TestHandleGvEditTourValor:
    @pytest.mark.asyncio
    async def test_no_callback_goes_to_motivo(self) -> None:
        """Tapping 'No' must go directly to motivo."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_MOTIVO,
            handle_gv_edit_tour_valor,
        )

        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(uuid.uuid4())
        update = _make_update(callback_data="gv_tour_valor_no")

        result = await handle_gv_edit_tour_valor(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_cambiar_valor_venta") is False
        assert ctx.user_data.get("gv_nuevo_valor_venta") is None

    @pytest.mark.asyncio
    async def test_si_callback_asks_for_new_valor_venta(self) -> None:
        """Tapping 'Sí' must ask for the new valor_venta and stay in GV_EDIT_TOUR_VALOR."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_TOUR_VALOR,
            handle_gv_edit_tour_valor,
        )

        ctx = _make_context()
        update = _make_update(callback_data="gv_tour_valor_si")

        result = await handle_gv_edit_tour_valor(update, ctx)

        assert result == GV_EDIT_TOUR_VALOR
        assert ctx.user_data.get("gv_cambiar_valor_venta") is True

    @pytest.mark.asyncio
    async def test_invalid_monto_stays_in_state(self) -> None:
        """Typing invalid amount must re-show error and stay in GV_EDIT_TOUR_VALOR."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_TOUR_VALOR,
            handle_gv_edit_tour_valor,
        )

        ctx = _make_context()
        ctx.user_data["gv_cambiar_valor_venta"] = True
        update = _make_update(text="not_a_number")

        result = await handle_gv_edit_tour_valor(update, ctx)

        assert result == GV_EDIT_TOUR_VALOR

    @pytest.mark.asyncio
    async def test_valid_monto_text_goes_to_motivo(self) -> None:
        """Typing valid amount must store it and go to motivo."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_MOTIVO,
            handle_gv_edit_tour_valor,
        )

        ctx = _make_context()
        ctx.user_data["gv_cambiar_valor_venta"] = True
        update = _make_update(text="750000")

        result = await handle_gv_edit_tour_valor(update, ctx)

        assert result == GV_MOTIVO
        stored = ctx.user_data.get("gv_nuevo_valor_venta")
        assert stored is not None
        assert stored.monto == Decimal("750000")


# ---------------------------------------------------------------------------
# FASE 5.10: _handle_confirmar_editar_servicio — calls service correctly
# ---------------------------------------------------------------------------


class TestHandleConfirmarEditarServicio:
    @pytest.mark.asyncio
    async def test_confirmar_editar_servicio_calls_service(self) -> None:
        """Confirming tour edit must call editar_servicio_svc.ejecutar with correct args."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_confirmar,
        )

        venta_id = uuid.uuid4()
        nuevo_sid = uuid.uuid4()
        svc_mock = MagicMock()

        ctx = _make_context(editar_servicio_svc=svc_mock)
        ctx.user_data.update(
            {
                "gv_accion": "editar_tour",
                "gv_venta_id": str(venta_id),
                "gv_motivo": "Test motivo",
                "gv_nuevo_servicio_id": nuevo_sid,
                "gv_nuevo_servicio_nombre": "Tour Nuevo",
                "gv_nuevo_neto": Dinero(Decimal("100000"), "COP"),
                "gv_nuevo_valor_venta": None,
                "gv_cambiar_valor_venta": False,
            }
        )
        update = _make_update(callback_data="gv_confirmar")

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            result = await handle_gv_confirmar(update, ctx)

        svc_mock.ejecutar.assert_called_once()
        cmd = svc_mock.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.nuevo_servicio_id == nuevo_sid
        assert cmd.motivo == "Test motivo"
        assert cmd.nuevo_valor_venta is None
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirmar_editar_servicio_error_propagation(self) -> None:
        """LimiteEdicionesAlcanzado must show limite_ediciones message."""
        from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            handle_gv_confirmar,
        )

        venta_id = uuid.uuid4()
        nuevo_sid = uuid.uuid4()
        svc_mock = MagicMock()
        svc_mock.ejecutar.side_effect = LimiteEdicionesAlcanzado("limite")

        ctx = _make_context(editar_servicio_svc=svc_mock)
        ctx.user_data.update(
            {
                "gv_accion": "editar_tour",
                "gv_venta_id": str(venta_id),
                "gv_motivo": "Test motivo",
                "gv_nuevo_servicio_id": nuevo_sid,
                "gv_nuevo_servicio_nombre": "Tour Nuevo",
                "gv_nuevo_neto": Dinero(Decimal("100000"), "COP"),
                "gv_nuevo_valor_venta": None,
                "gv_cambiar_valor_venta": False,
            }
        )
        update = _make_update(callback_data="gv_confirmar")

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            await handle_gv_confirmar(update, ctx)

        update.effective_message.reply_text.assert_called()
        # First call is the error message; subsequent calls may be the cerrar_flujo menu.
        all_calls = update.effective_message.reply_text.call_args_list
        first_call_text = all_calls[0][0][0]
        # The message key is "gestion_ventas.limite_ediciones" → contains "ediciones"
        assert "ediciones" in first_call_text.lower() or "máximo" in first_call_text.lower()


# ---------------------------------------------------------------------------
# FASE 6: Wiring tests — new states registered in ConversationHandler
# ---------------------------------------------------------------------------


def _build_gv_handler() -> ConversationHandler:  # type: ignore[type-arg]
    """Build the gestionar_ventas ConversationHandler from crear_aplicacion."""
    with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
        settings = MagicMock()
        settings.propietario_telegram_ids = ""
        settings.dev_telegram_ids = ""
        mock_settings.return_value = settings
        from garay.infraestructura.telegram.bot import crear_aplicacion

        app = crear_aplicacion("fake:token")

    from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_NETO

    for handler_group in app.handlers.values():
        for handler in handler_group:
            if isinstance(handler, ConversationHandler) and GV_EDIT_NETO in handler.states:
                return handler
    raise AssertionError("gestionar_ventas ConversationHandler not found")


class TestGvEditTourWiring:
    def test_gv_edit_familia_state_registered(self) -> None:
        """GV_EDIT_FAMILIA (234) must be registered in the gv ConversationHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_FAMILIA

        conv = _build_gv_handler()
        assert GV_EDIT_FAMILIA in conv.states, (
            f"GV_EDIT_FAMILIA={GV_EDIT_FAMILIA} not in states"
        )

    def test_gv_edit_servicio_state_registered(self) -> None:
        """GV_EDIT_SERVICIO (235) must be registered in the gv ConversationHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_SERVICIO

        conv = _build_gv_handler()
        assert GV_EDIT_SERVICIO in conv.states, (
            f"GV_EDIT_SERVICIO={GV_EDIT_SERVICIO} not in states"
        )

    def test_gv_edit_tour_valor_state_registered(self) -> None:
        """GV_EDIT_TOUR_VALOR (236) must be registered in the gv ConversationHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_TOUR_VALOR

        conv = _build_gv_handler()
        assert GV_EDIT_TOUR_VALOR in conv.states, (
            f"GV_EDIT_TOUR_VALOR={GV_EDIT_TOUR_VALOR} not in states"
        )

    def test_gv_edit_familia_has_callback_handler(self) -> None:
        """GV_EDIT_FAMILIA state must contain a CallbackQueryHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_FAMILIA

        conv = _build_gv_handler()
        handlers = conv.states[GV_EDIT_FAMILIA]
        assert any(isinstance(h, CallbackQueryHandler) for h in handlers)

    def test_gv_edit_tour_valor_has_both_callback_and_message_handler(self) -> None:
        """GV_EDIT_TOUR_VALOR state must contain both CallbackQueryHandler and MessageHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_TOUR_VALOR

        conv = _build_gv_handler()
        handlers = conv.states[GV_EDIT_TOUR_VALOR]
        assert any(isinstance(h, CallbackQueryHandler) for h in handlers)
        assert any(isinstance(h, MessageHandler) for h in handlers)
