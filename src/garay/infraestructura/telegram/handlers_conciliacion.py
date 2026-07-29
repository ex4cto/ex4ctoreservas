"""Telegram handlers for the conciliacion module.

Commands:
  /conciliar   — Run the reconciliation engine (owner only).
  /pendientes  — List conciliaciones awaiting manual review (owner only).

Callbacks (inline keyboard):
  conc:{id}:match     — Mark conciliacion as MATCHEADO.
  conc:{id}:personal  — Mark conciliacion as PERSONAL.
  conc:{id}:sin_match — Mark conciliacion as SIN_MATCH.
"""

from __future__ import annotations

import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from garay.dominio.conciliacion.tipos import EstadoConciliacion
from garay.dominio.puertos.repositorios import ConciliacionRepository
from garay.infraestructura.telegram.auth import requiere_propietario
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

_CALLBACK_PREFIX = "conc"

_MAPA_ACCIONES: dict[str, tuple[EstadoConciliacion, str]] = {
    "match": (EstadoConciliacion.MATCHEADO, "conciliacion.confirmado"),
    "personal": (EstadoConciliacion.PERSONAL, "conciliacion.marcado_personal"),
    "sin_match": (EstadoConciliacion.SIN_MATCH, "conciliacion.marcado_sin_match"),
}


@requiere_propietario
async def cmd_conciliar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run the reconciliation engine and reply with the summary."""
    from garay.aplicacion.conciliacion.conciliar_ingresos import ConciliarIngresosService

    servicio: ConciliarIngresosService = context.bot_data["conciliar_service"]
    resultado = servicio.ejecutar()

    texto = obtener_mensaje("conciliacion.resumen").format(
        matcheados=resultado.matcheados,
        sin_match=resultado.sin_match,
        pendientes=resultado.pendientes,
    )
    if update.effective_message:
        await update.effective_message.reply_text(texto)


@requiere_propietario
async def cmd_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List pending conciliaciones with inline action buttons."""
    repo: ConciliacionRepository = context.bot_data["conciliacion_repo"]
    pendientes = repo.listar_pendientes()

    if not pendientes:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("conciliacion.sin_pendientes")
            )
        return

    for conc in pendientes:
        botones = [
            [
                InlineKeyboardButton(
                    "✅ Match",
                    callback_data=f"{_CALLBACK_PREFIX}:{conc.id}:match",
                ),
                InlineKeyboardButton(
                    "👤 Personal",
                    callback_data=f"{_CALLBACK_PREFIX}:{conc.id}:personal",
                ),
                InlineKeyboardButton(
                    "❓ Sin match",
                    callback_data=f"{_CALLBACK_PREFIX}:{conc.id}:sin_match",
                ),
            ]
        ]
        sugerencia = str(conc.venta_id) if conc.venta_id else "Sin sugerencia"
        texto = obtener_mensaje("conciliacion.item_pendiente").format(
            monto=str(conc.ingreso_id),
            banco="—",
            fecha="—",
            sugerencia=sugerencia,
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                texto, reply_markup=InlineKeyboardMarkup(botones)
            )


async def callback_conciliar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard actions for a conciliacion."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    partes = (query.data or "").split(":")
    if len(partes) != 3:
        return

    _, conc_id_str, accion = partes
    try:
        conc_id = uuid.UUID(conc_id_str)
    except ValueError:
        return

    if accion not in _MAPA_ACCIONES:
        return

    repo: ConciliacionRepository = context.bot_data["conciliacion_repo"]
    conciliacion = repo.buscar_por_id(conc_id)
    if conciliacion is None:
        return

    nuevo_estado, clave_msg = _MAPA_ACCIONES[accion]
    conciliacion.estado = nuevo_estado
    repo.guardar(conciliacion)

    if query.message:
        await query.edit_message_text(obtener_mensaje(clave_msg))


def registrar_handlers(app: object) -> None:
    """Register all conciliacion handlers with the Telegram Application."""
    from telegram.ext import Application

    assert isinstance(app, Application)
    app.add_handler(CommandHandler("conciliar", cmd_conciliar))
    app.add_handler(CommandHandler("pendientes", cmd_pendientes))
    app.add_handler(
        CallbackQueryHandler(callback_conciliar, pattern=rf"^{_CALLBACK_PREFIX}:")
    )
