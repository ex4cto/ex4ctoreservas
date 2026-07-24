"""PTB handler functions — thin adapter over FSMTiquetera."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from garay.aplicacion.tiquetera.fsm import (
    ContextoVenta,
    EstadoFSM,
    FSMTiquetera,
    SalidaFSM,
)
from garay.infraestructura.telegram.estados import ESTADO_PTB

logger = logging.getLogger(__name__)

_fsm = FSMTiquetera()


def _teclado(opciones: list[str]) -> InlineKeyboardMarkup | None:
    if not opciones:
        return None
    botones = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones]
    return InlineKeyboardMarkup(botones)


def _get_contexto(context: ContextTypes.DEFAULT_TYPE) -> ContextoVenta:
    if context.user_data is None:
        return ContextoVenta()
    ctx = context.user_data.get("contexto")
    if not isinstance(ctx, ContextoVenta):
        return ContextoVenta()
    return ctx


async def _enviar_salida(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    salida: SalidaFSM,
) -> int:
    context.user_data["contexto"] = salida.contexto  # type: ignore[index]
    teclado = _teclado(salida.opciones)
    if update.message:
        await update.message.reply_text(
            salida.mensaje,
            reply_markup=teclado,
            parse_mode="Markdown",
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            salida.mensaje,
            reply_markup=teclado,
            parse_mode="Markdown",
        )
    return ESTADO_PTB[salida.nuevo_estado]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start — initialize the FSM."""
    salida = _fsm.iniciar()
    return await _enviar_salida(update, context, salida)


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancelar — cancel from any state."""
    ctx = _get_contexto(context)
    salida = _fsm.cancelar(ctx)
    return await _enviar_salida(update, context, salida)


def _make_handler(estado: EstadoFSM):  # type: ignore[return]
    """Factory: creates an async handler for a given FSM state."""

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        entrada: str = ""
        if update.callback_query:
            await update.callback_query.answer()
            entrada = update.callback_query.data or ""
        elif update.message and update.message.text:
            entrada = update.message.text
        ctx = _get_contexto(context)
        salida = _fsm.procesar(estado, entrada, ctx)
        if salida.listo:
            # TODO(UW5): call servicio.ejecutar(cmd) here once repos are wired.
            # NotificadorGrupoTelegram is ready — service wiring happens in infraestructura layer.
            logger.info("Venta lista para registrar (service wiring pendiente): %s", salida.contexto)
        return await _enviar_salida(update, context, salida)

    handler.__name__ = f"handle_{estado.value}"
    return handler


# Pre-built handlers for each FSM state
handle_tipo_reserva = _make_handler(EstadoFSM.TIPO_RESERVA)
handle_punto_de_venta = _make_handler(EstadoFSM.PUNTO_DE_VENTA)
handle_destino = _make_handler(EstadoFSM.DESTINO)
handle_cliente_nombre = _make_handler(EstadoFSM.CLIENTE_NOMBRE)
handle_cliente_telefono = _make_handler(EstadoFSM.CLIENTE_TELEFONO)
handle_cliente_hotel = _make_handler(EstadoFSM.CLIENTE_HOTEL)
handle_cliente_habitacion = _make_handler(EstadoFSM.CLIENTE_HABITACION)
handle_fecha_salida = _make_handler(EstadoFSM.FECHA_SALIDA)
handle_pax_adultos = _make_handler(EstadoFSM.PAX_ADULTOS)
handle_pax_ninos = _make_handler(EstadoFSM.PAX_NINOS)
handle_numero_ticket = _make_handler(EstadoFSM.NUMERO_TICKET)
handle_monto_valor = _make_handler(EstadoFSM.MONTO_VALOR)
handle_monto_abono = _make_handler(EstadoFSM.MONTO_ABONO)
handle_monto_neto = _make_handler(EstadoFSM.MONTO_NETO)
handle_participante_nombre = _make_handler(EstadoFSM.PARTICIPANTE_NOMBRE)
handle_participante_rol = _make_handler(EstadoFSM.PARTICIPANTE_ROL)
handle_participante_otro = _make_handler(EstadoFSM.PARTICIPANTE_OTRO)
handle_confirmacion = _make_handler(EstadoFSM.CONFIRMACION)
