"""PTB handlers for /liquidar_socio — manual partner payment registration (E5)."""

from __future__ import annotations

import datetime
import logging
import uuid
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.comun.montos import parsear_monto
from garay.aplicacion.socios.split import ResumenSocio, ResumenSplitSocios
from garay.dominio.comun.dinero import Dinero
from garay.dominio.socios.entidades import PagoSocio
from garay.infraestructura.telegram.auth import requiere_propietario_conv
from garay.infraestructura.telegram.handlers import cmd_start
from garay.mensajes.catalogo import formatear_html, obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 250-253 to avoid collision with all existing ranges
# (egresos: 100-152, freelancers: 201-213, gestion_ventas: 220-226,
#  tours: 220-241, propuestas: 400-419)
# ---------------------------------------------------------------------------

LQ_SELECCION: int = 250
LQ_TIPO: int = 251
LQ_MONTO: int = 252
LQ_CONFIRMAR: int = 253

# ---------------------------------------------------------------------------
# Callback data constants
# ---------------------------------------------------------------------------

_CB_SOCIO_PREFIX: str = "lq_socio:"
_CB_TOTAL: str = "lq_total"
_CB_PARCIAL: str = "lq_parcial"
_CB_CONFIRMAR: str = "lq_confirmar"
_CB_CANCELAR: str = "lq_cancelar"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_cop(valor: Decimal) -> str:
    """Format a Decimal as Colombian pesos. E.g.: 500000 -> '$500.000'"""
    return "$" + f"{int(valor):,}".replace(",", ".")


def _limpiar(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove lq_* keys from user_data to prevent stale state."""
    if context.user_data is not None:
        context.user_data.pop("lq_socio", None)
        context.user_data.pop("lq_tipo", None)
        context.user_data.pop("lq_monto", None)


def _encontrar_resumen_socio(
    resumen: ResumenSplitSocios, nombre: str
) -> ResumenSocio | None:
    for socio in resumen.por_socio:
        if socio.nombre.lower() == nombre.lower():
            return socio
    return None


def _pantalla_confirmacion(
    nombre_socio: str, tipo: str, monto: Dinero
) -> str:
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")
    tipo_label = (
        obtener_mensaje("liquidar_socio.tipo_total")
        if tipo == "total"
        else obtener_mensaje("liquidar_socio.tipo_parcial")
    )
    monto_fmt = _fmt_cop(monto.monto)
    nombre_cap = nombre_socio.capitalize()
    return formatear_html(
        obtener_mensaje("liquidar_socio.confirmacion"),
        nombre=nombre_cap,
        tipo=tipo_label,
        monto=monto_fmt,
        fecha=fecha_str,
    )


def _teclado_confirmacion() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("liquidar_socio.boton_confirmar"),
                    callback_data=_CB_CONFIRMAR,
                ),
                InlineKeyboardButton(
                    obtener_mensaje("liquidar_socio.boton_cancelar"),
                    callback_data=_CB_CANCELAR,
                ),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Entry point: /liquidar_socio
# ---------------------------------------------------------------------------


@requiere_propietario_conv
async def cmd_liquidar_socio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — shows partner selection buttons."""
    socios_config_repo = context.bot_data.get("socios_config_repo")
    if socios_config_repo is None:
        logger.error("socios_config_repo not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("liquidar_socio.error_config"),
                parse_mode="HTML",
            )
        return ConversationHandler.END

    socios = socios_config_repo.listar()
    if not socios:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("liquidar_socio.sin_socios"),
                parse_mode="HTML",
            )
        return ConversationHandler.END

    botones: list[list[InlineKeyboardButton]] = []
    for socio in socios:
        nombre = socio.nombre
        botones.append(
            [InlineKeyboardButton(nombre.capitalize(), callback_data=f"{_CB_SOCIO_PREFIX}{nombre}")]
        )
    botones.append(
        [
            InlineKeyboardButton(
                obtener_mensaje("liquidar_socio.boton_cancelar"), callback_data=_CB_CANCELAR
            )
        ]
    )

    markup = InlineKeyboardMarkup(botones)
    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("liquidar_socio.seleccionar_socio"),
            reply_markup=markup,
            parse_mode="HTML",
        )
    return LQ_SELECCION


# ---------------------------------------------------------------------------
# LQ_SELECCION state — partner chosen via callback lq_socio:{nombre}
# ---------------------------------------------------------------------------


async def handle_lq_seleccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle partner selection."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    data: str = ""
    if query is not None:
        data = query.data or ""

    if not data.startswith(_CB_SOCIO_PREFIX):
        _limpiar(context)
        return ConversationHandler.END

    nombre = data[len(_CB_SOCIO_PREFIX):]
    if context.user_data is not None:
        context.user_data["lq_socio"] = nombre

    # Get the pending amount for this partner
    split_service = context.bot_data.get("split_socios_service")
    pendiente_fmt = "—"
    if split_service is not None:
        resumen: ResumenSplitSocios = split_service.calcular_acumulado()
        socio_resumen = _encontrar_resumen_socio(resumen, nombre)
        if socio_resumen is not None:
            pendiente_fmt = _fmt_cop(socio_resumen.pendiente.monto)

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("liquidar_socio.boton_total").format(pendiente=pendiente_fmt),
                    callback_data=_CB_TOTAL,
                )
            ],
            [
                InlineKeyboardButton(
                    obtener_mensaje("liquidar_socio.boton_parcial"), callback_data=_CB_PARCIAL
                )
            ],
            [
                InlineKeyboardButton(
                    obtener_mensaje("liquidar_socio.boton_cancelar"), callback_data=_CB_CANCELAR
                )
            ],
        ]
    )
    if update.effective_message:
        await update.effective_message.reply_text(
            formatear_html(
                obtener_mensaje("liquidar_socio.seleccionar_tipo"), nombre=nombre.capitalize()
            ),
            reply_markup=markup,
            parse_mode="HTML",
        )
    return LQ_TIPO


# ---------------------------------------------------------------------------
# LQ_TIPO state — total or partial choice
# ---------------------------------------------------------------------------


async def handle_lq_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle payment type selection (total or partial)."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    data: str = ""
    if query is not None:
        data = query.data or ""

    user_data = context.user_data or {}
    nombre: str = user_data.get("lq_socio", "")

    if data == _CB_TOTAL:
        # Determine pending amount for this socio
        split_service = context.bot_data.get("split_socios_service")
        monto = Dinero(0)
        if split_service is not None:
            resumen: ResumenSplitSocios = split_service.calcular_acumulado()
            socio_resumen = _encontrar_resumen_socio(resumen, nombre)
            if socio_resumen is not None:
                monto = socio_resumen.pendiente

        if context.user_data is not None:
            context.user_data["lq_tipo"] = "total"
            context.user_data["lq_monto"] = monto

        texto = _pantalla_confirmacion(nombre, "total", monto)
        if update.effective_message:
            await update.effective_message.reply_text(
                texto,
                reply_markup=_teclado_confirmacion(),
                parse_mode="HTML",
            )
        return LQ_CONFIRMAR

    if data == _CB_PARCIAL:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("liquidar_socio.pedir_monto"),
                parse_mode="HTML",
            )
        return LQ_MONTO

    if data == _CB_CANCELAR:
        _limpiar(context)
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("liquidar_socio.cancelado"), parse_mode="HTML"
            )
        return ConversationHandler.END

    _limpiar(context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# LQ_MONTO state — text input for partial amount
# ---------------------------------------------------------------------------


async def handle_lq_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle partial amount text input."""
    if update.effective_message is None:
        _limpiar(context)
        return ConversationHandler.END

    texto: str = ""
    if update.message is not None:
        texto = (update.message.text or "").strip()

    monto_decimal: Decimal | None = parsear_monto(texto)
    if monto_decimal is None:
        await update.effective_message.reply_text(
            obtener_mensaje("liquidar_socio.error_monto"),
            parse_mode="HTML",
        )
        return LQ_MONTO

    monto = Dinero(monto_decimal)
    if context.user_data is not None:
        context.user_data["lq_tipo"] = "parcial"
        context.user_data["lq_monto"] = monto

    user_data = context.user_data or {}
    nombre: str = user_data.get("lq_socio", "")

    texto_confirm = _pantalla_confirmacion(nombre, "parcial", monto)
    await update.effective_message.reply_text(
        texto_confirm,
        reply_markup=_teclado_confirmacion(),
        parse_mode="HTML",
    )
    return LQ_CONFIRMAR


# ---------------------------------------------------------------------------
# LQ_CONFIRMAR state — final confirmation
# ---------------------------------------------------------------------------


async def handle_lq_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Persist the payment and end the conversation."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user_data = context.user_data or {}
    nombre_socio: str | None = user_data.get("lq_socio")
    tipo: str | None = user_data.get("lq_tipo")
    monto: Dinero | None = user_data.get("lq_monto")

    if not nombre_socio or not tipo or monto is None:
        logger.error("handle_lq_confirmar: incomplete state — lq_socio/lq_tipo/lq_monto missing")
        _limpiar(context)
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("liquidar_socio.estado_incompleto"),
                parse_mode="HTML",
            )
        return ConversationHandler.END

    pagos_socio_repo = context.bot_data.get("pagos_socio_repo")
    if pagos_socio_repo is None:
        logger.error("pagos_socio_repo not found in bot_data — wiring error")
        _limpiar(context)
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("liquidar_socio.error_config"),
                parse_mode="HTML",
            )
        return ConversationHandler.END

    pago = PagoSocio(
        id=uuid.uuid4(),
        nombre_socio=nombre_socio,
        monto=monto,
        fecha=datetime.date.today(),
        tipo=tipo,
        nota=None,
        registrado_en=datetime.datetime.now(datetime.UTC),
    )
    pagos_socio_repo.guardar(pago)

    _limpiar(context)

    tipo_label = (
        obtener_mensaje("liquidar_socio.tipo_total")
        if tipo == "total"
        else obtener_mensaje("liquidar_socio.tipo_parcial")
    )
    monto_fmt = _fmt_cop(monto.monto)
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")
    if update.effective_message:
        await update.effective_message.reply_text(
            formatear_html(
                obtener_mensaje("liquidar_socio.registrado"),
                nombre=nombre_socio.capitalize(),
                tipo=tipo_label,
                monto=monto_fmt,
                fecha=fecha_str,
            ),
            parse_mode="HTML",
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Cancel handler — valid in any state
# ---------------------------------------------------------------------------


async def handle_lq_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation from any state."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    _limpiar(context)
    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("liquidar_socio.cancelado"), parse_mode="HTML"
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def registrar_handlers(app: object) -> None:
    """Register the /liquidar_socio ConversationHandler with the Application."""
    assert isinstance(app, Application)

    conv = ConversationHandler(
        entry_points=[CommandHandler("liquidar_socio", cmd_liquidar_socio)],
        states={
            LQ_SELECCION: [
                CallbackQueryHandler(handle_lq_seleccion, pattern=f"^{_CB_SOCIO_PREFIX}"),
                CallbackQueryHandler(handle_lq_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
            LQ_TIPO: [
                CallbackQueryHandler(
                    handle_lq_tipo,
                    pattern=f"^({_CB_TOTAL}|{_CB_PARCIAL}|{_CB_CANCELAR})$",
                ),
            ],
            LQ_MONTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lq_monto),
                CallbackQueryHandler(handle_lq_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
            LQ_CONFIRMAR: [
                CallbackQueryHandler(handle_lq_confirmar, pattern=f"^{_CB_CONFIRMAR}$"),
                CallbackQueryHandler(handle_lq_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_lq_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            CommandHandler("cancelar", handle_lq_cancelar),
            CommandHandler("start", cmd_start),
        ],
        name="liquidar_socio",
        persistent=False,
    )

    app.add_handler(conv, group=10)
