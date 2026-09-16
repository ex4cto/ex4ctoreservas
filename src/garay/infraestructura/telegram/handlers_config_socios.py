"""PTB handlers for /config_socios — partner configuration editor (E6).

Only accessible to owners (propietarios). Allows viewing and editing partner
percentages and Telegram IDs.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

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

from garay.dominio.socios.entidades import SocioConfig
from garay.infraestructura.telegram.auth import requiere_propietario_conv
from garay.infraestructura.telegram.handlers import cmd_start

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 260-264
# ---------------------------------------------------------------------------

CS_MENU: int = 260
CS_PORC_INPUT: int = 261
CS_TG_SELECCION: int = 262
CS_TG_INPUT: int = 263

# ---------------------------------------------------------------------------
# Callback data constants
# ---------------------------------------------------------------------------

_CB_EDITAR_PORC: str = "cs_editar_porc"
_CB_EDITAR_TG: str = "cs_editar_tg"
_CB_TG_PREFIX: str = "cs_tg:"
_CB_CANCELAR: str = "cs_cancelar"

# ---------------------------------------------------------------------------
# Emojis per partner name
# ---------------------------------------------------------------------------

_EMOJIS: dict[str, str] = {
    "empresa": "🏢",
    "garay": "🧑",
    "ryan": "🧑",
}
_EMOJI_DEFAULT: str = "👤"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emoji_socio(nombre: str) -> str:
    return _EMOJIS.get(nombre.lower(), _EMOJI_DEFAULT)


def _fmt_tg(telegram_id: int | None) -> str:
    if telegram_id is None:
        return "no configurado"
    return f"@{telegram_id}"


def _construir_texto_config(socios: list[SocioConfig]) -> str:
    if not socios:
        return "⚙️ <b>Configuración de socios</b>\n\n⚠️ No hay socios configurados."

    lineas = ["⚙️ <b>Configuración de socios</b>\n"]
    for socio in socios:
        emoji = _emoji_socio(socio.nombre)
        nombre_cap = socio.nombre.capitalize()
        porc = (
            int(socio.porcentaje)
            if socio.porcentaje == int(socio.porcentaje)
            else socio.porcentaje
        )
        tg = _fmt_tg(socio.telegram_id)
        lineas.append(f"{emoji} {nombre_cap}: {porc}% | Telegram: {tg}")

    return "\n".join(lineas)


def _teclado_menu(tiene_socios: bool) -> InlineKeyboardMarkup:
    botones: list[list[InlineKeyboardButton]] = []
    if tiene_socios:
        botones.append(
            [InlineKeyboardButton("🔢 Editar porcentajes", callback_data=_CB_EDITAR_PORC)]
        )
        botones.append(
            [InlineKeyboardButton("📱 Editar Telegram ID", callback_data=_CB_EDITAR_TG)]
        )
    botones.append(
        [InlineKeyboardButton("❌ Cancelar", callback_data=_CB_CANCELAR)]
    )
    return InlineKeyboardMarkup(botones)


def _limpiar(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data is not None:
        context.user_data.pop("cs_socio_editando", None)


# ---------------------------------------------------------------------------
# Entry point: /config_socios
# ---------------------------------------------------------------------------


@requiere_propietario_conv
async def cmd_config_socios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — shows current partner configuration."""
    socios_config_repo = context.bot_data.get("socios_config_repo")
    if socios_config_repo is None:
        logger.error("socios_config_repo not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                "Error de configuración. Contacta al administrador.",
                parse_mode="HTML",
            )
        return ConversationHandler.END

    socios: list[SocioConfig] = socios_config_repo.listar()
    texto = _construir_texto_config(socios)
    markup = _teclado_menu(tiene_socios=bool(socios))

    if update.effective_message:
        await update.effective_message.reply_text(
            texto,
            reply_markup=markup,
            parse_mode="HTML",
        )
    return CS_MENU


# ---------------------------------------------------------------------------
# CS_MENU state — action selection
# ---------------------------------------------------------------------------


async def handle_cs_editar_porc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback 'cs_editar_porc' — ask for new percentages."""
    query = update.callback_query
    if query is not None:
        await query.answer()
        await query.edit_message_text(
            "Ingresa los porcentajes en orden empresa,garay,ryan separados por coma.\n"
            "Deben sumar 100. Ejemplo: <code>50,25,25</code>",
            parse_mode="HTML",
        )
    return CS_PORC_INPUT


async def handle_cs_editar_tg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback 'cs_editar_tg' — show partner picker for Telegram ID edit."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    socios_config_repo = context.bot_data.get("socios_config_repo")
    socios: list[SocioConfig] = socios_config_repo.listar() if socios_config_repo else []

    botones: list[list[InlineKeyboardButton]] = []
    for socio in socios:
        nombre_cap = socio.nombre.capitalize()
        botones.append(
            [InlineKeyboardButton(nombre_cap, callback_data=f"{_CB_TG_PREFIX}{socio.nombre}")]
        )
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data=_CB_CANCELAR)])
    markup = InlineKeyboardMarkup(botones)

    if query is not None:
        await query.edit_message_text(
            "Selecciona el socio para editar su Telegram ID:",
            reply_markup=markup,
            parse_mode="HTML",
        )
    return CS_TG_SELECCION


async def handle_cs_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel from any state."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    _limpiar(context)
    if update.effective_message:
        await update.effective_message.reply_text("❌ Cancelado.", parse_mode="HTML")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# CS_PORC_INPUT state — parse and validate percentages
# ---------------------------------------------------------------------------


async def handle_cs_porc_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the raw text input with three percentages."""
    if update.effective_message is None:
        return ConversationHandler.END

    texto: str = ""
    if update.message is not None:
        texto = (update.message.text or "").strip()

    partes = [p.strip() for p in texto.split(",")]
    if len(partes) != 3:
        await update.effective_message.reply_text(
            "⚠️ Formato inválido o suma ≠ 100. Intenta de nuevo:",
            parse_mode="HTML",
        )
        return CS_PORC_INPUT

    decimals: list[Decimal] = []
    for parte in partes:
        try:
            val = Decimal(parte)
        except InvalidOperation:
            await update.effective_message.reply_text(
                "⚠️ Formato inválido o suma ≠ 100. Intenta de nuevo:",
                parse_mode="HTML",
            )
            return CS_PORC_INPUT
        if val < 0:
            await update.effective_message.reply_text(
                "⚠️ Formato inválido o suma ≠ 100. Intenta de nuevo:",
                parse_mode="HTML",
            )
            return CS_PORC_INPUT
        decimals.append(val)

    if sum(decimals) != Decimal("100"):
        await update.effective_message.reply_text(
            "⚠️ Formato inválido o suma ≠ 100. Intenta de nuevo:",
            parse_mode="HTML",
        )
        return CS_PORC_INPUT

    socios_config_repo = context.bot_data.get("socios_config_repo")
    if socios_config_repo is None:
        await update.effective_message.reply_text(
            "Error de configuración. Contacta al administrador.",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    socios: list[SocioConfig] = socios_config_repo.listar()

    # Apply new percentages positionally (empresa=0, garay=1, ryan=2)
    # If there are exactly 3 socios, map by position; otherwise fall back
    for i, socio in enumerate(socios):
        if i < len(decimals):
            nuevo = SocioConfig(
                nombre=socio.nombre,
                porcentaje=decimals[i],
                telegram_id=socio.telegram_id,
            )
            socios_config_repo.guardar(nuevo)

    # Build summary line
    partes_fmt = " | ".join(
        f"{socios[i].nombre.capitalize()} {int(decimals[i])}%"
        for i in range(len(socios))
        if i < len(decimals)
    )
    await update.effective_message.reply_text(
        f"✅ Porcentajes actualizados: {partes_fmt}",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# CS_TG_SELECCION state — partner chosen via callback cs_tg:{nombre}
# ---------------------------------------------------------------------------


async def handle_cs_tg_seleccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle partner selection for Telegram ID editing."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    data: str = ""
    if query is not None:
        data = query.data or ""

    if not data.startswith(_CB_TG_PREFIX):
        _limpiar(context)
        return ConversationHandler.END

    nombre = data[len(_CB_TG_PREFIX):]
    if context.user_data is not None:
        context.user_data["cs_socio_editando"] = nombre

    nombre_cap = nombre.capitalize()
    if update.effective_message:
        await update.effective_message.reply_text(
            f"Ingresa el Telegram ID de {nombre_cap} (número entero, o 'none' para eliminar):",
            parse_mode="HTML",
        )
    return CS_TG_INPUT


# ---------------------------------------------------------------------------
# CS_TG_INPUT state — parse Telegram ID (integer or "none")
# ---------------------------------------------------------------------------


async def handle_cs_tg_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input with the new Telegram ID."""
    if update.effective_message is None:
        return ConversationHandler.END

    texto: str = ""
    if update.message is not None:
        texto = (update.message.text or "").strip()

    telegram_id: int | None

    if texto.lower() == "none":
        telegram_id = None
    else:
        try:
            telegram_id = int(texto)
        except ValueError:
            await update.effective_message.reply_text(
                "⚠️ Ingresa un número entero o 'none':",
                parse_mode="HTML",
            )
            return CS_TG_INPUT

    user_data = context.user_data or {}
    nombre: str = user_data.get("cs_socio_editando", "")

    socios_config_repo = context.bot_data.get("socios_config_repo")
    if socios_config_repo is None:
        await update.effective_message.reply_text(
            "Error de configuración. Contacta al administrador.",
            parse_mode="HTML",
        )
        _limpiar(context)
        return ConversationHandler.END

    socio: SocioConfig | None = socios_config_repo.buscar_por_nombre(nombre)
    if socio is None:
        await update.effective_message.reply_text(
            f"⚠️ Socio '{nombre}' no encontrado.",
            parse_mode="HTML",
        )
        _limpiar(context)
        return ConversationHandler.END

    nuevo = SocioConfig(
        nombre=socio.nombre,
        porcentaje=socio.porcentaje,
        telegram_id=telegram_id,
    )
    socios_config_repo.guardar(nuevo)
    _limpiar(context)

    nombre_cap = nombre.capitalize()
    if telegram_id is None:
        msg = f"✅ Telegram ID de {nombre_cap} eliminado."
    else:
        msg = f"✅ Telegram ID de {nombre_cap} actualizado."

    await update.effective_message.reply_text(msg, parse_mode="HTML")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def registrar_handlers(app: object) -> None:
    """Register the /config_socios ConversationHandler with the Application."""
    assert isinstance(app, Application)

    conv = ConversationHandler(
        entry_points=[CommandHandler("config_socios", cmd_config_socios)],
        states={
            CS_MENU: [
                CallbackQueryHandler(handle_cs_editar_porc, pattern=f"^{_CB_EDITAR_PORC}$"),
                CallbackQueryHandler(handle_cs_editar_tg, pattern=f"^{_CB_EDITAR_TG}$"),
                CallbackQueryHandler(handle_cs_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
            CS_PORC_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cs_porc_input),
                CallbackQueryHandler(handle_cs_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
            CS_TG_SELECCION: [
                CallbackQueryHandler(handle_cs_tg_seleccion, pattern=f"^{_CB_TG_PREFIX}"),
                CallbackQueryHandler(handle_cs_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
            CS_TG_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cs_tg_input),
                CallbackQueryHandler(handle_cs_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_cs_cancelar, pattern=f"^{_CB_CANCELAR}$"),
            CommandHandler("cancelar", handle_cs_cancelar),
            CommandHandler("start", cmd_start),
        ],
        name="config_socios",
        persistent=False,
    )

    app.add_handler(conv, group=11)
