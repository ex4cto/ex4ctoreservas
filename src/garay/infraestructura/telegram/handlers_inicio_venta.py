"""Handlers for the date-selector screen shown at the start of /nueva_venta.

New states:
  INICIO_VENTA         = 33  — shows "Nueva venta hoy" / "Otra fecha" picker
  FECHA_RETROACTIVA    = 34  — shows Ayer / Antes de ayer / Otra fecha / Atrás
  FECHA_RETROACTIVA_TEXTO = 35 — waits for free-text date input

Flow:
  /nueva_venta → handle_iniciar_venta (INICIO_VENTA)
    → inicio_hoy   → handle_inicio_hoy → METODO_INPUT  (no override)
    → inicio_otra_fecha → handle_inicio_otra_fecha → FECHA_RETROACTIVA
        → fecha_ayer       → stores override → METODO_INPUT
        → fecha_antes_ayer → stores override → METODO_INPUT
        → fecha_otra       → handle_fecha_retroactiva_otra → FECHA_RETROACTIVA_TEXTO
            → <text>  → handle_fecha_retroactiva_texto
                valid   → stores override → METODO_INPUT
                invalid → re-ask → FECHA_RETROACTIVA_TEXTO
        → inicio_volver → handle_inicio_volver → INICIO_VENTA (clears override)
      (also from METODO_INPUT and FECHA_RETROACTIVA)
"""

from __future__ import annotations

import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from garay.aplicacion.comun.fechas import parsear_fecha

logger = logging.getLogger(__name__)

# New PTB integer states (highest existing is 32 = FACTURA_IDIOMA).
INICIO_VENTA: int = 33
FECHA_RETROACTIVA: int = 34
FECHA_RETROACTIVA_TEXTO: int = 35

_TZ_BOGOTA = datetime.timezone(datetime.timedelta(hours=-5))


def _teclado_inicio(mostrar_otra_fecha: bool) -> InlineKeyboardMarkup:
    filas = [[InlineKeyboardButton("📅 Nueva venta (hoy)", callback_data="inicio_hoy")]]
    if mostrar_otra_fecha:
        filas.append([InlineKeyboardButton("🗓 Otra fecha", callback_data="inicio_otra_fecha")])
    return InlineKeyboardMarkup(filas)


def _teclado_fecha_retroactiva() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Ayer", callback_data="fecha_ayer")],
            [InlineKeyboardButton("📅 Antes de ayer", callback_data="fecha_antes_ayer")],
            [InlineKeyboardButton("✏️ Otra fecha", callback_data="fecha_otra")],
            [InlineKeyboardButton("← Atrás", callback_data="inicio_volver")],
        ]
    )


async def _mostrar_selector_inicio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Send (or edit) the initial date-choice screen and return INICIO_VENTA."""
    from garay.infraestructura.telegram.auth import es_admin_o_propietario

    texto = "¿Cuándo es la venta?"
    user = update.effective_user
    mostrar_otra_fecha = (
        user is not None
        and await es_admin_o_propietario(user.id, context)
    )
    markup = _teclado_inicio(mostrar_otra_fecha)
    if update.callback_query is not None:
        await update.callback_query.edit_message_text(texto, reply_markup=markup)
    elif update.message is not None:
        await update.message.reply_text(texto, reply_markup=markup)
    elif update.effective_message is not None:
        await update.effective_message.reply_text(texto, reply_markup=markup)
    return INICIO_VENTA


async def handle_inicio_hoy(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User chose 'Nueva venta hoy' — initialize FSM context and proceed to METODO_INPUT."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    from garay.infraestructura.telegram.handlers import _lanzar_flujo_venta

    return await _lanzar_flujo_venta(update, context)


async def handle_inicio_otra_fecha(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User chose 'Otra fecha' — show the date sub-picker.

    Stale-callback defence: if a FREELANCER somehow reaches this handler
    (e.g. stale inline keyboard), show an alert and return INICIO_VENTA
    without setting any override.
    """
    from garay.infraestructura.telegram.auth import es_admin_o_propietario
    from garay.mensajes.catalogo import obtener_mensaje

    user = update.effective_user
    autorizado = (
        user is not None
        and await es_admin_o_propietario(user.id, context)
    )
    if not autorizado:
        if update.callback_query is not None:
            await update.callback_query.answer(
                obtener_mensaje("venta.retroactiva_sin_acceso"),
                show_alert=True,
            )
        return INICIO_VENTA

    # Authorized path: show sub-picker
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "¿Cuál es la fecha de la venta?",
            reply_markup=_teclado_fecha_retroactiva(),
        )
    return FECHA_RETROACTIVA


def _hoy_bogota() -> datetime.date:
    """Return today's date in the Bogota timezone (UTC-5, no DST)."""
    return datetime.datetime.now(tz=_TZ_BOGOTA).date()


def _date_to_datetime(d: datetime.date) -> datetime.datetime:
    """Convert a date to a datetime at midnight (no tzinfo) — matches parsear_fecha output."""
    return datetime.datetime(d.year, d.month, d.day, 0, 0, 0)


async def handle_fecha_ayer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User chose 'Ayer' — save the override and proceed to METODO_INPUT."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    ayer = _hoy_bogota() - datetime.timedelta(days=1)
    if context.user_data is not None:
        context.user_data["fecha_venta_override"] = _date_to_datetime(ayer)
    from garay.infraestructura.telegram.handlers import _lanzar_flujo_venta

    return await _lanzar_flujo_venta(update, context)


async def handle_fecha_antes_ayer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User chose 'Antes de ayer' — save the override and proceed to METODO_INPUT."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    antes_ayer = _hoy_bogota() - datetime.timedelta(days=2)
    if context.user_data is not None:
        context.user_data["fecha_venta_override"] = _date_to_datetime(antes_ayer)
    from garay.infraestructura.telegram.handlers import _lanzar_flujo_venta

    return await _lanzar_flujo_venta(update, context)


async def handle_fecha_retroactiva_otra(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User chose 'Otra fecha' — prompt for free-text date input."""
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Ingresa la fecha en formato DD/MM/YYYY:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("← Atrás", callback_data="inicio_volver")]]
            ),
        )
    return FECHA_RETROACTIVA_TEXTO


async def handle_fecha_retroactiva_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Process a free-text date input.

    Valid → save override and return METODO_INPUT.
    Invalid → re-ask and return FECHA_RETROACTIVA_TEXTO.
    """
    texto = ""
    if update.message is not None and update.message.text:
        texto = update.message.text.strip()

    fecha = parsear_fecha(texto)
    if fecha is None:
        if update.message is not None:
            await update.message.reply_text(
                "Formato inválido. Usá DD/MM/YYYY (ej: 15/09/2026):",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("← Atrás", callback_data="inicio_volver")]]
                ),
            )
        return FECHA_RETROACTIVA_TEXTO

    if context.user_data is not None:
        context.user_data["fecha_venta_override"] = fecha
    from garay.infraestructura.telegram.handlers import _lanzar_flujo_venta

    return await _lanzar_flujo_venta(update, context)


async def handle_inicio_volver(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """User pressed '← Atrás' — clear any override and return to the start screen."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    if context.user_data is not None:
        context.user_data.pop("fecha_venta_override", None)
    return await _mostrar_selector_inicio(update, context)
