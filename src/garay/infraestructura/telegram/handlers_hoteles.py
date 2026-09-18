"""PTB handlers for hotel payment obligations (ConversationHandler + /deudas command)."""

from __future__ import annotations

import datetime
import logging
import uuid
import zoneinfo
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.comun.fechas import parsear_fecha
from garay.aplicacion.comun.montos import parsear_monto
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import ObligacionHotel
from garay.infraestructura.telegram.auth import (
    requiere_admin,
    requiere_admin_conv,
)
from garay.mensajes.catalogo import formatear_html, obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 200-219 (no collision with egresos 100-152 or tiquetera 0-36)
# ---------------------------------------------------------------------------

HOTEL_LIST: int = 200
HOTEL_DETALLE: int = 201
HOTEL_PAGO_MONTO: int = 202
HOTEL_PAGO_FECHA: int = 203
HOTEL_PAGO_CONCEPTO: int = 204
HOTEL_PAGO_CONFIRMAR: int = 205
HOTEL_HISTORIAL: int = 206

# ---------------------------------------------------------------------------
# Callback data constants
# ---------------------------------------------------------------------------

CB_HUB_HOTELES: str = "hub_hoteles"
PREFIJO_HOTEL_SEL: str = "hotel:"
CB_HOTEL_PAGAR: str = "hotel_pagar"
CB_HOTEL_HISTORIAL: str = "hotel_historial"
CB_HOTEL_ATRAS: str = "hotel_atras"
CB_HOTEL_VOLVER_DETALLE: str = "hotel_volver_detalle"
CB_HOTEL_USAR_SUGERIDO: str = "hotel_usar_sugerido"
CB_HOTEL_HOY: str = "hotel_hoy"
CB_HOTEL_OMITIR_CONCEPTO: str = "hotel_omitir_concepto"
CB_HOTEL_PAGO_CONFIRMAR: str = "hotel_pago_confirmar"
CB_HOTEL_PAGO_EDITAR: str = "hotel_pago_editar"
CB_HOTEL_PAGO_CANCELAR: str = "hotel_pago_cancelar"

# ---------------------------------------------------------------------------
# Timezone helper
# ---------------------------------------------------------------------------

_ZONA_BOGOTA: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("America/Bogota")


def _hoy_bogota() -> datetime.date:
    """Current date in Bogota timezone. Testable via monkeypatching."""
    return datetime.datetime.now(_ZONA_BOGOTA).date()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_cop(valor: Decimal) -> str:
    return "$" + f"{int(valor):,}".replace(",", ".")


def _fmt_dinero(dinero: Dinero) -> str:
    return _fmt_cop(dinero.monto)


def _fila_boton(texto: str, data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(texto, callback_data=data)]


async def _reply(
    update: Update, texto: str, teclado: InlineKeyboardMarkup | None = None
) -> None:
    """Send or edit a message, handling both callback queries and regular messages."""
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            texto, reply_markup=teclado, parse_mode="HTML"
        )
    elif update.effective_message is not None:
        await update.effective_message.reply_text(
            texto, reply_markup=teclado, parse_mode="HTML"
        )


def _input_text(update: Update) -> str:
    if update.callback_query is not None:
        return update.callback_query.data or ""
    if update.message is not None and update.message.text:
        return update.message.text
    return ""


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict[str, object]:
    if context.user_data is None:
        return {}
    return context.user_data


def _parsear_monto_cop(texto: str) -> Decimal | None:
    """Parse a Colombian peso amount, rejecting zero and negative values."""
    valor = parsear_monto(texto)
    if valor is None or valor <= Decimal("0"):
        return None
    return valor


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def _teclado_lista_hoteles(
    hoteles_con_saldo: list[tuple[ObligacionHotel, Dinero]],
) -> InlineKeyboardMarkup:
    filas: list[list[InlineKeyboardButton]] = []
    for i, (hotel, saldo) in enumerate(hoteles_con_saldo):
        label = f"🏨 {hotel.punto_de_venta_nombre} — saldo {_fmt_dinero(saldo)}"
        filas.append(_fila_boton(label, f"{PREFIJO_HOTEL_SEL}{i}"))
    filas.append(_fila_boton("⬅️ Volver", CB_HOTEL_ATRAS))
    return InlineKeyboardMarkup(filas)


def _teclado_detalle() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _fila_boton("💰 Registrar pago", CB_HOTEL_PAGAR),
            _fila_boton("📋 Ver historial", CB_HOTEL_HISTORIAL),
            _fila_boton("⬅️ Volver", CB_HOTEL_ATRAS),
        ]
    )


def _teclado_confirmar_pago() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=CB_HOTEL_PAGO_CONFIRMAR),
                InlineKeyboardButton("✏️ Editar", callback_data=CB_HOTEL_PAGO_EDITAR),
                InlineKeyboardButton("❌ Cancelar", callback_data=CB_HOTEL_PAGO_CANCELAR),
            ]
        ]
    )


def _texto_detalle(
    hotel: ObligacionHotel, saldo: Dinero
) -> str:
    linea_dia_2 = ""
    if hotel.dia_pago_2 is not None and hotel.monto_cuota_dia_2 is not None:
        linea_dia_2 = (
            f"Cuota día {hotel.dia_pago_2}: {_fmt_dinero(hotel.monto_cuota_dia_2)}\n"
        )
    return formatear_html(
        obtener_mensaje("hoteles.detalle"),
        nombre=hotel.punto_de_venta_nombre,
        receptor=hotel.receptor_nombre,
        dia_1=str(hotel.dia_pago_1),
        cuota_1=_fmt_dinero(hotel.monto_cuota_dia_1),
        linea_dia_2=linea_dia_2,
        saldo=_fmt_dinero(saldo),
    )


def _texto_resumen_pago(
    hotel: ObligacionHotel,
    monto: Decimal,
    fecha: datetime.date,
    concepto: str | None,
    saldo_tras_pago: Dinero,
) -> str:
    return formatear_html(
        obtener_mensaje("hoteles.pagar_confirmar"),
        nombre=hotel.punto_de_venta_nombre,
        receptor=hotel.receptor_nombre,
        monto=_fmt_cop(monto),
        fecha=fecha.strftime("%d/%m/%Y"),
        concepto=concepto or "—",
        saldo_tras_pago=_fmt_dinero(saldo_tras_pago),
    )


# ---------------------------------------------------------------------------
# Entry point: hub_hoteles callback → shows hotel list
# ---------------------------------------------------------------------------


async def handle_hotel_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point triggered by hub_hoteles callback. Lists all active hotels."""
    svc = context.bot_data.get("hotel_service")
    if svc is None:
        logger.error("hotel_service not found in bot_data")
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    hoteles_con_saldo: list[tuple[ObligacionHotel, Dinero]] = svc.listar_con_saldo()
    ud = _ud(context)
    ud["hotel_ids"] = [str(h.id) for h, _ in hoteles_con_saldo]

    teclado = _teclado_lista_hoteles(hoteles_con_saldo)
    await _reply(update, obtener_mensaje("hoteles.lista_titulo"), teclado)
    return HOTEL_LIST


# ---------------------------------------------------------------------------
# HOTEL_LIST state: hotel selection or back
# ---------------------------------------------------------------------------


async def handle_hotel_detalle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle hotel selection (HOTEL_LIST state) and detail action buttons (HOTEL_DETALLE state)."""
    data = _input_text(update)
    ud = _ud(context)
    svc = context.bot_data.get("hotel_service")

    # Back to hotel list
    if data == CB_HOTEL_ATRAS:
        if svc is None:
            await _reply(update, obtener_mensaje("error_generico"))
            return ConversationHandler.END
        hoteles_con_saldo = svc.listar_con_saldo()
        ud["hotel_ids"] = [str(h.id) for h, _ in hoteles_con_saldo]
        teclado = _teclado_lista_hoteles(hoteles_con_saldo)
        await _reply(update, obtener_mensaje("hoteles.lista_titulo"), teclado)
        return HOTEL_LIST

    # Navigate to payment flow
    if data == CB_HOTEL_PAGAR:
        hotel_id_str = str(ud.get("hotel_sel_id", ""))
        if not hotel_id_str or svc is None:
            await _reply(update, obtener_mensaje("error_generico"))
            return ConversationHandler.END
        try:
            hotel_id = uuid.UUID(hotel_id_str)
        except ValueError:
            await _reply(update, obtener_mensaje("error_generico"))
            return ConversationHandler.END
        saldo = svc.saldo_actual(hotel_id)
        sugerido = svc.monto_sugerido(_get_hotel_from_service(svc, hotel_id), _hoy_bogota())
        nombre = str(ud.get("hotel_sel_nombre", ""))
        teclado = InlineKeyboardMarkup(
            [
                _fila_boton(
                    f"✅ Usar {_fmt_dinero(sugerido)} (cuota)",
                    CB_HOTEL_USAR_SUGERIDO,
                )
            ]
        )
        ud["hotel_monto_sugerido"] = sugerido.monto
        await _reply(
            update,
            formatear_html(
                obtener_mensaje("hoteles.pagar_pedir_monto"),
                nombre=nombre,
                saldo=_fmt_dinero(saldo),
            ),
            teclado,
        )
        return HOTEL_PAGO_MONTO

    # Navigate to historial
    if data == CB_HOTEL_HISTORIAL:
        return await handle_hotel_historial(update, context)

    # Hotel selection from list
    if data.startswith(PREFIJO_HOTEL_SEL):
        ids: list[str] = ud.get("hotel_ids", [])  # type: ignore[assignment]
        try:
            idx = int(data[len(PREFIJO_HOTEL_SEL):])
            hotel_id = uuid.UUID(ids[idx])
        except (ValueError, IndexError):
            if svc:
                hoteles_con_saldo = svc.listar_con_saldo()
                ud["hotel_ids"] = [str(h.id) for h, _ in hoteles_con_saldo]
                teclado = _teclado_lista_hoteles(hoteles_con_saldo)
                await _reply(update, obtener_mensaje("hoteles.lista_titulo"), teclado)
            return HOTEL_LIST

        if svc is None:
            await _reply(update, obtener_mensaje("error_generico"))
            return ConversationHandler.END

        saldo = svc.saldo_actual(hotel_id)
        # Find the hotel object
        hoteles_con_saldo = svc.listar_con_saldo()
        hotel = next((h for h, _ in hoteles_con_saldo if h.id == hotel_id), None)
        if hotel is None:
            await _reply(update, obtener_mensaje("error_generico"))
            return ConversationHandler.END

        ud["hotel_sel_id"] = str(hotel.id)
        ud["hotel_sel_nombre"] = hotel.punto_de_venta_nombre

        await _reply(update, _texto_detalle(hotel, saldo), _teclado_detalle())
        return HOTEL_DETALLE

    # Fallback
    await _reply(update, obtener_mensaje("error_generico"))
    return ConversationHandler.END


def _get_hotel_from_service(svc: object, hotel_id: uuid.UUID) -> ObligacionHotel:
    """Retrieve a single ObligacionHotel by id from the service."""
    # Use listar_con_saldo to find the object (avoids a separate repo call in handler)
    hoteles_con_saldo = svc.listar_con_saldo()  # type: ignore[attr-defined]
    return next((h for h, _ in hoteles_con_saldo if h.id == hotel_id))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# HOTEL_PAGO_MONTO state
# ---------------------------------------------------------------------------


async def handle_pago_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive payment amount (suggested or typed)."""
    data = _input_text(update)
    ud = _ud(context)
    svc = context.bot_data.get("hotel_service")

    monto: Decimal
    if data == CB_HOTEL_USAR_SUGERIDO:
        sugerido = ud.get("hotel_monto_sugerido")
        if not isinstance(sugerido, Decimal):
            # Re-compute from service
            hotel_id_str = str(ud.get("hotel_sel_id", ""))
            if svc and hotel_id_str:
                try:
                    hotel_id = uuid.UUID(hotel_id_str)
                    hotel = _get_hotel_from_service(svc, hotel_id)
                    monto = svc.monto_sugerido(hotel, _hoy_bogota()).monto
                except Exception:
                    await _reply(update, obtener_mensaje("error_generico"))
                    return ConversationHandler.END
            else:
                await _reply(update, obtener_mensaje("error_generico"))
                return ConversationHandler.END
        else:
            monto = sugerido
    else:
        parsed = _parsear_monto_cop(data)
        if parsed is None:
            await _reply(update, obtener_mensaje("egreso.error_monto"))
            return HOTEL_PAGO_MONTO
        monto = parsed

    ud["hotel_pago_monto"] = monto
    teclado = InlineKeyboardMarkup(
        [_fila_boton(f"📅 Hoy — {_hoy_bogota().strftime('%d/%m/%Y')}", CB_HOTEL_HOY)]
    )
    await _reply(update, obtener_mensaje("hoteles.pagar_pedir_fecha"), teclado)
    return HOTEL_PAGO_FECHA


# ---------------------------------------------------------------------------
# HOTEL_PAGO_FECHA state
# ---------------------------------------------------------------------------


async def handle_pago_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive payment date (today button or typed)."""
    data = _input_text(update)
    ud = _ud(context)

    if data == CB_HOTEL_HOY:
        fecha: datetime.date = _hoy_bogota()
    else:
        resultado = parsear_fecha(data)
        if resultado is None:
            await _reply(update, obtener_mensaje("egreso.error_fecha"))
            return HOTEL_PAGO_FECHA
        fecha = resultado.date()

    ud["hotel_pago_fecha"] = fecha
    teclado = InlineKeyboardMarkup(
        [_fila_boton("Omitir", CB_HOTEL_OMITIR_CONCEPTO)]
    )
    await _reply(update, obtener_mensaje("hoteles.pagar_pedir_concepto"), teclado)
    return HOTEL_PAGO_CONCEPTO


# ---------------------------------------------------------------------------
# HOTEL_PAGO_CONCEPTO state
# ---------------------------------------------------------------------------


async def handle_pago_concepto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive optional payment concept (skip or typed text)."""
    data = _input_text(update)
    ud = _ud(context)

    if data == CB_HOTEL_OMITIR_CONCEPTO:
        ud["hotel_pago_concepto"] = None
    else:
        texto = data.strip()
        ud["hotel_pago_concepto"] = texto if texto else None

    # Build confirmation message
    hotel_id_str = str(ud.get("hotel_sel_id", ""))
    monto: Decimal = ud.get("hotel_pago_monto", Decimal("0"))  # type: ignore[assignment]
    fecha: datetime.date = ud.get("hotel_pago_fecha", _hoy_bogota())  # type: ignore[assignment]
    concepto: str | None = ud.get("hotel_pago_concepto")  # type: ignore[assignment]

    svc = context.bot_data.get("hotel_service")
    if svc is None or not hotel_id_str:
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    try:
        hotel_id = uuid.UUID(hotel_id_str)
        hotel = _get_hotel_from_service(svc, hotel_id)
        saldo_actual = svc.saldo_actual(hotel_id)
    except Exception:
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    saldo_tras_pago = saldo_actual - Dinero(monto)
    texto = _texto_resumen_pago(hotel, monto, fecha, concepto, saldo_tras_pago)
    await _reply(update, texto, _teclado_confirmar_pago())
    return HOTEL_PAGO_CONFIRMAR


# ---------------------------------------------------------------------------
# HOTEL_PAGO_CONFIRMAR state
# ---------------------------------------------------------------------------


async def handle_pago_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process user choice on payment confirmation screen."""
    data = _input_text(update)
    ud = _ud(context)
    svc = context.bot_data.get("hotel_service")

    if data == CB_HOTEL_PAGO_CANCELAR:
        await _reply(update, obtener_mensaje("venta_cancelada"))
        return ConversationHandler.END

    if data == CB_HOTEL_PAGO_EDITAR:
        # Go back to monto step
        hotel_id_str = str(ud.get("hotel_sel_id", ""))
        nombre = str(ud.get("hotel_sel_nombre", ""))
        if svc and hotel_id_str:
            try:
                hotel_id = uuid.UUID(hotel_id_str)
                saldo = svc.saldo_actual(hotel_id)
                hotel = _get_hotel_from_service(svc, hotel_id)
                sugerido = svc.monto_sugerido(hotel, _hoy_bogota())
                ud["hotel_monto_sugerido"] = sugerido.monto
                teclado = InlineKeyboardMarkup(
                    [_fila_boton(f"✅ Usar {_fmt_dinero(sugerido)} (cuota)", CB_HOTEL_USAR_SUGERIDO)]
                )
                await _reply(
                    update,
                    formatear_html(
                        obtener_mensaje("hoteles.pagar_pedir_monto"),
                        nombre=nombre,
                        saldo=_fmt_dinero(saldo),
                    ),
                    teclado,
                )
            except Exception:
                await _reply(update, obtener_mensaje("error_generico"))
                return ConversationHandler.END
        return HOTEL_PAGO_MONTO

    if data != CB_HOTEL_PAGO_CONFIRMAR:
        await _reply(update, obtener_mensaje("venta_cancelada"))
        return ConversationHandler.END

    # Confirm: register the payment
    if svc is None:
        logger.error("hotel_service not found in bot_data")
        return ConversationHandler.END

    hotel_id_str = str(ud.get("hotel_sel_id", ""))
    monto: Decimal = ud.get("hotel_pago_monto", Decimal("0"))  # type: ignore[assignment]
    fecha: datetime.date = ud.get("hotel_pago_fecha", _hoy_bogota())  # type: ignore[assignment]
    concepto: str | None = ud.get("hotel_pago_concepto")  # type: ignore[assignment]

    user = update.effective_user
    registrado_por_id: int = user.id if user else 0

    from garay.config.settings import obtener_settings

    moneda = obtener_settings().moneda_predeterminada

    try:
        hotel_id = uuid.UUID(hotel_id_str)
        svc.registrar_pago(
            obligacion_id=hotel_id,
            monto=Dinero(monto, moneda),
            fecha=fecha,
            concepto=concepto,
            registrado_por_id=registrado_por_id,
        )
    except Exception:
        logger.exception("Error registrando pago hotel")
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    # Show success and go to detail with updated saldo
    try:
        nuevo_saldo = svc.saldo_actual(hotel_id)
        nombre = str(ud.get("hotel_sel_nombre", ""))
        await _reply(
            update,
            formatear_html(
                obtener_mensaje("hoteles.pago_registrado"),
                nombre=nombre,
                monto=_fmt_cop(monto),
                saldo=_fmt_dinero(nuevo_saldo),
            ),
        )
        hotel = _get_hotel_from_service(svc, hotel_id)
        await _reply(update, _texto_detalle(hotel, nuevo_saldo), _teclado_detalle())
    except Exception:
        logger.exception("Error showing post-payment detail")

    return HOTEL_DETALLE


# ---------------------------------------------------------------------------
# HOTEL_HISTORIAL state
# ---------------------------------------------------------------------------


async def handle_hotel_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show payment history or handle back button."""
    data = _input_text(update)
    ud = _ud(context)
    svc = context.bot_data.get("hotel_service")

    if data == CB_HOTEL_VOLVER_DETALLE:
        # Go back to detail
        hotel_id_str = str(ud.get("hotel_sel_id", ""))
        if svc and hotel_id_str:
            try:
                hotel_id = uuid.UUID(hotel_id_str)
                saldo = svc.saldo_actual(hotel_id)
                hotel = _get_hotel_from_service(svc, hotel_id)
                await _reply(update, _texto_detalle(hotel, saldo), _teclado_detalle())
                return HOTEL_DETALLE
            except Exception:
                pass
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    # Show historial
    hotel_id_str = str(ud.get("hotel_sel_id", ""))
    nombre = str(ud.get("hotel_sel_nombre", ""))

    if svc is None or not hotel_id_str:
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    try:
        hotel_id = uuid.UUID(hotel_id_str)
        pagos = svc.historial(hotel_id, 10)
    except Exception:
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END

    teclado = InlineKeyboardMarkup([_fila_boton("⬅️ Volver", CB_HOTEL_VOLVER_DETALLE)])

    if not pagos:
        texto = formatear_html(
            obtener_mensaje("hoteles.historial_titulo"), nombre=nombre
        ) + "\n\n" + formatear_html(
            obtener_mensaje("hoteles.historial_vacio"), nombre=nombre
        )
        await _reply(update, texto, teclado)
        return HOTEL_HISTORIAL

    lineas = [
        formatear_html(obtener_mensaje("hoteles.historial_titulo"), nombre=nombre)
    ]
    for pago in pagos:
        linea = (
            f"• {pago.fecha.strftime('%d/%m/%Y')} · {_fmt_dinero(pago.monto)}"
            + (f" · {pago.descripcion}" if pago.descripcion else "")
        )
        lineas.append(linea)

    await _reply(update, "\n".join(lineas), teclado)
    return HOTEL_HISTORIAL


# ---------------------------------------------------------------------------
# /deudas — admin-only, no FSM
# ---------------------------------------------------------------------------


@requiere_admin
async def cmd_deudas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a summary of all active hotel debts."""
    svc = context.bot_data.get("hotel_service")
    if svc is None:
        logger.error("hotel_service not found in bot_data")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("error_generico"), parse_mode="HTML"
            )
        return

    hoteles_con_saldo: list[tuple[object, Dinero]] = svc.listar_con_saldo()

    total = Dinero(Decimal("0"))
    filas: list[str] = []
    for hotel, saldo in hoteles_con_saldo:
        from garay.dominio.conciliacion.entidades import ObligacionHotel as _OH

        hotel_obj: _OH = hotel  # type: ignore[assignment]
        filas.append(
            f"• <b>{hotel_obj.punto_de_venta_nombre}</b> ({hotel_obj.receptor_nombre})"
            f" — saldo {_fmt_dinero(saldo)}"
        )
        total = total + saldo

    texto = formatear_html(
        obtener_mensaje("deudas.resumen"),
        filas="\n".join(filas),
        total=_fmt_dinero(total),
    )
    if update.effective_message:
        await update.effective_message.reply_text(texto, parse_mode="HTML")
