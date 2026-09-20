"""Handlers for /resumen_divisiones — period-scoped partner split summary.

States 310-313, group=13, callback prefix rep_s:.
Provides an inline calendar date-range picker (no external library).
"""

from __future__ import annotations

import calendar
import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from garay.aplicacion.socios.split import ResumenSplitPeriodo
from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.telegram.auth import requiere_admin_o_propietario_conv
from garay.infraestructura.telegram.handlers import cmd_start
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants (310-313, verified free block after cotizacion 300-309)
# ---------------------------------------------------------------------------

DIV_MENU: int = 310
DIV_CAL_DESDE: int = 311
DIV_CAL_HASTA: int = 312
DIV_RESULT: int = 313

# ---------------------------------------------------------------------------
# Callback prefixes
# ---------------------------------------------------------------------------

_CB_MENU = "rep_s:menu:"       # rep_s:menu:hoy | ayer | periodo | cancel
_CB_CAL = "rep_s:cal:"         # rep_s:cal:desde:yyyy-mm | rep_s:cal:hasta:yyyy-mm
_CB_DIA = "rep_s:dia:"         # rep_s:dia:desde:yyyy-mm-dd | rep_s:dia:hasta:yyyy-mm-dd
_CB_ATRAS = "rep_s:atras:"     # rep_s:atras:menu | rep_s:atras:hasta

# user_data keys
_KEY_DESDE = "div_desde"   # datetime.date | None
_KEY_MES = "div_mes"       # "yyyy-mm" string — currently viewed month

_MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_cop(d: Dinero) -> str:
    return "$" + f"{int(d.monto):,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Calendar builder
# ---------------------------------------------------------------------------


def _teclado_calendario(year: int, month: int, step: str) -> InlineKeyboardMarkup:
    """Build the PTB inline calendar keyboard for a given month.

    step: "desde" | "hasta" — used in callback_data to distinguish the two
    calendar invocations and correctly route day selections.
    """
    rows: list[list[InlineKeyboardButton]] = []

    # Row 0: month header (non-interactive)
    mes_label = f"{_MESES_ES[month]} {year}"
    rows.append([InlineKeyboardButton(mes_label, callback_data="rep_s:noop")])

    # Day-of-week header
    dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
    rows.append([InlineKeyboardButton(d, callback_data="rep_s:noop") for d in dias])

    # Day buttons
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="rep_s:noop"))
            else:
                fecha = datetime.date(year, month, day)
                row.append(
                    InlineKeyboardButton(
                        str(day),
                        callback_data=f"rep_s:dia:{step}:{fecha.isoformat()}",
                    )
                )
        rows.append(row)

    # Navigation row
    nav_row: list[InlineKeyboardButton] = []
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    nav_row.append(
        InlineKeyboardButton(
            f"◀ {_MESES_ES[prev_month]} {prev_year}",
            callback_data=f"rep_s:cal:{step}:{prev_year}-{prev_month:02d}",
        )
    )
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    nav_row.append(
        InlineKeyboardButton(
            f"{_MESES_ES[next_month]} {next_year} ▶",
            callback_data=f"rep_s:cal:{step}:{next_year}-{next_month:02d}",
        )
    )
    rows.append(nav_row)

    # Back button
    back_target = "menu" if step == "desde" else "hasta"
    rows.append(
        [InlineKeyboardButton("← Atrás", callback_data=f"rep_s:atras:{back_target}")]
    )

    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Result renderer
# ---------------------------------------------------------------------------


def _render_resultado(resultado: ResumenSplitPeriodo, periodo_label: str) -> str:
    """Render the period result as an HTML string."""
    if resultado.ventas_count == 0:
        return obtener_mensaje("resumen_divisiones.sin_datos")

    titulo = obtener_mensaje("resumen_divisiones.titulo").format(periodo=periodo_label)
    ventas_row = obtener_mensaje("resumen_divisiones.ventas_row").format(
        n=resultado.ventas_count,
        bruto=_fmt_cop(resultado.total_bruto),
    )
    freelancer_row = obtener_mensaje("resumen_divisiones.freelancer_row").format(
        monto=_fmt_cop(resultado.total_comisiones_freelancer),
    )
    agencia_row = obtener_mensaje("resumen_divisiones.agencia_row").format(
        monto=_fmt_cop(resultado.total_agencia),
    )

    lineas = [titulo, "", ventas_row, "", freelancer_row, agencia_row]

    socios = resultado.por_socio
    for i, s in enumerate(socios):
        arbol = "└" if i == len(socios) - 1 else "├"
        # Pad names for alignment (up to 8 chars)
        padding = " " * max(0, 8 - len(s.nombre))
        lineas.append(
            obtener_mensaje("resumen_divisiones.socio_row").format(
                arbol=arbol,
                nombre=s.nombre,
                padding=padding,
                monto=_fmt_cop(s.acumulado),
            )
        )

    # Total ganancia = agency net + freelancer commissions
    ganancia = resultado.total_agencia + resultado.total_comisiones_freelancer
    ganancia_row = obtener_mensaje("resumen_divisiones.ganancia_row").format(
        monto=_fmt_cop(ganancia),
    )
    lineas.append(ganancia_row)

    return "\n".join(lineas)


def _periodo_label_hoy() -> str:
    hoy = datetime.date.today()
    return obtener_mensaje("resumen_divisiones.periodo_hoy").format(
        fecha=hoy.strftime("%d/%m/%Y")
    )


def _periodo_label_ayer() -> str:
    ayer = datetime.date.today() - datetime.timedelta(days=1)
    return obtener_mensaje("resumen_divisiones.periodo_ayer").format(
        fecha=ayer.strftime("%d/%m/%Y")
    )


def _periodo_label_rango(desde: datetime.date, hasta: datetime.date) -> str:
    return obtener_mensaje("resumen_divisiones.periodo_rango").format(
        desde=desde.strftime("%d/%m/%Y"),
        hasta=hasta.strftime("%d/%m/%Y"),
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@requiere_admin_o_propietario_conv
async def cmd_resumen_divisiones(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point: show the 4-button menu."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_hoy"),
                    callback_data=f"{_CB_MENU}hoy",
                ),
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_ayer"),
                    callback_data=f"{_CB_MENU}ayer",
                ),
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_periodo"),
                    callback_data=f"{_CB_MENU}periodo",
                ),
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_cancelar"),
                    callback_data=f"{_CB_MENU}cancel",
                ),
            ]
        ]
    )
    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("resumen_divisiones.titulo").format(periodo="…"),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    return DIV_MENU


async def handle_div_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle menu button selection: hoy, ayer, periodo, cancel."""
    cq = update.callback_query
    if cq is None:
        return DIV_MENU
    await cq.answer()

    data: str = cq.data or ""

    if data == f"{_CB_MENU}cancel":
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.cancelado"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data == f"{_CB_MENU}periodo":
        hoy = datetime.date.today()
        context.user_data[_KEY_MES] = f"{hoy.year}-{hoy.month:02d}"  # type: ignore[index]
        context.user_data.pop(_KEY_DESDE, None)  # type: ignore[union-attr]
        teclado = _teclado_calendario(hoy.year, hoy.month, "desde")
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.cal_inicio"),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return DIV_CAL_DESDE

    # Quick paths: hoy / ayer
    split_service = context.bot_data.get("split_service")
    if split_service is None:
        logger.error("split_service not found in bot_data")
        return ConversationHandler.END

    if data == f"{_CB_MENU}hoy":
        hoy = datetime.date.today()
        resultado = split_service.calcular_periodo(hoy, hoy)
        texto = _render_resultado(resultado, _periodo_label_hoy())
    elif data == f"{_CB_MENU}ayer":
        ayer = datetime.date.today() - datetime.timedelta(days=1)
        resultado = split_service.calcular_periodo(ayer, ayer)
        texto = _render_resultado(resultado, _periodo_label_ayer())
    else:
        return DIV_MENU

    await cq.edit_message_text(texto, parse_mode="HTML")
    return ConversationHandler.END


async def handle_div_cal(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle month navigation in the calendar grid."""
    cq = update.callback_query
    if cq is None:
        return DIV_CAL_DESDE
    await cq.answer()

    data: str = cq.data or ""
    # data format: rep_s:cal:desde:yyyy-mm  or  rep_s:cal:hasta:yyyy-mm
    parts = data.split(":")
    # parts: ["rep_s", "cal", step, "yyyy-mm"]
    if len(parts) < 4:
        return DIV_CAL_DESDE

    step = parts[2]
    year_month = parts[3]
    context.user_data[_KEY_MES] = year_month  # type: ignore[index]

    try:
        year, month = int(year_month[:4]), int(year_month[5:7])
    except (ValueError, IndexError):
        return DIV_CAL_DESDE

    teclado = _teclado_calendario(year, month, step)
    prompt = (
        obtener_mensaje("resumen_divisiones.cal_inicio")
        if step == "desde"
        else obtener_mensaje("resumen_divisiones.cal_fin")
    )
    await cq.edit_message_text(prompt, reply_markup=teclado, parse_mode="HTML")

    return DIV_CAL_DESDE if step == "desde" else DIV_CAL_HASTA


async def handle_div_dia(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle day selection in the calendar grid."""
    cq = update.callback_query
    if cq is None:
        return DIV_CAL_DESDE
    await cq.answer.__self__ if hasattr(cq.answer, "__self__") else None

    data: str = cq.data or ""
    # data format: rep_s:dia:desde:yyyy-mm-dd  or  rep_s:dia:hasta:yyyy-mm-dd
    parts = data.split(":")
    # parts: ["rep_s", "dia", step, "yyyy", "mm", "dd"]  (ISO date uses -)
    # Actually the ISO date yyyy-mm-dd uses "-" so after split(":") we get
    # ["rep_s", "dia", "desde", "2026-09-05"] — 4 parts, last is the date string
    if len(parts) < 4:
        await cq.answer("Dato inválido.")
        return DIV_CAL_DESDE

    step = parts[2]
    fecha_str = parts[3]

    try:
        fecha = datetime.date.fromisoformat(fecha_str)
    except ValueError:
        await cq.answer("Fecha inválida.")
        return DIV_CAL_DESDE if step == "desde" else DIV_CAL_HASTA

    if step == "desde":
        context.user_data[_KEY_DESDE] = fecha  # type: ignore[index]
        # Move to hasta picker
        teclado = _teclado_calendario(fecha.year, fecha.month, "hasta")
        context.user_data[_KEY_MES] = f"{fecha.year}-{fecha.month:02d}"  # type: ignore[index]
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.cal_fin"),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return DIV_CAL_HASTA

    # step == "hasta"
    desde: datetime.date | None = context.user_data.get(_KEY_DESDE)  # type: ignore[union-attr]
    if desde is None:
        # Edge case: desde lost — restart
        hoy = datetime.date.today()
        teclado = _teclado_calendario(hoy.year, hoy.month, "desde")
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.cal_inicio"),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return DIV_CAL_DESDE

    if fecha < desde:
        await cq.answer(obtener_mensaje("resumen_divisiones.error_fecha_fin"))
        return DIV_CAL_HASTA

    # Both dates valid — compute result
    split_service = context.bot_data.get("split_service")
    if split_service is None:
        logger.error("split_service not found in bot_data")
        return ConversationHandler.END

    resultado = split_service.calcular_periodo(desde, fecha)
    texto = _render_resultado(resultado, _periodo_label_rango(desde, fecha))
    await cq.edit_message_text(texto, parse_mode="HTML")
    return ConversationHandler.END


async def handle_div_atras(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle the ← Atrás button in the calendar."""
    cq = update.callback_query
    if cq is None:
        return DIV_MENU
    await cq.answer()

    data: str = cq.data or ""
    # data format: rep_s:atras:menu | rep_s:atras:hasta
    parts = data.split(":")
    target = parts[2] if len(parts) >= 3 else "menu"

    if target == "hasta":
        # Back from hasta → restore desde picker
        desde: datetime.date | None = context.user_data.get(_KEY_DESDE)  # type: ignore[union-attr]
        if desde is not None:
            teclado = _teclado_calendario(desde.year, desde.month, "desde")
            context.user_data[_KEY_MES] = f"{desde.year}-{desde.month:02d}"  # type: ignore[index]
        else:
            hoy = datetime.date.today()
            teclado = _teclado_calendario(hoy.year, hoy.month, "desde")
            context.user_data[_KEY_MES] = f"{hoy.year}-{hoy.month:02d}"  # type: ignore[index]
        context.user_data.pop(_KEY_DESDE, None)  # type: ignore[union-attr]
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.cal_inicio"),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return DIV_CAL_DESDE

    # Back to menu
    hoy = datetime.date.today()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_hoy"),
                    callback_data=f"{_CB_MENU}hoy",
                ),
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_ayer"),
                    callback_data=f"{_CB_MENU}ayer",
                ),
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_periodo"),
                    callback_data=f"{_CB_MENU}periodo",
                ),
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.menu_cancelar"),
                    callback_data=f"{_CB_MENU}cancel",
                ),
            ]
        ]
    )
    await cq.edit_message_text(
        obtener_mensaje("resumen_divisiones.titulo").format(periodo="…"),
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return DIV_MENU


# ---------------------------------------------------------------------------
# ConversationHandler factory
# ---------------------------------------------------------------------------


def build_divisiones_conv_handler() -> ConversationHandler:  # type: ignore[type-arg]
    """Wire and return the /resumen_divisiones ConversationHandler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("resumen_divisiones", cmd_resumen_divisiones),
        ],
        states={
            DIV_MENU: [
                CallbackQueryHandler(handle_div_menu, pattern=r"^rep_s:menu:"),
            ],
            DIV_CAL_DESDE: [
                CallbackQueryHandler(handle_div_cal, pattern=r"^rep_s:cal:desde:"),
                CallbackQueryHandler(handle_div_dia, pattern=r"^rep_s:dia:desde:"),
                CallbackQueryHandler(handle_div_atras, pattern=r"^rep_s:atras:"),
            ],
            DIV_CAL_HASTA: [
                CallbackQueryHandler(handle_div_cal, pattern=r"^rep_s:cal:hasta:"),
                CallbackQueryHandler(handle_div_dia, pattern=r"^rep_s:dia:hasta:"),
                CallbackQueryHandler(handle_div_atras, pattern=r"^rep_s:atras:"),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", _fallback_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )


async def _fallback_cancelar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("resumen_divisiones.cancelado")
        )
    return ConversationHandler.END
