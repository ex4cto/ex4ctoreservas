"""PTB handler for /cuenta_cobro — generates PDF cuenta de cobro for Isla Palma."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.comun.fechas import parsear_fecha
from garay.aplicacion.comun.formato import fmt_cop
from garay.infraestructura.telegram.auth import requiere_admin_conv
from garay.infraestructura.telegram.handlers import cmd_start

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 300-301 (no collision with existing handlers:
# egresos: 100-152, freelancers: 201-213, gestion_ventas: 220-226,
# socios: 250-253, propuestas: 400-419)
# ---------------------------------------------------------------------------

CC_ESPERAR_FECHA: int = 300
CC_CONFIRMAR: int = 301

# ---------------------------------------------------------------------------
# Callback data constants
# ---------------------------------------------------------------------------

_CB_GENERAR = "cc_generar"
_CB_CANCELAR = "cc_cancelar"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEXT = filters.TEXT & ~filters.COMMAND


def _limpiar(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove cc_* keys from user_data."""
    if context.user_data is not None:
        context.user_data.pop("cc_fecha", None)
        context.user_data.pop("cc_ventas", None)
        context.user_data.pop("cc_ganancia", None)


# ---------------------------------------------------------------------------
# Entry point: /cuenta_cobro
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_cuenta_cobro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — /cuenta_cobro. Admin-only."""
    _limpiar(context)

    if update.effective_message:
        await update.effective_message.reply_text(
            "📋 <b>Cuenta de Cobro — Isla Palma</b>\n\n"
            "Ingresa la fecha de ventas (DD/MM/YYYY):\n\n"
            "Escribe /cancelar para salir.",
            parse_mode="HTML",
        )
    return CC_ESPERAR_FECHA


# ---------------------------------------------------------------------------
# CC_ESPERAR_FECHA state
# ---------------------------------------------------------------------------


async def handle_cc_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive date, search ventas, show summary with action buttons."""
    if update.effective_message is None or update.effective_message.text is None:
        return CC_ESPERAR_FECHA

    texto = update.effective_message.text.strip()
    dt = parsear_fecha(texto)
    if dt is None:
        await update.effective_message.reply_text(
            "Formato de fecha inválido. Usa DD/MM/YYYY (ejemplo: 07/10/2026)."
        )
        return CC_ESPERAR_FECHA

    fecha = dt.date()

    # Retrieve the service from bot_data.
    svc = context.bot_data.get("cuenta_cobro_service")
    if svc is None:
        logger.error("cuenta_cobro_service not found in bot_data — wiring error")
        await update.effective_message.reply_text(
            "Error de configuración. Contacta al administrador."
        )
        return ConversationHandler.END

    ventas = svc.buscar_ventas_isla_palma(fecha)
    if not ventas:
        await update.effective_message.reply_text(
            f"No se encontraron ventas de Isla Palma para el {fecha.strftime('%d/%m/%Y')}.",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # Sum ganancia for the preview using comisiones_repo.
    comisiones_repo = context.bot_data.get("comision_registrada_repo")
    from garay.dominio.comun.dinero import Dinero

    ganancia_total = Dinero(0)
    for venta in ventas:
        if comisiones_repo is not None:
            comision = comisiones_repo.buscar_por_venta_id(venta.id)
            if comision is not None:
                ganancia_total = ganancia_total + comision.desglose.agencia
                continue
        ganancia_total = ganancia_total + venta.neto

    # Save state.
    if context.user_data is not None:
        context.user_data["cc_fecha"] = fecha
        context.user_data["cc_ventas"] = len(ventas)

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Generar PDF", callback_data=_CB_GENERAR),
                InlineKeyboardButton("✖ Cancelar", callback_data=_CB_CANCELAR),
            ]
        ]
    )
    await update.effective_message.reply_text(
        f"📊 <b>Resumen Isla Palma — {fecha.strftime('%d/%m/%Y')}</b>\n\n"
        f"Ventas encontradas: <b>{len(ventas)}</b>\n"
        f"Ganancia total agencia: <b>{fmt_cop(ganancia_total)}</b>\n\n"
        "¿Generar la cuenta de cobro?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    return CC_CONFIRMAR


# ---------------------------------------------------------------------------
# CC_CONFIRMAR state
# ---------------------------------------------------------------------------


async def handle_cc_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation or cancellation buttons."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    data = query.data if query is not None else ""

    if data == _CB_CANCELAR:
        _limpiar(context)
        if query is not None and query.message is not None:
            await query.message.edit_text("✖ Cuenta de cobro cancelada.")
        return ConversationHandler.END

    # Retrieve state.
    fecha = context.user_data.get("cc_fecha") if context.user_data else None
    if fecha is None:
        if query is not None and query.message is not None:
            await query.message.edit_text("Error: estado perdido. Vuelve a usar /cuenta_cobro.")
        return ConversationHandler.END

    svc = context.bot_data.get("cuenta_cobro_service")
    comisiones_repo = context.bot_data.get("comision_registrada_repo")
    if svc is None or comisiones_repo is None:
        logger.error("cuenta_cobro_service or comision_registrada_repo missing — wiring error")
        if query is not None and query.message is not None:
            await query.message.edit_text(
                "Error de configuración. Contacta al administrador."
            )
        return ConversationHandler.END

    if query is not None and query.message is not None:
        await query.message.edit_text("⏳ Generando PDF, un momento…")

    try:
        resultado = await svc.ejecutar(fecha=fecha, comisiones_repo=comisiones_repo)
    except ValueError as exc:
        if query is not None and query.message is not None:
            await query.message.edit_text(f"No se pudo generar: {exc}")
        return ConversationHandler.END
    except Exception:
        logger.exception("Error generating cuenta de cobro PDF")
        if query is not None and query.message is not None:
            await query.message.edit_text(
                "Error al generar el PDF. Revisa los logs y contacta al desarrollador."
            )
        return ConversationHandler.END

    filename = (
        f"cuenta_cobro_isla_palma_{resultado.numero:03d}"
        f"_{resultado.fecha.strftime('%Y%m%d')}.pdf"
    )

    chat_id = (
        update.effective_chat.id if update.effective_chat else None
    )
    if chat_id is None:
        return ConversationHandler.END

    import io

    await context.bot.send_document(
        chat_id=chat_id,
        document=io.BytesIO(resultado.pdf_bytes),
        filename=filename,
        caption=(
            f"📄 Cuenta de Cobro No <b>{resultado.numero:03d}</b>\n"
            f"Fecha: {resultado.fecha.strftime('%d/%m/%Y')}\n"
            f"Ganancia: <b>{fmt_cop(resultado.ganancia)}</b>"
        ),
        parse_mode="HTML",
    )

    _limpiar(context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Fallback: /cancelar
# ---------------------------------------------------------------------------


async def handle_cc_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Abort the conversation from any state."""
    _limpiar(context)
    if update.effective_message:
        await update.effective_message.reply_text("✖ Operación cancelada.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def registrar_handlers(app: object) -> None:
    """Register the /cuenta_cobro ConversationHandler on the PTB Application."""
    conv = ConversationHandler(
        entry_points=[CommandHandler("cuenta_cobro", cmd_cuenta_cobro)],
        states={
            CC_ESPERAR_FECHA: [MessageHandler(_TEXT, handle_cc_fecha)],
            CC_CONFIRMAR: [CallbackQueryHandler(handle_cc_confirmar)],
        },
        fallbacks=[
            CommandHandler("cancelar", handle_cc_cancelar),
            CommandHandler("start", cmd_start),
        ],
        per_message=False,
    )
    app.add_handler(conv, group=5)  # type: ignore[attr-defined]
