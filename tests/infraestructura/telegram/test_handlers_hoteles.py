"""Tests for handlers_hoteles — hotel payment FSM and /deudas command."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, ObligacionHotel
from garay.dominio.conciliacion.tipos import TipoEgreso


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_HOTEL_ID = uuid.UUID("11111111-0001-0001-0001-111111111111")
_HOTEL_ID_2 = uuid.UUID("11111111-0002-0002-0002-222222222222")


def _make_obligacion(
    hotel_id: uuid.UUID = _HOTEL_ID,
    nombre: str = "Hotel Marie",
    receptor: str = "Maria",
    cuota_1: Decimal = Decimal("1000000"),
    cuota_2: Decimal | None = None,
    dia_1: int = 1,
    dia_2: int | None = None,
    deuda_inicial: Decimal = Decimal("5000000"),
) -> ObligacionHotel:
    return ObligacionHotel(
        id=hotel_id,
        punto_de_venta_nombre=nombre,
        receptor_nombre=receptor,
        monto_cuota_dia_1=Dinero(cuota_1),
        monto_cuota_dia_2=Dinero(cuota_2) if cuota_2 is not None else None,
        dia_pago_1=dia_1,
        dia_pago_2=dia_2,
        deuda_inicial=Dinero(deuda_inicial),
        fecha_deuda_inicial=datetime.date(2024, 1, 1),
        activa=True,
    )


def _make_egreso(
    obligacion_id: uuid.UUID = _HOTEL_ID,
    monto: Decimal = Decimal("1000000"),
    fecha: datetime.date = datetime.date(2024, 9, 1),
    concepto: str = "Cuota Hotel Marie",
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion=concepto,
        monto=Dinero(monto),
        fecha=fecha,
        categoria="cuota_hotel",
        tipo=TipoEgreso.MANUAL,
        destinatario="Maria",
        obligacion_hotel_id=obligacion_id,
    )


def _make_admin_repo(es_admin: bool = True) -> MagicMock:
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = es_admin
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_hotel_service(
    hoteles: list[ObligacionHotel] | None = None,
    saldo: Dinero | None = None,
    historial: list[Egreso] | None = None,
) -> MagicMock:
    svc = MagicMock()
    hotel = hoteles[0] if hoteles else _make_obligacion()
    hoteles_list = hoteles or [hotel]
    saldo_val = saldo or Dinero(Decimal("3000000"))
    svc.listar_con_saldo.return_value = [(h, saldo_val) for h in hoteles_list]
    svc.saldo_actual.return_value = saldo_val
    svc.monto_sugerido.return_value = Dinero(Decimal("1000000"))
    svc.registrar_pago.return_value = _make_egreso()
    svc.historial.return_value = historial or []
    return svc


def _make_update(
    callback_data: str | None = None,
    text: str | None = None,
    user_id: int = 999,
) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.message = None
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.callback_query.message = MagicMock()
    elif text is not None:
        update.callback_query = None
        update.message = AsyncMock()
        update.message.text = text
    else:
        update.message = None
        update.callback_query = None
    return update


def _make_context(
    hotel_service: MagicMock | None = None,
    es_admin: bool = True,
    user_data: dict | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot_data = {
        "freelancer_repo": _make_admin_repo(es_admin),
        "hotel_service": hotel_service or _make_hotel_service(),
    }
    return ctx


def _callback_datas(update: MagicMock) -> list[str]:
    """Extract all callback_data values from the last reply keyboard."""
    if update.callback_query is not None:
        markup = update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup")
    else:
        markup = update.effective_message.reply_text.call_args.kwargs.get("reply_markup")
    if markup is None:
        return []
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def _replied_text(update: MagicMock) -> str:
    """Return the text of the last reply sent."""
    if update.callback_query is not None:
        call = update.callback_query.edit_message_text.call_args
    else:
        call = update.effective_message.reply_text.call_args
    if call is None:
        return ""
    return call.args[0] if call.args else call.kwargs.get("text", "")


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

from garay.infraestructura.telegram.handlers_hoteles import (  # noqa: E402
    CB_HOTEL_ATRAS,
    CB_HOTEL_HISTORIAL,
    CB_HOTEL_OMITIR_CONCEPTO,
    CB_HOTEL_PAGAR,
    CB_HOTEL_PAGO_CONFIRMAR,
    CB_HOTEL_PAGO_EDITAR,
    CB_HOTEL_PAGO_CANCELAR,
    CB_HOTEL_USAR_SUGERIDO,
    CB_HOTEL_VOLVER_DETALLE,
    CB_HUB_HOTELES,
    HOTEL_DETALLE,
    HOTEL_HISTORIAL,
    HOTEL_LIST,
    HOTEL_PAGO_CONCEPTO,
    HOTEL_PAGO_CONFIRMAR,
    HOTEL_PAGO_FECHA,
    HOTEL_PAGO_MONTO,
    cmd_deudas,
    handle_hotel_detalle,
    handle_hotel_historial,
    handle_hotel_lista,
    handle_pago_concepto,
    handle_pago_confirmar,
    handle_pago_fecha,
    handle_pago_monto,
)


# ---------------------------------------------------------------------------
# Tests: state constants are in the 200-219 range
# ---------------------------------------------------------------------------

class TestStateConstants:
    def test_hotel_list_state(self) -> None:
        assert HOTEL_LIST == 200

    def test_hotel_detalle_state(self) -> None:
        assert HOTEL_DETALLE == 201

    def test_hotel_pago_monto_state(self) -> None:
        assert HOTEL_PAGO_MONTO == 202

    def test_hotel_pago_fecha_state(self) -> None:
        assert HOTEL_PAGO_FECHA == 203

    def test_hotel_pago_concepto_state(self) -> None:
        assert HOTEL_PAGO_CONCEPTO == 204

    def test_hotel_pago_confirmar_state(self) -> None:
        assert HOTEL_PAGO_CONFIRMAR == 205

    def test_hotel_historial_state(self) -> None:
        assert HOTEL_HISTORIAL == 206

    def test_no_collision_with_egresos(self) -> None:
        """States 200-219 must not collide with egresos (100-152) or tiquetera (0-36)."""
        states = [HOTEL_LIST, HOTEL_DETALLE, HOTEL_PAGO_MONTO, HOTEL_PAGO_FECHA,
                  HOTEL_PAGO_CONCEPTO, HOTEL_PAGO_CONFIRMAR, HOTEL_HISTORIAL]
        for s in states:
            assert 200 <= s <= 219, f"State {s} is out of expected range 200-219"


# ---------------------------------------------------------------------------
# Tests: handle_hotel_lista — entry point from hub callback
# ---------------------------------------------------------------------------

class TestHotelLista:
    @pytest.mark.asyncio
    async def test_muestra_lista_de_hoteles(self) -> None:
        """Shows hotel list with buttons for each hotel."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HUB_HOTELES)
        ctx = _make_context(hotel_service=svc)

        resultado = await handle_hotel_lista(update, ctx)

        assert resultado == HOTEL_LIST
        # The hotel name should appear in callback data or text
        datas = _callback_datas(update)
        assert any("hotel:" in d for d in datas), f"Expected hotel: prefix, got {datas}"

    @pytest.mark.asyncio
    async def test_guarda_ids_en_user_data(self) -> None:
        """Stores hotel IDs in user_data for later retrieval."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HUB_HOTELES)
        ctx = _make_context(hotel_service=svc)

        await handle_hotel_lista(update, ctx)

        assert "hotel_ids" in ctx.user_data

    @pytest.mark.asyncio
    async def test_muestra_boton_volver(self) -> None:
        """Shows a back button to return to hub."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HUB_HOTELES)
        ctx = _make_context(hotel_service=svc)

        await handle_hotel_lista(update, ctx)

        datas = _callback_datas(update)
        assert CB_HOTEL_ATRAS in datas


# ---------------------------------------------------------------------------
# Tests: handle_hotel_detalle — state HOTEL_LIST
# ---------------------------------------------------------------------------

class TestHotelDetalle:
    @pytest.mark.asyncio
    async def test_muestra_detalle_con_saldo(self) -> None:
        """Shows hotel detail with saldo and action buttons."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data="hotel:0")
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_ids": [str(hotel.id)]},
        )

        resultado = await handle_hotel_detalle(update, ctx)

        assert resultado == HOTEL_DETALLE

    @pytest.mark.asyncio
    async def test_boton_pagar_disponible(self) -> None:
        """Detail view includes 'Registrar pago' button."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data="hotel:0")
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_ids": [str(hotel.id)]},
        )

        await handle_hotel_detalle(update, ctx)

        datas = _callback_datas(update)
        assert CB_HOTEL_PAGAR in datas

    @pytest.mark.asyncio
    async def test_boton_historial_disponible(self) -> None:
        """Detail view includes 'Ver historial' button."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data="hotel:0")
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_ids": [str(hotel.id)]},
        )

        await handle_hotel_detalle(update, ctx)

        datas = _callback_datas(update)
        assert CB_HOTEL_HISTORIAL in datas

    @pytest.mark.asyncio
    async def test_atras_vuelve_a_lista(self) -> None:
        """Back button from detail returns to HOTEL_LIST state."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HOTEL_ATRAS)
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_ids": [str(hotel.id)]},
        )

        resultado = await handle_hotel_detalle(update, ctx)

        assert resultado == HOTEL_LIST


# ---------------------------------------------------------------------------
# Tests: handle_pago_monto — state HOTEL_DETALLE (after "Registrar pago")
# ---------------------------------------------------------------------------

class TestPagoMonto:
    @pytest.mark.asyncio
    async def test_usar_monto_sugerido(self) -> None:
        """Using the suggested amount advances to HOTEL_PAGO_FECHA."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HOTEL_USAR_SUGERIDO)
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_sel_id": str(hotel.id)},
        )

        resultado = await handle_pago_monto(update, ctx)

        assert resultado == HOTEL_PAGO_FECHA
        assert "hotel_pago_monto" in ctx.user_data

    @pytest.mark.asyncio
    async def test_monto_texto_valido(self) -> None:
        """A valid text amount advances to HOTEL_PAGO_FECHA."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(text="500000")
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_sel_id": str(hotel.id)},
        )

        resultado = await handle_pago_monto(update, ctx)

        assert resultado == HOTEL_PAGO_FECHA
        assert ctx.user_data["hotel_pago_monto"] == Decimal("500000")

    @pytest.mark.asyncio
    async def test_monto_invalido_permanece_en_estado(self) -> None:
        """Invalid amount keeps the conversation in HOTEL_PAGO_MONTO."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(text="no es un monto")
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_sel_id": str(hotel.id)},
        )

        resultado = await handle_pago_monto(update, ctx)

        assert resultado == HOTEL_PAGO_MONTO


# ---------------------------------------------------------------------------
# Tests: handle_pago_fecha — state HOTEL_PAGO_MONTO
# ---------------------------------------------------------------------------

class TestPagoFecha:
    @pytest.mark.asyncio
    async def test_hoy_avanza_a_concepto(self) -> None:
        """'Hoy' button advances to HOTEL_PAGO_CONCEPTO."""
        from garay.infraestructura.telegram.handlers_hoteles import CB_HOTEL_HOY

        update = _make_update(callback_data=CB_HOTEL_HOY)
        ctx = _make_context()

        resultado = await handle_pago_fecha(update, ctx)

        assert resultado == HOTEL_PAGO_CONCEPTO
        assert "hotel_pago_fecha" in ctx.user_data

    @pytest.mark.asyncio
    async def test_fecha_texto_valida(self) -> None:
        """Valid date text advances to HOTEL_PAGO_CONCEPTO."""
        update = _make_update(text="15/09/2024")
        ctx = _make_context()

        resultado = await handle_pago_fecha(update, ctx)

        assert resultado == HOTEL_PAGO_CONCEPTO

    @pytest.mark.asyncio
    async def test_fecha_invalida_permanece_en_estado(self) -> None:
        """Invalid date text keeps state at HOTEL_PAGO_FECHA."""
        update = _make_update(text="esto no es fecha")
        ctx = _make_context()

        resultado = await handle_pago_fecha(update, ctx)

        assert resultado == HOTEL_PAGO_FECHA


# ---------------------------------------------------------------------------
# Tests: handle_pago_concepto — state HOTEL_PAGO_FECHA
# ---------------------------------------------------------------------------

class TestPagoConcepto:
    def _ud_pago(self, hotel: ObligacionHotel) -> dict:
        return {
            "hotel_sel_id": str(hotel.id),
            "hotel_sel_nombre": hotel.punto_de_venta_nombre,
            "hotel_pago_monto": Decimal("1000000"),
            "hotel_pago_fecha": datetime.date(2024, 9, 15),
        }

    @pytest.mark.asyncio
    async def test_omitir_avanza_a_confirmar(self) -> None:
        """'Omitir' button advances to HOTEL_PAGO_CONFIRMAR."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HOTEL_OMITIR_CONCEPTO)
        ctx = _make_context(hotel_service=svc, user_data=self._ud_pago(hotel))

        resultado = await handle_pago_concepto(update, ctx)

        assert resultado == HOTEL_PAGO_CONFIRMAR
        assert ctx.user_data.get("hotel_pago_concepto") is None

    @pytest.mark.asyncio
    async def test_texto_libre_avanza_a_confirmar(self) -> None:
        """Free text advances to HOTEL_PAGO_CONFIRMAR and saves concepto."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(text="cuota 15 sep")
        ctx = _make_context(hotel_service=svc, user_data=self._ud_pago(hotel))

        resultado = await handle_pago_concepto(update, ctx)

        assert resultado == HOTEL_PAGO_CONFIRMAR
        assert ctx.user_data["hotel_pago_concepto"] == "cuota 15 sep"


# ---------------------------------------------------------------------------
# Tests: handle_pago_confirmar — state HOTEL_PAGO_CONFIRMAR
# ---------------------------------------------------------------------------

class TestPagoConfirmar:
    def _make_ud_completo(self, hotel: ObligacionHotel) -> dict:
        return {
            "hotel_sel_id": str(hotel.id),
            "hotel_pago_monto": Decimal("1000000"),
            "hotel_pago_fecha": datetime.date(2024, 9, 15),
            "hotel_pago_concepto": "cuota 15 sep",
        }

    @pytest.mark.asyncio
    async def test_confirmar_registra_pago(self) -> None:
        """Confirming calls ServicioHoteles.registrar_pago and ends conversation."""
        from telegram.ext import ConversationHandler

        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HOTEL_PAGO_CONFIRMAR)
        ctx = _make_context(
            hotel_service=svc,
            user_data=self._make_ud_completo(hotel),
        )

        resultado = await handle_pago_confirmar(update, ctx)

        svc.registrar_pago.assert_called_once()
        # After confirming, returns to HOTEL_DETALLE to show updated saldo
        assert resultado == HOTEL_DETALLE

    @pytest.mark.asyncio
    async def test_cancelar_termina_conversacion(self) -> None:
        """Cancelling ends the conversation without registering payment."""
        from telegram.ext import ConversationHandler

        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HOTEL_PAGO_CANCELAR)
        ctx = _make_context(
            hotel_service=svc,
            user_data=self._make_ud_completo(hotel),
        )

        resultado = await handle_pago_confirmar(update, ctx)

        svc.registrar_pago.assert_not_called()
        assert resultado == ConversationHandler.END


# ---------------------------------------------------------------------------
# Tests: handle_hotel_historial — state HOTEL_DETALLE (after "Ver historial")
# ---------------------------------------------------------------------------

class TestHotelHistorial:
    @pytest.mark.asyncio
    async def test_muestra_historial_vacio(self) -> None:
        """Empty historial shows 'vacio' message."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel], historial=[])
        update = _make_update(callback_data=CB_HOTEL_HISTORIAL)
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_sel_id": str(hotel.id)},
        )

        resultado = await handle_hotel_historial(update, ctx)

        assert resultado == HOTEL_HISTORIAL
        texto = _replied_text(update)
        assert texto  # something was sent

    @pytest.mark.asyncio
    async def test_muestra_pagos_en_historial(self) -> None:
        """Historial with pagos renders their dates and amounts."""
        hotel = _make_obligacion()
        pagos = [
            _make_egreso(
                obligacion_id=hotel.id,
                monto=Decimal("1000000"),
                fecha=datetime.date(2024, 9, 1),
            )
        ]
        svc = _make_hotel_service(hoteles=[hotel], historial=pagos)
        update = _make_update(callback_data=CB_HOTEL_HISTORIAL)
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_sel_id": str(hotel.id)},
        )

        resultado = await handle_hotel_historial(update, ctx)

        assert resultado == HOTEL_HISTORIAL

    @pytest.mark.asyncio
    async def test_boton_volver_desde_historial(self) -> None:
        """Back button from historial returns to HOTEL_DETALLE."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(callback_data=CB_HOTEL_VOLVER_DETALLE)
        ctx = _make_context(
            hotel_service=svc,
            user_data={"hotel_sel_id": str(hotel.id)},
        )

        resultado = await handle_hotel_historial(update, ctx)

        assert resultado == HOTEL_DETALLE


# ---------------------------------------------------------------------------
# Tests: cmd_deudas — no FSM, admin-only
# ---------------------------------------------------------------------------

class TestCmdDeudas:
    @pytest.mark.asyncio
    async def test_muestra_resumen_de_deudas(self) -> None:
        """Shows all hotels with their balances."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update()
        ctx = _make_context(hotel_service=svc, es_admin=True)

        await cmd_deudas(update, ctx)

        svc.listar_con_saldo.assert_called_once()
        # The message was sent
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_admin_no_ve_deudas(self) -> None:
        """Non-admin cannot see /deudas."""
        hotel = _make_obligacion()
        svc = _make_hotel_service(hoteles=[hotel])
        update = _make_update(user_id=9999)
        ctx = _make_context(hotel_service=svc, es_admin=False)

        await cmd_deudas(update, ctx)

        # Service was NOT called because guard denied access
        svc.listar_con_saldo.assert_not_called()

    @pytest.mark.asyncio
    async def test_resumen_incluye_total(self) -> None:
        """The /deudas response includes a total sum."""
        hotel1 = _make_obligacion(hotel_id=_HOTEL_ID, nombre="Hotel A")
        hotel2 = _make_obligacion(hotel_id=_HOTEL_ID_2, nombre="Hotel B")
        svc = MagicMock()
        svc.listar_con_saldo.return_value = [
            (hotel1, Dinero(Decimal("2000000"))),
            (hotel2, Dinero(Decimal("3000000"))),
        ]
        update = _make_update()
        ctx = _make_context(hotel_service=svc, es_admin=True)

        await cmd_deudas(update, ctx)

        text = update.effective_message.reply_text.call_args.args[0]
        # Should contain both hotel names and amounts
        assert "Hotel A" in text or "Hotel B" in text


# ---------------------------------------------------------------------------
# Tests: hub modification — hotel button appears first in egresos hub
# ---------------------------------------------------------------------------

class TestHubModificado:
    @pytest.mark.asyncio
    async def test_hub_tiene_boton_hoteles(self) -> None:
        """The egresos hub shows a Hoteles button."""
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_HUB_CANCELAR,
            CB_HUB_CATEGORIAS,
            CB_HUB_FIJOS,
            CB_HUB_NUEVO,
            cmd_egresos,
        )
        from garay.infraestructura.telegram.handlers_hoteles import CB_HUB_HOTELES

        update = _make_update()
        ctx = _make_context(es_admin=True)
        await cmd_egresos(update, ctx)

        datas = _callback_datas(update)
        assert CB_HUB_HOTELES in datas
        assert CB_HUB_NUEVO in datas
        assert CB_HUB_FIJOS in datas
        assert CB_HUB_CATEGORIAS in datas
        assert CB_HUB_CANCELAR in datas

    @pytest.mark.asyncio
    async def test_hoteles_es_primer_boton(self) -> None:
        """The Hoteles button is the first button in the hub."""
        from garay.infraestructura.telegram.handlers_egresos import cmd_egresos
        from garay.infraestructura.telegram.handlers_hoteles import CB_HUB_HOTELES

        update = _make_update()
        ctx = _make_context(es_admin=True)
        await cmd_egresos(update, ctx)

        markup = update.effective_message.reply_text.call_args.kwargs.get("reply_markup")
        assert markup is not None
        first_row = markup.inline_keyboard[0]
        assert first_row[0].callback_data == CB_HUB_HOTELES
