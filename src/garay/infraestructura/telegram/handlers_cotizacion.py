"""Handlers for the cotizacion (service quote) flow.

States 300-309, group=12 ConversationHandler.
All callback patterns use the cot_ prefix (exception: entry 'inicio_cotizacion').
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.cotizacion.contexto import ContextoCotizacion
from garay.dominio.servicios.entidades import Servicio

logger = logging.getLogger(__name__)

_BOGOTA = ZoneInfo("America/Bogota")

# ---------------------------------------------------------------------------
# State constants (300-309, verified free block)
# ---------------------------------------------------------------------------

COT_FAMILIA: int = 300
COT_TOUR: int = 301
COT_FECHA: int = 302
COT_FECHA_TEXTO: int = 303
COT_IDIOMA: int = 304
COT_NOMBRE: int = 305
COT_EMAIL: int = 306
COT_ADULTOS: int = 307
COT_NINOS: int = 308
COT_CONFIRMAR: int = 309

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hoy_bogota() -> datetime.date:
    return datetime.datetime.now(_BOGOTA).date()


def _teclado_fecha_cotizacion() -> InlineKeyboardMarkup:
    """Date picker keyboard — NO back button (SC-G01)."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Ayer", callback_data="cot_ayer")],
            [InlineKeyboardButton("📅 Antes de ayer", callback_data="cot_antes_ayer")],
            [InlineKeyboardButton("✏️ Otra fecha", callback_data="cot_otra")],
        ]
    )


def _teclado_fecha_texto_cotizacion() -> InlineKeyboardMarkup:
    """Free-text date sub-state keyboard — HAS back button (SC-G02)."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("← Atrás", callback_data="cot_fecha_volver")],
        ]
    )


def _ctx(context: ContextTypes.DEFAULT_TYPE) -> ContextoCotizacion:
    """Retrieve the ContextoCotizacion from user_data."""
    user_data: dict[str, object] = context.user_data  # type: ignore[assignment]
    return user_data["cotizacion_ctx"]  # type: ignore[return-value]


async def _responder(
    update: Update,
    texto: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()
        kwargs = {"text": texto}
        if markup:
            kwargs["reply_markup"] = markup  # type: ignore[assignment]
        await update.callback_query.edit_message_text(**kwargs)  # type: ignore[arg-type]
    elif update.message is not None:
        if markup:
            await update.message.reply_text(texto, reply_markup=markup)
        else:
            await update.message.reply_text(texto)


# ---------------------------------------------------------------------------
# Entry handler — auth gate
# ---------------------------------------------------------------------------


async def handle_inicio_cotizacion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Entry point: validate admin, init ContextoCotizacion, show familia keyboard."""
    from garay.infraestructura.telegram.auth import es_admin_o_propietario

    user = update.effective_user
    if user is None or not await es_admin_o_propietario(user.id, context):
        if update.callback_query is not None:
            await update.callback_query.answer()
        return ConversationHandler.END

    # Resolve vendedor_nombre: try freelancer repo, fall back to Telegram full_name
    vendedor_nombre: str | None = None
    freelancer_repo = context.bot_data.get("freelancer_repo")
    if freelancer_repo is not None:
        try:
            freelancer = freelancer_repo.buscar_por_telegram_id(user.id)
            if freelancer is not None:
                vendedor_nombre = getattr(freelancer, "nombre", None) or user.full_name
        except Exception:
            pass
    if vendedor_nombre is None:
        vendedor_nombre = user.full_name

    ctx = ContextoCotizacion(vendedor_nombre=vendedor_nombre)
    context.user_data["cotizacion_ctx"] = ctx  # type: ignore[index]

    # Build familia keyboard from active services
    servicio_repo = context.bot_data.get("servicio_repo")
    servicios = servicio_repo.listar_activos() if servicio_repo else []
    categorias: list[str] = sorted(
        {s.categoria for s in servicios if s.categoria},
    )

    if not categorias:
        await _responder(update, "No hay familias de tours disponibles.")
        return ConversationHandler.END

    filas = [
        [InlineKeyboardButton(cat, callback_data=f"cot_fam:{i}")]
        for i, cat in enumerate(categorias)
    ]
    # Store categorias list for lookup in handle_cot_familia
    context.user_data["_cot_categorias"] = categorias  # type: ignore[index]
    context.user_data["_cot_servicios"] = servicios  # type: ignore[index]

    await _responder(update, "¿Qué familia de tour?", InlineKeyboardMarkup(filas))
    return COT_FAMILIA


# ---------------------------------------------------------------------------
# COT_FAMILIA
# ---------------------------------------------------------------------------


async def handle_cot_familia(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User selected a tour family."""
    if update.callback_query is None:
        return COT_FAMILIA

    data = update.callback_query.data or ""
    idx = int(data.split(":")[1])
    user_data: dict[str, object] = context.user_data  # type: ignore[assignment]
    categorias: list[str] = user_data.get("_cot_categorias", [])  # type: ignore[assignment]
    servicios: list[Servicio] = user_data.get("_cot_servicios", [])  # type: ignore[assignment]

    if idx >= len(categorias):
        await update.callback_query.answer("Selección inválida.")
        return COT_FAMILIA

    familia = categorias[idx]
    ctx = _ctx(context)
    ctx.familia_seleccionada = familia

    tours_familia = [s for s in servicios if s.categoria == familia]
    if not tours_familia:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("No hay tours en esa familia.")
        return ConversationHandler.END

    filas = [
        [InlineKeyboardButton(s.nombre, callback_data=f"cot_tour:{s.numero}")]
        for s in tours_familia
    ]
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"Tours de *{familia}*:", reply_markup=InlineKeyboardMarkup(filas)
    )
    return COT_TOUR


# ---------------------------------------------------------------------------
# COT_TOUR
# ---------------------------------------------------------------------------


async def handle_cot_tour(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User selected a specific tour; populate pricing from Servicio."""
    if update.callback_query is None:
        return COT_TOUR

    data = update.callback_query.data or ""
    numero = int(data.split(":")[1])
    user_data_tour: dict[str, object] = context.user_data  # type: ignore[assignment]
    servicios_tour: list[Servicio] = user_data_tour.get("_cot_servicios", [])  # type: ignore[assignment]
    servicio: Servicio | None = next(
        (s for s in servicios_tour if s.numero == numero), None
    )

    if servicio is None:
        await update.callback_query.answer("Tour no encontrado.")
        return COT_TOUR

    ctx = _ctx(context)
    ctx.destinos_numeros = [servicio.numero]
    ctx.destinos_nombres = [servicio.nombre]
    ctx.precio_adulto = servicio.precio_neto_adulto
    ctx.precio_nino = servicio.precio_neto_nino

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"Tour: *{servicio.nombre}*\n\n¿Fecha del tour?",
        reply_markup=_teclado_fecha_cotizacion(),
    )
    return COT_FECHA


# ---------------------------------------------------------------------------
# COT_FECHA handlers
# ---------------------------------------------------------------------------


async def handle_cot_ayer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User selected 'Ayer'."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    ayer = _hoy_bogota() - datetime.timedelta(days=1)
    ctx = _ctx(context)
    ctx.fecha_salida = datetime.datetime(ayer.year, ayer.month, ayer.day)
    await _responder(update, "¿Idioma de la cotización?", _teclado_idioma())
    return COT_IDIOMA


async def handle_cot_antes_ayer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User selected 'Antes de ayer'."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    antes_ayer = _hoy_bogota() - datetime.timedelta(days=2)
    ctx = _ctx(context)
    ctx.fecha_salida = datetime.datetime(
        antes_ayer.year, antes_ayer.month, antes_ayer.day
    )
    await _responder(update, "¿Idioma de la cotización?", _teclado_idioma())
    return COT_IDIOMA


async def handle_cot_otra(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User pressed 'Otra fecha' — show free-text sub-state with back button."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    await _responder(
        update,
        "Escribe la fecha del tour (formato DD/MM/AAAA):",
        _teclado_fecha_texto_cotizacion(),
    )
    return COT_FECHA_TEXTO


async def handle_cot_fecha_volver(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Back button from COT_FECHA_TEXTO → return to COT_FECHA."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    ctx = _ctx(context)
    tour = ", ".join(ctx.destinos_nombres) if ctx.destinos_nombres else "Tour"
    await _responder(
        update,
        f"Tour: *{tour}*\n\n¿Fecha del tour?",
        _teclado_fecha_cotizacion(),
    )
    return COT_FECHA


async def handle_cot_fecha_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User typed a date in DD/MM/YYYY format."""
    from garay.aplicacion.comun.fechas import parsear_fecha

    texto = (update.message.text or "").strip() if update.message else ""
    fecha = parsear_fecha(texto)
    if fecha is None:
        if update.message is not None:
            await update.message.reply_text(
                "Fecha inválida. Usa el formato DD/MM/AAAA.",
                reply_markup=_teclado_fecha_texto_cotizacion(),
            )
        return COT_FECHA_TEXTO

    ctx = _ctx(context)
    ctx.fecha_salida = fecha
    await _responder(update, "¿Idioma de la cotización?", _teclado_idioma())
    return COT_IDIOMA


# ---------------------------------------------------------------------------
# COT_IDIOMA
# ---------------------------------------------------------------------------


def _teclado_idioma() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇨🇴 Español", callback_data="cot_idioma:es"),
                InlineKeyboardButton("🇺🇸 English", callback_data="cot_idioma:en"),
            ]
        ]
    )


async def handle_cot_idioma(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.callback_query is None:
        return COT_IDIOMA

    data = update.callback_query.data or ""
    idioma = data.split(":")[1]  # "es" or "en"
    ctx = _ctx(context)
    ctx.factura_idioma = idioma
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("¿Nombre del cliente?")
    return COT_NOMBRE


# ---------------------------------------------------------------------------
# COT_NOMBRE, COT_EMAIL, COT_ADULTOS, COT_NINOS
# ---------------------------------------------------------------------------


async def handle_cot_nombre(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    texto = (update.message.text or "").strip() if update.message else ""
    if not texto:
        if update.message:
            await update.message.reply_text("El nombre no puede estar vacío:")
        return COT_NOMBRE

    ctx = _ctx(context)
    ctx.cliente_nombre = texto

    teclado_omitir = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Omitir", callback_data="cot_omitir_email")]]
    )
    if update.message:
        await update.message.reply_text(
            "¿Correo electrónico del cliente? (o Omitir)", reply_markup=teclado_omitir
        )
    return COT_EMAIL


async def handle_cot_email(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    texto = (update.message.text or "").strip() if update.message else ""
    ctx = _ctx(context)
    ctx.cliente_email = texto if texto else None
    if update.message:
        await update.message.reply_text("¿Cuántos adultos?")
    return COT_ADULTOS


async def handle_cot_email_omitir(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.callback_query is not None:
        await update.callback_query.answer()
    ctx = _ctx(context)
    ctx.cliente_email = None
    if update.callback_query is not None:
        await update.callback_query.edit_message_text("¿Cuántos adultos?")
    return COT_ADULTOS


async def handle_cot_adultos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    texto = (update.message.text or "").strip() if update.message else ""
    try:
        adultos = int(texto)
        if adultos < 1:
            raise ValueError
    except ValueError:
        if update.message:
            await update.message.reply_text("Debe ser un número entero mayor a 0:")
        return COT_ADULTOS

    ctx = _ctx(context)
    ctx.adultos = adultos

    teclado_omitir = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Omitir (0 niños)", callback_data="cot_omitir_ninos")]]
    )
    if update.message:
        await update.message.reply_text(
            "¿Cuántos niños? (o Omitir)", reply_markup=teclado_omitir
        )
    return COT_NINOS


async def handle_cot_ninos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    texto = (update.message.text or "").strip() if update.message else ""
    try:
        ninos = int(texto)
        if ninos < 0:
            raise ValueError
    except ValueError:
        if update.message:
            await update.message.reply_text("Debe ser un número entero (0 o más):")
        return COT_NINOS

    ctx = _ctx(context)
    ctx.ninos = ninos
    await _mostrar_confirmacion(update, ctx)
    return COT_CONFIRMAR


async def handle_cot_ninos_omitir(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.callback_query is not None:
        await update.callback_query.answer()
    ctx = _ctx(context)
    ctx.ninos = 0
    await _mostrar_confirmacion_cb(update, ctx)
    return COT_CONFIRMAR


async def _mostrar_confirmacion(update: Update, ctx: ContextoCotizacion) -> None:
    texto = _resumen_cotizacion(ctx)
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="cot_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cot_cancelar"),
            ]
        ]
    )
    if update.message:
        await update.message.reply_text(texto, reply_markup=markup, parse_mode="HTML")


async def _mostrar_confirmacion_cb(update: Update, ctx: ContextoCotizacion) -> None:
    texto = _resumen_cotizacion(ctx)
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="cot_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cot_cancelar"),
            ]
        ]
    )
    if update.callback_query is not None:
        await update.callback_query.edit_message_text(
            texto, reply_markup=markup, parse_mode="HTML"
        )


def _resumen_cotizacion(ctx: ContextoCotizacion) -> str:
    fecha = (
        ctx.fecha_salida.strftime("%d/%m/%Y") if ctx.fecha_salida else "—"
    )
    tour = ", ".join(ctx.destinos_nombres) if ctx.destinos_nombres else "—"
    from garay.aplicacion.cotizacion.servicio import _fmt_cop

    return (
        f"<b>Resumen de cotización</b>\n\n"
        f"Tour: <b>{tour}</b>\n"
        f"Fecha: {fecha}\n"
        f"Idioma: {ctx.factura_idioma.upper()}\n"
        f"Cliente: {ctx.cliente_nombre or '—'}\n"
        f"Email: {ctx.cliente_email or 'Sin email'}\n"
        f"Adultos: {ctx.adultos or 0}\n"
        f"Niños: {ctx.ninos}\n"
        f"Total: <b>{_fmt_cop(ctx.valor_total)}</b>"
    )


# ---------------------------------------------------------------------------
# COT_CONFIRMAR
# ---------------------------------------------------------------------------


async def handle_cot_confirmar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Generate HTML, optionally send email, send Telegram notification, end flow."""
    from garay.aplicacion.cotizacion.servicio import _fmt_cop
    from garay.mensajes.catalogo import Idioma, obtener_mensaje

    if update.callback_query is not None:
        await update.callback_query.answer()
        data = update.callback_query.data or ""
        if "cancelar" in data:
            return await _cancelar_desde_confirmar(update, context)

    ctx = _ctx(context)
    cot_service = context.bot_data.get("cotizacion_service")
    html = cot_service.generar(ctx) if cot_service else ""

    notificador_email = context.bot_data.get("notificador_email")
    idioma = ctx.factura_idioma if ctx.factura_idioma in ("es", "en") else "es"

    if ctx.cliente_email and notificador_email is not None:
        asunto_key = f"cotizacion.asunto_email.{idioma}"
        catalog_idioma = Idioma.ES if idioma == "es" else Idioma.EN
        asunto = obtener_mensaje(asunto_key, catalog_idioma)
        await asyncio.to_thread(
            notificador_email.enviar,
            ctx.cliente_email,
            asunto,
            html,
        )
        estado_email_raw = obtener_mensaje("cotizacion.estado_email_enviado")
        estado_email = estado_email_raw.format(email=ctx.cliente_email)
    else:
        estado_email = obtener_mensaje("cotizacion.estado_email_sin")

    tour = ", ".join(ctx.destinos_nombres) if ctx.destinos_nombres else "—"
    fecha = ctx.fecha_salida.strftime("%d/%m/%Y") if ctx.fecha_salida else "—"
    notif_template = obtener_mensaje("cotizacion.notificacion_telegram")
    notif_text = notif_template.format(
        tour=tour,
        cliente=ctx.cliente_nombre or "—",
        fecha=fecha,
        idioma=idioma.upper(),
        adultos=ctx.adultos or 0,
        ninos=ctx.ninos,
        total=_fmt_cop(ctx.valor_total),
        estado_email=estado_email,
    )

    chat_id = (
        update.effective_chat.id if update.effective_chat else None
    )
    if chat_id is not None:
        await context.bot.send_message(
            chat_id=chat_id,
            text=notif_text,
            parse_mode="HTML",
        )

    # Clean up
    context.user_data.pop("cotizacion_ctx", None)  # type: ignore[union-attr]
    context.user_data.pop("_cot_categorias", None)  # type: ignore[union-attr]
    context.user_data.pop("_cot_servicios", None)  # type: ignore[union-attr]

    return ConversationHandler.END


async def _cancelar_desde_confirmar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    from garay.mensajes.catalogo import obtener_mensaje

    context.user_data.pop("cotizacion_ctx", None)  # type: ignore[union-attr]
    context.user_data.pop("_cot_categorias", None)  # type: ignore[union-attr]
    context.user_data.pop("_cot_servicios", None)  # type: ignore[union-attr]
    if update.callback_query is not None:
        await update.callback_query.edit_message_text(
            obtener_mensaje("cotizacion.cancelado")
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /cancelar fallback
# ---------------------------------------------------------------------------


async def cmd_cancelar_cotizacion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    from garay.mensajes.catalogo import obtener_mensaje

    context.user_data.pop("cotizacion_ctx", None)  # type: ignore[union-attr]
    context.user_data.pop("_cot_categorias", None)  # type: ignore[union-attr]
    context.user_data.pop("_cot_servicios", None)  # type: ignore[union-attr]
    if update.message is not None:
        await update.message.reply_text(obtener_mensaje("cotizacion.cancelado"))
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# ConversationHandler definition
# ---------------------------------------------------------------------------

_TEXT = filters.TEXT & ~filters.COMMAND


_CB = CallbackQueryHandler

cotizacion_conv_handler = ConversationHandler(
    entry_points=[
        _CB(handle_inicio_cotizacion, pattern="^inicio_cotizacion$")
    ],
    states={
        COT_FAMILIA: [_CB(handle_cot_familia, pattern="^cot_fam:")],
        COT_TOUR: [_CB(handle_cot_tour, pattern="^cot_tour:")],
        COT_FECHA: [
            _CB(handle_cot_ayer, pattern="^cot_ayer$"),
            _CB(handle_cot_antes_ayer, pattern="^cot_antes_ayer$"),
            _CB(handle_cot_otra, pattern="^cot_otra$"),
        ],
        COT_FECHA_TEXTO: [
            MessageHandler(_TEXT, handle_cot_fecha_texto),
            _CB(handle_cot_fecha_volver, pattern="^cot_fecha_volver$"),
        ],
        COT_IDIOMA: [_CB(handle_cot_idioma, pattern="^cot_idioma:")],
        COT_NOMBRE: [MessageHandler(_TEXT, handle_cot_nombre)],
        COT_EMAIL: [
            MessageHandler(_TEXT, handle_cot_email),
            _CB(handle_cot_email_omitir, pattern="^cot_omitir_email$"),
        ],
        COT_ADULTOS: [MessageHandler(_TEXT, handle_cot_adultos)],
        COT_NINOS: [
            MessageHandler(_TEXT, handle_cot_ninos),
            _CB(handle_cot_ninos_omitir, pattern="^cot_omitir_ninos$"),
        ],
        COT_CONFIRMAR: [
            _CB(handle_cot_confirmar, pattern="^cot_(confirmar|cancelar)$")
        ],
    },
    fallbacks=[
        CommandHandler("cancelar", cmd_cancelar_cotizacion),
        CommandHandler("start", cmd_cancelar_cotizacion),
    ],
)

__all__ = ["cotizacion_conv_handler"]
