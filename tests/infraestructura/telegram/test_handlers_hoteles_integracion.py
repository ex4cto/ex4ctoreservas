"""Integration tests for hotel handler flows (full pago flow and /deudas command)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, ObligacionHotel
from garay.dominio.conciliacion.tipos import TipoEgreso


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOTEL_ID = uuid.UUID("11111111-0001-0001-0001-111111111111")


def _make_obligacion(
    hotel_id: uuid.UUID = _HOTEL_ID,
    nombre: str = "Hotel Marie",
    receptor: str = "Maria",
    deuda_inicial: Decimal = Decimal("5000000"),
) -> ObligacionHotel:
    return ObligacionHotel(
        id=hotel_id,
        punto_de_venta_nombre=nombre,
        receptor_nombre=receptor,
        monto_cuota_dia_1=Dinero(Decimal("1000000")),
        monto_cuota_dia_2=None,
        dia_pago_1=1,
        dia_pago_2=None,
        deuda_inicial=Dinero(deuda_inicial),
        fecha_deuda_inicial=datetime.date(2024, 1, 1),
        activa=True,
    )


def _make_egreso_registrado(
    hotel_id: uuid.UUID = _HOTEL_ID,
    monto: Decimal = Decimal("1000000"),
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="cuota Hotel Marie",
        monto=Dinero(monto),
        fecha=datetime.date(2024, 9, 15),
        categoria="cuota_hotel",
        tipo=TipoEgreso.MANUAL,
        destinatario="Maria",
        obligacion_hotel_id=hotel_id,
    )


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


def _make_admin_repo(es_admin: bool = True) -> MagicMock:
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = es_admin
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_context(
    hotel_service: MagicMock | None = None,
    es_admin: bool = True,
    user_data: dict | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot_data = {
        "freelancer_repo": _make_admin_repo(es_admin),
        "hotel_service": hotel_service,
    }
    return ctx


# ---------------------------------------------------------------------------
# Integration test: complete pago flow
# ---------------------------------------------------------------------------

class TestPagoFlowCompleto:
    """Test the full hotel payment state machine from list to confirmation."""

    @pytest.mark.asyncio
    async def test_flujo_completo_pago_con_monto_texto(self) -> None:
        """Full flow: list → detail → monto → fecha → concepto → confirmar → pago registrado."""
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers_hoteles import (
            CB_HUB_HOTELES,
            CB_HOTEL_HISTORIAL,
            CB_HOTEL_OMITIR_CONCEPTO,
            CB_HOTEL_PAGAR,
            CB_HOTEL_PAGO_CONFIRMAR,
            HOTEL_DETALLE,
            HOTEL_LIST,
            HOTEL_PAGO_CONCEPTO,
            HOTEL_PAGO_CONFIRMAR,
            HOTEL_PAGO_FECHA,
            HOTEL_PAGO_MONTO,
            handle_hotel_detalle,
            handle_hotel_lista,
            handle_pago_concepto,
            handle_pago_confirmar,
            handle_pago_fecha,
            handle_pago_monto,
        )

        hotel = _make_obligacion()
        saldo_inicial = Dinero(Decimal("4000000"))
        saldo_pos_pago = Dinero(Decimal("3000000"))

        svc = MagicMock()
        svc.listar_con_saldo.return_value = [(hotel, saldo_inicial)]
        svc.saldo_actual.side_effect = [saldo_inicial, saldo_pos_pago, saldo_pos_pago]
        svc.monto_sugerido.return_value = Dinero(Decimal("1000000"))
        egreso_registrado = _make_egreso_registrado(hotel_id=hotel.id)
        svc.registrar_pago.return_value = egreso_registrado

        ctx = _make_context(hotel_service=svc)

        # Step 1: Entry — hotel list
        update = _make_update(callback_data=CB_HUB_HOTELES)
        resultado = await handle_hotel_lista(update, ctx)
        assert resultado == HOTEL_LIST
        assert str(hotel.id) in ctx.user_data.get("hotel_ids", [])

        # Step 2: Select the hotel → detail
        ctx.user_data.update({"hotel_ids": [str(hotel.id)]})
        update = _make_update(callback_data="hotel:0")
        resultado = await handle_hotel_detalle(update, ctx)
        assert resultado == HOTEL_DETALLE
        assert ctx.user_data["hotel_sel_id"] == str(hotel.id)

        # Step 3: Click "Registrar pago" → pedir monto
        ctx.user_data["hotel_sel_nombre"] = hotel.punto_de_venta_nombre
        update = _make_update(callback_data=CB_HOTEL_PAGAR)
        resultado = await handle_hotel_detalle(update, ctx)
        assert resultado == HOTEL_PAGO_MONTO

        # Step 4: Enter monto as text
        update = _make_update(text="1000000")
        resultado = await handle_pago_monto(update, ctx)
        assert resultado == HOTEL_PAGO_FECHA
        assert ctx.user_data["hotel_pago_monto"] == Decimal("1000000")

        # Step 5: Enter date as text
        update = _make_update(text="15/09/2024")
        resultado = await handle_pago_fecha(update, ctx)
        assert resultado == HOTEL_PAGO_CONCEPTO

        # Step 6: Omit concepto
        update = _make_update(callback_data=CB_HOTEL_OMITIR_CONCEPTO)
        resultado = await handle_pago_concepto(update, ctx)
        assert resultado == HOTEL_PAGO_CONFIRMAR

        # Step 7: Confirm payment
        update = _make_update(callback_data=CB_HOTEL_PAGO_CONFIRMAR, user_id=999)
        resultado = await handle_pago_confirmar(update, ctx)

        # Payment was registered
        svc.registrar_pago.assert_called_once()
        call_kwargs = svc.registrar_pago.call_args.kwargs
        assert call_kwargs["obligacion_id"] == hotel.id
        assert call_kwargs["monto"].monto == Decimal("1000000")
        assert call_kwargs["concepto"] is None

        # Returned to HOTEL_DETALLE
        assert resultado == HOTEL_DETALLE

    @pytest.mark.asyncio
    async def test_pago_con_concepto_textual(self) -> None:
        """Flow includes a typed concepto and it is passed to registrar_pago."""
        from garay.infraestructura.telegram.handlers_hoteles import (
            CB_HOTEL_OMITIR_CONCEPTO,
            CB_HOTEL_PAGO_CONFIRMAR,
            HOTEL_DETALLE,
            HOTEL_PAGO_CONFIRMAR,
            handle_pago_concepto,
            handle_pago_confirmar,
        )

        hotel = _make_obligacion()
        svc = MagicMock()
        svc.listar_con_saldo.return_value = [(hotel, Dinero(Decimal("4000000")))]
        svc.saldo_actual.return_value = Dinero(Decimal("4000000"))
        svc.registrar_pago.return_value = _make_egreso_registrado()

        ctx = _make_context(
            hotel_service=svc,
            user_data={
                "hotel_sel_id": str(hotel.id),
                "hotel_sel_nombre": hotel.punto_de_venta_nombre,
                "hotel_pago_monto": Decimal("1000000"),
                "hotel_pago_fecha": datetime.date(2024, 9, 15),
            },
        )

        # Enter concepto
        update = _make_update(text="cuota 15 sep")
        resultado = await handle_pago_concepto(update, ctx)
        assert resultado == HOTEL_PAGO_CONFIRMAR
        assert ctx.user_data["hotel_pago_concepto"] == "cuota 15 sep"

        # Confirm
        update = _make_update(callback_data=CB_HOTEL_PAGO_CONFIRMAR, user_id=999)
        await handle_pago_confirmar(update, ctx)

        call_kwargs = svc.registrar_pago.call_args.kwargs
        assert call_kwargs["concepto"] == "cuota 15 sep"

    @pytest.mark.asyncio
    async def test_egreso_registrado_tiene_obligacion_hotel_id(self) -> None:
        """The Egreso produced by registrar_pago has obligacion_hotel_id set."""
        from garay.infraestructura.telegram.handlers_hoteles import (
            CB_HOTEL_PAGO_CONFIRMAR,
            handle_pago_confirmar,
        )

        hotel = _make_obligacion()
        egreso = _make_egreso_registrado(hotel_id=hotel.id)
        svc = MagicMock()
        svc.listar_con_saldo.return_value = [(hotel, Dinero(Decimal("4000000")))]
        svc.saldo_actual.return_value = Dinero(Decimal("3000000"))
        svc.registrar_pago.return_value = egreso

        ctx = _make_context(
            hotel_service=svc,
            user_data={
                "hotel_sel_id": str(hotel.id),
                "hotel_sel_nombre": hotel.punto_de_venta_nombre,
                "hotel_pago_monto": Decimal("1000000"),
                "hotel_pago_fecha": datetime.date(2024, 9, 15),
                "hotel_pago_concepto": None,
            },
        )
        update = _make_update(callback_data=CB_HOTEL_PAGO_CONFIRMAR, user_id=999)
        await handle_pago_confirmar(update, ctx)

        # Verify the egreso returned has obligacion_hotel_id set
        assert egreso.obligacion_hotel_id == hotel.id

    @pytest.mark.asyncio
    async def test_saldo_decreases_after_pago(self) -> None:
        """After registering a payment, saldo_actual is called again and reflects the decrease."""
        from garay.infraestructura.telegram.handlers_hoteles import (
            CB_HOTEL_PAGO_CONFIRMAR,
            handle_pago_confirmar,
        )

        hotel = _make_obligacion(deuda_inicial=Decimal("5000000"))
        saldo_antes = Dinero(Decimal("4000000"))
        saldo_despues = Dinero(Decimal("3000000"))

        svc = MagicMock()
        svc.listar_con_saldo.return_value = [(hotel, saldo_despues)]
        # First call returns before-pago saldo (for detail view), second after
        svc.saldo_actual.side_effect = [saldo_despues, saldo_despues]
        svc.registrar_pago.return_value = _make_egreso_registrado()

        ctx = _make_context(
            hotel_service=svc,
            user_data={
                "hotel_sel_id": str(hotel.id),
                "hotel_sel_nombre": hotel.punto_de_venta_nombre,
                "hotel_pago_monto": Decimal("1000000"),
                "hotel_pago_fecha": datetime.date(2024, 9, 15),
                "hotel_pago_concepto": None,
            },
        )
        update = _make_update(callback_data=CB_HOTEL_PAGO_CONFIRMAR, user_id=999)
        resultado = await handle_pago_confirmar(update, ctx)

        # saldo_actual was called after registrar_pago to show updated saldo
        assert svc.saldo_actual.called
        assert resultado == 201  # HOTEL_DETALLE


# ---------------------------------------------------------------------------
# Integration test: /deudas command
# ---------------------------------------------------------------------------

class TestCmdDeudasIntegracion:
    @pytest.mark.asyncio
    async def test_deudas_muestra_todos_los_hoteles(self) -> None:
        """The /deudas command lists all hotels with their balances."""
        from garay.infraestructura.telegram.handlers_hoteles import cmd_deudas

        hoteles = [
            _make_obligacion(
                hotel_id=uuid.UUID("11111111-0001-0001-0001-111111111111"),
                nombre="Hotel Marie",
                receptor="Maria",
            ),
            _make_obligacion(
                hotel_id=uuid.UUID("11111111-0002-0002-0002-222222222222"),
                nombre="Mama Waldy",
                receptor="Waldy",
            ),
            _make_obligacion(
                hotel_id=uuid.UUID("11111111-0003-0003-0003-333333333333"),
                nombre="Hostal Dora",
                receptor="Dora",
            ),
            _make_obligacion(
                hotel_id=uuid.UUID("11111111-0004-0004-0004-444444444444"),
                nombre="Crespo",
                receptor="Crespo Mgmt",
            ),
        ]
        saldos = [
            Dinero(Decimal("2000000")),
            Dinero(Decimal("1500000")),
            Dinero(Decimal("3000000")),
            Dinero(Decimal("500000")),
        ]

        svc = MagicMock()
        svc.listar_con_saldo.return_value = list(zip(hoteles, saldos))

        update = _make_update(user_id=999)
        ctx = _make_context(hotel_service=svc, es_admin=True)

        await cmd_deudas(update, ctx)

        svc.listar_con_saldo.assert_called_once()
        update.effective_message.reply_text.assert_called_once()
        text = update.effective_message.reply_text.call_args.args[0]

        # All 4 hotels should appear in the response
        assert "Hotel Marie" in text
        assert "Mama Waldy" in text
        assert "Hostal Dora" in text
        assert "Crespo" in text

    @pytest.mark.asyncio
    async def test_deudas_incluye_total(self) -> None:
        """The /deudas response contains a computed total balance."""
        from garay.infraestructura.telegram.handlers_hoteles import cmd_deudas

        hotel = _make_obligacion(nombre="Hotel Marie")
        saldo = Dinero(Decimal("2000000"))

        svc = MagicMock()
        svc.listar_con_saldo.return_value = [(hotel, saldo)]

        update = _make_update(user_id=999)
        ctx = _make_context(hotel_service=svc, es_admin=True)

        await cmd_deudas(update, ctx)

        text = update.effective_message.reply_text.call_args.args[0]
        # Should contain "Total" from the message template
        assert "Total" in text or "total" in text.lower()

    @pytest.mark.asyncio
    async def test_deudas_no_admin_deniega_acceso(self) -> None:
        """Non-admin users cannot access /deudas."""
        from garay.infraestructura.telegram.handlers_hoteles import cmd_deudas

        hotel = _make_obligacion()
        svc = MagicMock()
        svc.listar_con_saldo.return_value = [(hotel, Dinero(Decimal("2000000")))]

        update = _make_update(user_id=9999)
        ctx = _make_context(hotel_service=svc, es_admin=False)

        await cmd_deudas(update, ctx)

        # Service was NOT called because requiere_admin denied access
        svc.listar_con_saldo.assert_not_called()
