"""Handlers for /resumen_divisiones — period-scoped partner split summary.

States 310-313, group=13, callback prefix rep_s:.
Provides an inline calendar date-range picker (no external library).
States 315-316: liquidaciones de freelancers.
"""

from __future__ import annotations

import calendar
import datetime
import logging
import uuid as _uuid_mod

import html

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.comun.formato import fmt_cop
from garay.aplicacion.comun.montos import parsear_monto
from garay.aplicacion.liquidaciones.servicio import (
    LiquidarFreelancerService,
    RegistrarPagoFreelancerComando,
    ResultadoCalculoLiquidacion,
    _dias_solapados,
)
from garay.aplicacion.socios.split import (
    ResumenSocio,
    ResumenSplitPeriodo,
    ResumenSplitSocios,
    ResumenVentaDetalle,
)
from garay.dominio.comun.dinero import Dinero
from garay.dominio.liquidaciones.entidades import PagoFreelancer
from garay.dominio.socios.entidades import PagoSocio
from garay.config.settings import obtener_settings
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
DIV_VENTA: int = 314
DIV_LIQ_FREELANCER: int = 315   # Showing freelancer list with their commissions
DIV_LIQ_CONFIRMAR: int = 316    # Showing confirmation with desglose + overlap warning
DIV_SOC_SELECCION: int = 317   # Socio selection list
DIV_SOC_CONFIRMAR: int = 318   # Desglose + confirm/monto input

# ---------------------------------------------------------------------------
# Callback prefixes
# ---------------------------------------------------------------------------

_CB_MENU = "rep_s:menu:"       # rep_s:menu:hoy | ayer | periodo | cancel | ver
_CB_CAL = "rep_s:cal:"         # rep_s:cal:desde:yyyy-mm  or  rep_s:cal:hasta:yyyy-mm
_CB_DIA = "rep_s:dia:"         # rep_s:dia:desde:yyyy-mm-dd | rep_s:dia:hasta:yyyy-mm-dd
_CB_ATRAS = "rep_s:atras:"     # rep_s:atras:menu | rep_s:atras:hasta | rep_s:atras:resultado
_CB_VENTA = "rep_s:venta:"     # rep_s:venta:{index}
_CB_LIQ = "rep_s:liq:"         # rep_s:liq:start | rep_s:liq:fl:{uuid} | rep_s:liq:confirmar:{uuid} | rep_s:liq:cancelar | rep_s:liq:atras

# user_data keys
_KEY_DESDE = "div_desde"           # datetime.date | None
_KEY_MES = "div_mes"               # "yyyy-mm" string — currently viewed month
_KEY_HOY_SEL = "div_hoy_sel"       # bool — Hoy checkbox state
_KEY_AYER_SEL = "div_ayer_sel"     # bool — Ayer checkbox state
_KEY_VENTAS = "div_ventas"         # list[ResumenVentaDetalle] — for drill-down
_KEY_RESULTADO = "div_resultado"   # ResumenSplitPeriodo — cached for Atrás
_KEY_PERIODO_LABEL = "div_periodo_label"  # str — period label for Atrás
_KEY_LIQ_DESDE = "div_liq_desde"          # date — liquidation period start
_KEY_LIQ_HASTA = "div_liq_hasta"          # date — liquidation period end
_KEY_LIQ_FREELANCERS = "div_liq_fls"      # list[tuple[str, uuid.UUID, Dinero]] — (nombre, id, comision)
_KEY_LIQ_RESULTADO = "div_liq_resultado"  # ResultadoCalculoLiquidacion
_KEY_SOC_NOMBRE = "div_soc_nombre"   # str — selected socio name
_KEY_SOC_MONTO  = "div_soc_monto"    # Dinero | None — partial amount entered

_MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------




def _fmt_k(monto: int) -> str:
    """Format an integer COP amount as $Xk or $X.XXXk (e.g. 600000 → $600k)."""
    miles = monto // 1000
    return "$" + f"{miles:,}".replace(",", ".") + "k"


def _venta_btn_label(venta: ResumenVentaDetalle) -> str:
    """Build inline button label: '{dd/mm}  {primer_nombre}  ${k_format}'.

    dd/mm is the registration date when available; falls back to tour date.
    """
    fecha_display = venta.registrado_en.date() if venta.registrado_en else venta.fecha
    dd_mm = fecha_display.strftime("%d/%m")
    primer_nombre = (venta.vendedor_nombre or "—").split()[0]
    k_label = _fmt_k(int(venta.valor_bruto.monto))
    return f"{dd_mm}  {primer_nombre}  {k_label}"


# ---------------------------------------------------------------------------
# Menu keyboard builder
# ---------------------------------------------------------------------------


def _teclado_menu(hoy_sel: bool, ayer_sel: bool) -> InlineKeyboardMarkup:
    """Build the main menu keyboard with Hoy/Ayer as toggle checkboxes.

    Row 0: [⬜/✅ Hoy] [⬜/✅ Ayer] [📊 Período] [✖ Cancelar]
    Row 1: [📊 Ver resumen] (full width)
    """
    hoy_icon = "✅" if hoy_sel else "⬜"
    ayer_icon = "✅" if ayer_sel else "⬜"

    row0 = [
        InlineKeyboardButton(
            f"{hoy_icon} {obtener_mensaje('resumen_divisiones.menu_hoy')}",
            callback_data=f"{_CB_MENU}hoy",
        ),
        InlineKeyboardButton(
            f"{ayer_icon} {obtener_mensaje('resumen_divisiones.menu_ayer')}",
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
    row1 = [
        InlineKeyboardButton(
            obtener_mensaje("resumen_divisiones.menu_ver"),
            callback_data=f"{_CB_MENU}ver",
        ),
    ]
    return InlineKeyboardMarkup([row0, row1])


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


def _render_resultado(
    resultado: ResumenSplitPeriodo,
    periodo_label: str,
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Render the period result as (HTML text, optional InlineKeyboardMarkup).

    The markup contains one button per sale when ventas_detalle is present.
    Returns (sin_datos_text, None) when there are no sales.
    """
    if resultado.ventas_count == 0:
        return obtener_mensaje("resumen_divisiones.sin_datos"), None

    titulo = obtener_mensaje("resumen_divisiones.titulo").format(periodo=periodo_label)
    ventas_row = obtener_mensaje("resumen_divisiones.ventas_row").format(
        n=resultado.ventas_count,
        bruto=fmt_cop(resultado.total_bruto),
    )
    agencia_row = obtener_mensaje("resumen_divisiones.agencia_row").format(
        monto=fmt_cop(resultado.total_agencia),
    )

    lineas = [titulo, "", ventas_row, ""]

    # Per-freelancer breakdown (replaces aggregate freelancer row)
    freelancers = resultado.por_freelancer
    if freelancers:
        lineas.append(obtener_mensaje("resumen_divisiones.freelancer_header"))
        for i, fl in enumerate(freelancers):
            arbol = "└" if i == len(freelancers) - 1 else "├"
            lineas.append(
                obtener_mensaje("resumen_divisiones.freelancer_item").format(
                    arbol=arbol,
                    nombre=fl.nombre,
                    monto=fmt_cop(fl.comision),
                )
            )
    else:
        freelancer_row = obtener_mensaje("resumen_divisiones.freelancer_row").format(
            monto=fmt_cop(resultado.total_comisiones_freelancer),
        )
        lineas.append(freelancer_row)

    lineas.append(agencia_row)

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
                monto=fmt_cop(s.acumulado),
            )
        )

    # Total ganancia = agency net + freelancer commissions
    ganancia = resultado.total_agencia + resultado.total_comisiones_freelancer
    ganancia_row = obtener_mensaje("resumen_divisiones.ganancia_row").format(
        monto=fmt_cop(ganancia),
    )
    lineas.append(ganancia_row)

    texto = "\n".join(lineas)

    # Build per-sale buttons if detail available
    markup: InlineKeyboardMarkup | None = None
    if resultado.ventas_detalle:
        rows = [
            [
                InlineKeyboardButton(
                    _venta_btn_label(venta),
                    callback_data=f"rep_s:venta:{i}",
                )
            ]
            for i, venta in enumerate(resultado.ventas_detalle)
        ]
        rows.append(
            [
                InlineKeyboardButton(
                    "💸 Pagos pendientes",
                    callback_data="rep_s:liq:start",
                )
            ]
        )
        if resultado.por_socio:
            rows.append([InlineKeyboardButton(
                obtener_mensaje("resumen_divisiones.soc_btn_entrada"),
                callback_data="rep_s:soc:start",
            )])
        rows.append(
            [InlineKeyboardButton(
                obtener_mensaje("resumen_divisiones.btn_cerrar"),
                callback_data="rep_s:menu:cerrar",
            )]
        )
        markup = InlineKeyboardMarkup(rows)

    return texto, markup


def _render_detalle_venta(venta: ResumenVentaDetalle) -> tuple[str, InlineKeyboardMarkup]:
    """Render per-sale drill-down detail as (HTML text, InlineKeyboardMarkup with Atrás)."""
    fecha_str = venta.fecha.strftime("%d/%m")
    nombre = venta.vendedor_nombre or "—"
    titulo = obtener_mensaje("resumen_divisiones.detalle_titulo").format(
        fecha=fecha_str, nombre=nombre
    )
    bruto = obtener_mensaje("resumen_divisiones.detalle_bruto").format(
        monto=fmt_cop(venta.valor_bruto)
    )

    lineas = [titulo, "", bruto]

    # Commission items — only show when > 0
    tiene_comisiones = any([
        venta.desglose_vendedor > Dinero(0),
        venta.desglose_cerrador > Dinero(0),
        venta.desglose_punto > Dinero(0),
    ])
    if tiene_comisiones:
        lineas.append(obtener_mensaje("resumen_divisiones.detalle_comisiones_header"))
        if venta.desglose_vendedor > Dinero(0) and venta.vendedor_nombre:
            lineas.append(
                obtener_mensaje("resumen_divisiones.detalle_comision_item").format(
                    nombre=venta.vendedor_nombre,
                    monto=fmt_cop(venta.desglose_vendedor),
                )
            )
        if venta.desglose_cerrador > Dinero(0) and venta.cerrador_nombre:
            lineas.append(
                obtener_mensaje("resumen_divisiones.detalle_comision_item").format(
                    nombre=venta.cerrador_nombre,
                    monto=fmt_cop(venta.desglose_cerrador),
                )
            )
        if venta.desglose_punto > Dinero(0):
            lineas.append(
                obtener_mensaje("resumen_divisiones.detalle_comision_item").format(
                    nombre="Punto de venta",
                    monto=fmt_cop(venta.desglose_punto),
                )
            )

    lineas.append(
        obtener_mensaje("resumen_divisiones.detalle_agencia").format(
            monto=fmt_cop(venta.desglose_agencia)
        )
    )

    if venta.saldo_pendiente > Dinero(0):
        lineas.append(
            obtener_mensaje("resumen_divisiones.detalle_saldo_pendiente").format(
                monto=fmt_cop(venta.saldo_pendiente)
            )
        )

    # Per-sale split
    socios = venta.split_socios
    for i, s in enumerate(socios):
        arbol = "└" if i == len(socios) - 1 else "├"
        padding = " " * max(0, 8 - len(s.nombre))
        lineas.append(
            obtener_mensaje("resumen_divisiones.socio_row").format(
                arbol=arbol,
                nombre=s.nombre,
                padding=padding,
                monto=fmt_cop(s.acumulado),
            )
        )

    texto = "\n".join(lineas)

    atras_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("resumen_divisiones.btn_atras"),
                    callback_data="rep_s:atras:resultado",
                )
            ]
        ]
    )
    return texto, atras_markup


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
    """Entry point: show the toggle-checkbox menu."""
    context.user_data[_KEY_HOY_SEL] = False  # type: ignore[index]
    context.user_data[_KEY_AYER_SEL] = False  # type: ignore[index]

    keyboard = _teclado_menu(False, False)
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
    """Handle menu button selection: hoy (toggle), ayer (toggle), ver, periodo, cancel."""
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

    # Toggle Hoy checkbox
    if data == f"{_CB_MENU}hoy":
        current: bool = bool(context.user_data.get(_KEY_HOY_SEL, False))  # type: ignore[union-attr]
        context.user_data[_KEY_HOY_SEL] = not current  # type: ignore[index]
        hoy_sel: bool = context.user_data[_KEY_HOY_SEL]  # type: ignore[index]
        ayer_sel: bool = bool(context.user_data.get(_KEY_AYER_SEL, False))  # type: ignore[union-attr]
        await cq.edit_message_reply_markup(
            reply_markup=_teclado_menu(hoy_sel, ayer_sel)
        )
        return DIV_MENU

    # Toggle Ayer checkbox
    if data == f"{_CB_MENU}ayer":
        current_ayer: bool = bool(context.user_data.get(_KEY_AYER_SEL, False))  # type: ignore[union-attr]
        context.user_data[_KEY_AYER_SEL] = not current_ayer  # type: ignore[index]
        hoy_sel_a: bool = bool(context.user_data.get(_KEY_HOY_SEL, False))  # type: ignore[union-attr]
        ayer_sel_a: bool = context.user_data[_KEY_AYER_SEL]  # type: ignore[index]
        await cq.edit_message_reply_markup(
            reply_markup=_teclado_menu(hoy_sel_a, ayer_sel_a)
        )
        return DIV_MENU

    # Ver resumen — compute from selections
    if data == f"{_CB_MENU}ver":
        hoy_selected: bool = bool(context.user_data.get(_KEY_HOY_SEL, False))  # type: ignore[union-attr]
        ayer_selected: bool = bool(context.user_data.get(_KEY_AYER_SEL, False))  # type: ignore[union-attr]

        if not hoy_selected and not ayer_selected:
            await cq.answer(
                obtener_mensaje("resumen_divisiones.nada_seleccionado"),
                show_alert=True,
            )
            return DIV_MENU

        hoy = datetime.date.today()
        ayer = hoy - datetime.timedelta(days=1)

        if hoy_selected and ayer_selected:
            desde = ayer
            hasta = hoy
            periodo_label = _periodo_label_rango(ayer, hoy)
        elif hoy_selected:
            desde = hoy
            hasta = hoy
            periodo_label = _periodo_label_hoy()
        else:
            desde = ayer
            hasta = ayer
            periodo_label = _periodo_label_ayer()

        split_service = context.bot_data.get("split_socios_service")
        if split_service is None:
            logger.error("split_socios_service not found in bot_data")
            return ConversationHandler.END

        resultado = split_service.calcular_periodo(desde, hasta)
        texto, markup = _render_resultado(resultado, periodo_label)

        if markup is not None:
            # Store data for drill-down
            context.user_data[_KEY_VENTAS] = list(resultado.ventas_detalle)  # type: ignore[index]
            context.user_data[_KEY_RESULTADO] = resultado  # type: ignore[index]
            context.user_data[_KEY_PERIODO_LABEL] = periodo_label  # type: ignore[index]
            context.user_data[_KEY_LIQ_DESDE] = desde  # type: ignore[index]
            context.user_data[_KEY_LIQ_HASTA] = hasta  # type: ignore[index]
            await cq.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
            return DIV_RESULT

        await cq.edit_message_text(texto, parse_mode="HTML")
        return ConversationHandler.END

    return DIV_MENU


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
    await cq.answer()

    data: str = cq.data or ""
    # data format: rep_s:dia:desde:yyyy-mm-dd  or  rep_s:dia:hasta:yyyy-mm-dd
    parts = data.split(":")
    # parts: ["rep_s", "dia", step, "yyyy-mm-dd"] — 4 parts, last is the date string
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
    split_service = context.bot_data.get("split_socios_service")
    if split_service is None:
        logger.error("split_socios_service not found in bot_data")
        return ConversationHandler.END

    resultado = split_service.calcular_periodo(desde, fecha)
    periodo_label = _periodo_label_rango(desde, fecha)
    texto, markup = _render_resultado(resultado, periodo_label)

    if markup is not None:
        context.user_data[_KEY_VENTAS] = list(resultado.ventas_detalle)  # type: ignore[index]
        context.user_data[_KEY_RESULTADO] = resultado  # type: ignore[index]
        context.user_data[_KEY_PERIODO_LABEL] = periodo_label  # type: ignore[index]
        context.user_data[_KEY_LIQ_DESDE] = desde  # type: ignore[index]
        context.user_data[_KEY_LIQ_HASTA] = fecha  # type: ignore[index]
        await cq.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
        return DIV_RESULT

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
    # data format: rep_s:atras:menu | rep_s:atras:hasta | rep_s:atras:resultado
    parts = data.split(":")
    target = parts[2] if len(parts) >= 3 else "menu"

    if target == "resultado":
        # Back from drill-down — restore result view with sale buttons
        resultado: ResumenSplitPeriodo | None = context.user_data.get(_KEY_RESULTADO)  # type: ignore[union-attr]
        periodo_label: str = context.user_data.get(_KEY_PERIODO_LABEL, "")  # type: ignore[union-attr]
        if resultado is not None:
            texto, markup = _render_resultado(resultado, periodo_label)
            await cq.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
        return DIV_RESULT

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
    hoy_sel: bool = bool(context.user_data.get(_KEY_HOY_SEL, False))  # type: ignore[union-attr]
    ayer_sel: bool = bool(context.user_data.get(_KEY_AYER_SEL, False))  # type: ignore[union-attr]
    keyboard = _teclado_menu(hoy_sel, ayer_sel)
    await cq.edit_message_text(
        obtener_mensaje("resumen_divisiones.titulo").format(periodo="…"),
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return DIV_MENU


async def handle_div_venta(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle sale drill-down: show per-sale detail with Atrás button."""
    cq = update.callback_query
    if cq is None:
        return DIV_RESULT
    await cq.answer()

    data: str = cq.data or ""
    # data format: rep_s:venta:{index}
    parts = data.split(":")
    try:
        index = int(parts[2]) if len(parts) >= 3 else 0
    except (ValueError, IndexError):
        return DIV_RESULT

    ventas: list[ResumenVentaDetalle] = context.user_data.get(_KEY_VENTAS, [])  # type: ignore[union-attr]
    if index < 0 or index >= len(ventas):
        return DIV_RESULT

    venta = ventas[index]
    texto, atras_markup = _render_detalle_venta(venta)
    await cq.edit_message_text(texto, parse_mode="HTML", reply_markup=atras_markup)
    return DIV_RESULT


async def handle_div_cerrar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User pressed Cerrar — remove keyboard and show /start hint."""
    cq = update.callback_query
    if cq is None:
        return ConversationHandler.END
    await cq.answer()
    await cq.edit_message_text(
        obtener_mensaje("resumen_divisiones.cerrado"),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Liquidaciones handlers
# ---------------------------------------------------------------------------


def _pax_label(adultos: int, ninos: int) -> str:
    """Build compact pax string: '2 adultos' or '2 adultos 1 niño'."""
    partes = [f"{adultos} adulto{'s' if adultos != 1 else ''}"]
    if ninos:
        partes.append(f"{ninos} niño{'s' if ninos != 1 else ''}")
    return " ".join(partes)


def _overlap_warning(solapados: list[PagoFreelancer], desde: datetime.date, hasta: datetime.date) -> str:
    """Build HTML warning text for overlapping payments."""
    lines: list[str] = []
    for s in solapados:
        dias = _dias_solapados(desde, hasta, s.desde, s.hasta)
        if not dias:
            continue
        dias_str = ", ".join(str(d.day) for d in dias[:5])
        if len(dias) > 5:
            dias_str += "…"
        periodo_anterior = f"{s.desde.strftime('%d/%m')} – {s.hasta.strftime('%d/%m')}"
        lines.append(
            obtener_mensaje("liquidaciones.advertencia_solapamiento").format(
                dias=dias_str,
                periodo_anterior=periodo_anterior,
            )
        )
    return "".join(lines)


async def handle_div_liq_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User pressed 💸 Pagos pendientes — show freelancer list with their commissions."""
    cq = update.callback_query
    if cq is None:
        return DIV_RESULT
    await cq.answer()

    resultado: ResumenSplitPeriodo | None = context.user_data.get(_KEY_RESULTADO)  # type: ignore[union-attr]
    if resultado is None or not resultado.por_freelancer:
        await cq.edit_message_text(
            obtener_mensaje("liquidaciones.sin_freelancers"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    desde: datetime.date | None = context.user_data.get(_KEY_LIQ_DESDE)  # type: ignore[union-attr]
    hasta: datetime.date | None = context.user_data.get(_KEY_LIQ_HASTA)  # type: ignore[union-attr]

    if desde is None or hasta is None:
        logger.error("div_liq_desde/hasta not set in user_data — cannot show liquidaciones")
        await cq.answer("Error interno: período no disponible.", show_alert=True)
        return DIV_RESULT

    # Build nombre→freelancer_id lookup
    freelancer_repo = context.bot_data.get("freelancer_repo")
    if freelancer_repo is None:
        logger.error("freelancer_repo not in bot_data")
        return ConversationHandler.END

    freelancers_activos = freelancer_repo.listar_activos()
    nombre_a_id: dict[str, _uuid_mod.UUID] = {f.nombre: f.id for f in freelancers_activos}

    # Map por_freelancer entries to (nombre, id, comision)
    fls: list[tuple[str, _uuid_mod.UUID, Dinero]] = []
    for fl in resultado.por_freelancer:
        fl_id = nombre_a_id.get(fl.nombre)
        if fl_id is not None:
            fls.append((fl.nombre, fl_id, fl.comision))

    if not fls:
        await cq.edit_message_text(
            obtener_mensaje("liquidaciones.sin_freelancers"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    context.user_data[_KEY_LIQ_FREELANCERS] = fls  # type: ignore[index]

    pago_repo = context.bot_data.get("pago_freelancer_repo")

    periodo_label = context.user_data.get(_KEY_PERIODO_LABEL, "")  # type: ignore[union-attr]
    titulo = obtener_mensaje("liquidaciones.titulo").format(periodo=periodo_label)

    rows: list[list[InlineKeyboardButton]] = []
    for nombre, fl_id, comision in fls:
        ya_pagado = (
            bool(pago_repo.buscar_solapados(fl_id, desde, hasta))
            if pago_repo is not None
            else False
        )
        base_label = obtener_mensaje("liquidaciones.freelancer_item").format(
            nombre=nombre, monto=fmt_cop(comision)
        )
        label = f"✅ {base_label}" if ya_pagado else base_label
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"rep_s:liq:fl:{fl_id}")]
        )
    rows.append([InlineKeyboardButton("← Atrás", callback_data="rep_s:liq:atras")])
    rows.append([InlineKeyboardButton("✖ Cancelar", callback_data="rep_s:liq:cancelar")])

    await cq.edit_message_text(
        titulo, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
    )
    return DIV_LIQ_FREELANCER


async def handle_div_liq_freelancer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle freelancer selection or navigation in the liquidaciones list."""
    cq = update.callback_query
    if cq is None:
        return DIV_LIQ_FREELANCER
    await cq.answer()

    data: str = cq.data or ""

    if data == "rep_s:liq:cancelar":
        await cq.edit_message_text(
            obtener_mensaje("liquidaciones.cancelado"), parse_mode="HTML"
        )
        return ConversationHandler.END

    if data == "rep_s:liq:atras":
        # Go back to result view
        resultado: ResumenSplitPeriodo | None = context.user_data.get(_KEY_RESULTADO)  # type: ignore[union-attr]
        periodo_label: str = context.user_data.get(_KEY_PERIODO_LABEL, "")  # type: ignore[union-attr]
        if resultado is not None:
            texto, markup = _render_resultado(resultado, periodo_label)
            await cq.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
        return DIV_RESULT

    # data format: rep_s:liq:fl:{uuid}
    if data.startswith("rep_s:liq:fl:"):
        fl_id_str = data[len("rep_s:liq:fl:"):]
        try:
            fl_id = _uuid_mod.UUID(fl_id_str)
        except ValueError:
            return DIV_LIQ_FREELANCER

        liquidar_service = context.bot_data.get("liquidar_service")
        if not isinstance(liquidar_service, LiquidarFreelancerService):
            logger.error("liquidar_service not in bot_data")
            return ConversationHandler.END

        raw_desde = context.user_data.get(_KEY_LIQ_DESDE)  # type: ignore[union-attr]
        raw_hasta = context.user_data.get(_KEY_LIQ_HASTA)  # type: ignore[union-attr]
        if not isinstance(raw_desde, datetime.date) or not isinstance(raw_hasta, datetime.date):
            logger.error("div_liq_desde/hasta missing in user_data for freelancer selection")
            return ConversationHandler.END
        desde: datetime.date = raw_desde
        hasta: datetime.date = raw_hasta

        liq_resultado = liquidar_service.calcular(fl_id, desde, hasta)
        context.user_data[_KEY_LIQ_RESULTADO] = liq_resultado  # type: ignore[index]

        # If already paid — show read-only "ya liquidado" screen
        if liq_resultado.solapados:
            lines: list[str] = [
                obtener_mensaje("liquidaciones.ya_liquidado_titulo"),
                "",
            ]
            rows_ya_liq: list[list[InlineKeyboardButton]] = []
            for pago in liq_resultado.solapados:
                fecha_pago_str = pago.fecha_pago.strftime("%d/%m/%Y")
                registrado_por = pago.registrado_por_nombre or "—"
                lines.append(
                    obtener_mensaje("liquidaciones.ya_liquidado_pago").format(
                        monto=fmt_cop(pago.monto),
                        fecha=fecha_pago_str,
                        registrado_por=registrado_por,
                    )
                )
                rows_ya_liq.append(
                    [InlineKeyboardButton("🗑️ Anular pago", callback_data=f"rep_s:liq:anular:{pago.id}")]
                )
            rows_ya_liq.append(
                [InlineKeyboardButton("← Atrás", callback_data="rep_s:liq:atras_confirmar")]
            )
            texto_ya_liq = "\n".join(lines)
            await cq.edit_message_text(
                texto_ya_liq, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows_ya_liq)
            )
            return DIV_LIQ_CONFIRMAR

        # Build confirmation message
        conf_lines: list[str] = [
            obtener_mensaje("liquidaciones.confirmar_titulo").format(
                nombre=liq_resultado.freelancer_nombre,
                desde=desde.strftime("%d/%m/%Y"),
                hasta=hasta.strftime("%d/%m/%Y"),
                total=fmt_cop(liq_resultado.comisiones_total),
            ),
        ]

        if liq_resultado.desglose:
            conf_lines.append("")
            for item in liq_resultado.desglose:
                pax = _pax_label(item.adultos, item.ninos)
                conf_lines.append(
                    obtener_mensaje("liquidaciones.desglose_item").format(
                        fecha=item.fecha.strftime("%d/%m"),
                        servicio=item.servicio_nombre,
                        pax=pax,
                        monto=fmt_cop(item.comision),
                    )
                )

        texto = "\n".join(conf_lines)
        rows = [
            [InlineKeyboardButton("✅ Confirmar", callback_data=f"rep_s:liq:confirmar:{fl_id}")],
            [InlineKeyboardButton("← Atrás", callback_data="rep_s:liq:atras_confirmar")],
            [InlineKeyboardButton("✖ Cancelar", callback_data="rep_s:liq:cancelar")],
        ]
        await cq.edit_message_text(
            texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
        )
        return DIV_LIQ_CONFIRMAR

    return DIV_LIQ_FREELANCER


async def handle_div_liq_confirmar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle confirmation, back, or cancel in the liquidaciones confirmation view."""
    cq = update.callback_query
    if cq is None:
        return DIV_LIQ_CONFIRMAR
    await cq.answer()

    data: str = cq.data or ""

    if data == "rep_s:liq:cancelar":
        await cq.edit_message_text(
            obtener_mensaje("liquidaciones.cancelado"), parse_mode="HTML"
        )
        return ConversationHandler.END

    if data == "rep_s:liq:atras_confirmar":
        # Go back to freelancer list
        return await handle_div_liq_start(update, context)

    # data format: rep_s:liq:confirmar:{uuid}
    if data.startswith("rep_s:liq:confirmar:"):
        fl_id_str = data[len("rep_s:liq:confirmar:"):]
        try:
            fl_id = _uuid_mod.UUID(fl_id_str)
        except ValueError:
            return DIV_LIQ_CONFIRMAR

        liquidar_service_confirmar = context.bot_data.get("liquidar_service")
        if not isinstance(liquidar_service_confirmar, LiquidarFreelancerService):
            logger.error("liquidar_service not in bot_data")
            return ConversationHandler.END

        raw_liq = context.user_data.get(_KEY_LIQ_RESULTADO)  # type: ignore[union-attr]
        if not isinstance(raw_liq, ResultadoCalculoLiquidacion):
            logger.error("liq_resultado not in user_data")
            return ConversationHandler.END
        liq_resultado: ResultadoCalculoLiquidacion = raw_liq

        raw_desde_conf = context.user_data.get(_KEY_LIQ_DESDE)  # type: ignore[union-attr]
        raw_hasta_conf = context.user_data.get(_KEY_LIQ_HASTA)  # type: ignore[union-attr]
        if not isinstance(raw_desde_conf, datetime.date) or not isinstance(raw_hasta_conf, datetime.date):
            logger.error("div_liq_desde/hasta missing in user_data for confirmar")
            return ConversationHandler.END
        desde: datetime.date = raw_desde_conf
        hasta: datetime.date = raw_hasta_conf

        user = update.effective_user
        registrado_por_id = user.id if user else 0
        registrado_por_nombre = user.full_name if user else None

        cmd = RegistrarPagoFreelancerComando(
            freelancer_id=fl_id,
            monto=liq_resultado.comisiones_total,
            desde=desde,
            hasta=hasta,
            registrado_por_telegram_id=registrado_por_id,
            registrado_por_nombre=registrado_por_nombre,
        )
        liquidar_service_confirmar.registrar_pago(cmd)

        # Send DM if freelancer has telegram_user_id
        telegram_id = liq_resultado.freelancer_telegram_id
        if telegram_id is not None:
            dm_lines: list[str] = [
                obtener_mensaje("liquidaciones.dm_titulo"),
                "",
                obtener_mensaje("liquidaciones.dm_periodo").format(
                    desde=desde.strftime("%d/%m"),
                    hasta=hasta.strftime("%d/%m"),
                ),
                obtener_mensaje("liquidaciones.dm_total").format(
                    total=fmt_cop(liq_resultado.comisiones_total)
                ),
            ]
            if liq_resultado.desglose:
                dm_lines.append("")
                dm_lines.append("Detalle:")
                for item in liq_resultado.desglose:
                    pax = _pax_label(item.adultos, item.ninos)
                    dm_lines.append(
                        obtener_mensaje("liquidaciones.dm_desglose_item").format(
                            fecha=item.fecha.strftime("%d/%m"),
                            servicio=item.servicio_nombre,
                            pax=pax,
                            monto=fmt_cop(item.comision),
                        )
                    )
            dm_text = "\n".join(dm_lines)
            try:
                bot: Bot = context.bot
                await bot.send_message(
                    chat_id=telegram_id, text=dm_text, parse_mode="HTML"
                )
            except Exception:
                logger.warning(
                    "Could not send DM to freelancer telegram_id=%s", telegram_id
                )

        nombre = liq_resultado.freelancer_nombre
        if telegram_id is not None:
            success_msg = obtener_mensaje("liquidaciones.pago_registrado").format(nombre=nombre)
        else:
            success_msg = obtener_mensaje("liquidaciones.pago_sin_dm").format(nombre=nombre)

        await cq.edit_message_text(success_msg, parse_mode="HTML")
        return ConversationHandler.END

    # data format: rep_s:liq:anular:{uuid}
    if data.startswith("rep_s:liq:anular:"):
        pago_id_str = data[len("rep_s:liq:anular:"):]
        try:
            pago_id = _uuid_mod.UUID(pago_id_str)
        except ValueError:
            return DIV_LIQ_CONFIRMAR

        raw_liq_anular = context.user_data.get(_KEY_LIQ_RESULTADO)  # type: ignore[union-attr]
        if not isinstance(raw_liq_anular, ResultadoCalculoLiquidacion):
            return DIV_LIQ_CONFIRMAR
        liq_resultado_anular: ResultadoCalculoLiquidacion = raw_liq_anular

        pago_a_anular = next(
            (p for p in liq_resultado_anular.solapados if p.id == pago_id), None
        )
        nombre_anular = liq_resultado_anular.freelancer_nombre
        monto_anular = fmt_cop(pago_a_anular.monto) if pago_a_anular else "—"

        texto_anular = obtener_mensaje("liquidaciones.anular_confirmar_titulo").format(
            monto=monto_anular,
            nombre=nombre_anular,
        )
        rows_anular = [
            [InlineKeyboardButton("✅ Confirmar", callback_data=f"rep_s:liq:anular_ok:{pago_id}")],
            [InlineKeyboardButton("← Cancelar", callback_data="rep_s:liq:anular_cancelar")],
        ]
        await cq.edit_message_text(
            texto_anular, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows_anular)
        )
        return DIV_LIQ_CONFIRMAR

    # data format: rep_s:liq:anular_ok:{uuid}
    if data.startswith("rep_s:liq:anular_ok:"):
        pago_id_str = data[len("rep_s:liq:anular_ok:"):]
        try:
            pago_id = _uuid_mod.UUID(pago_id_str)
        except ValueError:
            return DIV_LIQ_CONFIRMAR

        pago_repo = context.bot_data.get("pago_freelancer_repo")
        if pago_repo is not None:
            pago_repo.eliminar(pago_id)

        await cq.edit_message_text(
            obtener_mensaje("liquidaciones.anular_ok"), parse_mode="HTML"
        )
        return await handle_div_liq_start(update, context)

    # rep_s:liq:anular_cancelar — go back to ya_liquidado screen
    if data == "rep_s:liq:anular_cancelar":
        raw_liq_cancelar = context.user_data.get(_KEY_LIQ_RESULTADO)  # type: ignore[union-attr]
        if isinstance(raw_liq_cancelar, ResultadoCalculoLiquidacion):
            liq_res_cancelar: ResultadoCalculoLiquidacion = raw_liq_cancelar
            lines_cancelar: list[str] = [
                obtener_mensaje("liquidaciones.ya_liquidado_titulo"),
                "",
            ]
            rows_cancelar: list[list[InlineKeyboardButton]] = []
            for pago in liq_res_cancelar.solapados:
                fecha_pago_str = pago.fecha_pago.strftime("%d/%m/%Y")
                registrado_por = pago.registrado_por_nombre or "—"
                lines_cancelar.append(
                    obtener_mensaje("liquidaciones.ya_liquidado_pago").format(
                        monto=fmt_cop(pago.monto),
                        fecha=fecha_pago_str,
                        registrado_por=registrado_por,
                    )
                )
                rows_cancelar.append(
                    [InlineKeyboardButton("🗑️ Anular pago", callback_data=f"rep_s:liq:anular:{pago.id}")]
                )
            rows_cancelar.append(
                [InlineKeyboardButton("← Atrás", callback_data="rep_s:liq:atras_confirmar")]
            )
            await cq.edit_message_text(
                "\n".join(lines_cancelar),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows_cancelar),
            )
        return DIV_LIQ_CONFIRMAR

    return DIV_LIQ_CONFIRMAR


# ---------------------------------------------------------------------------
# Socio payment handlers
# ---------------------------------------------------------------------------


async def handle_div_soc_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry: callback rep_s:soc:start from DIV_RESULT. Shows socio selection list."""
    cq = update.callback_query
    if cq is None:
        return DIV_RESULT
    await cq.answer()

    resultado: ResumenSplitPeriodo | None = context.user_data.get(_KEY_RESULTADO)  # type: ignore[union-attr]
    periodo_label: str = context.user_data.get(_KEY_PERIODO_LABEL, "")  # type: ignore[union-attr]

    if resultado is None or not resultado.por_socio:
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.soc_cancelado"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    rows: list[list[InlineKeyboardButton]] = []
    for s in resultado.por_socio:
        nombre = s.nombre
        periodo_monto = fmt_cop(s.acumulado)
        label = obtener_mensaje("resumen_divisiones.soc_item_btn").format(
            nombre=nombre.capitalize(),
            periodo_monto=periodo_monto,
        )
        rows.append([InlineKeyboardButton(label, callback_data=f"rep_s:soc:sel:{nombre}")])

    rows.append([InlineKeyboardButton("← Atrás", callback_data="rep_s:atras:resultado")])
    rows.append([InlineKeyboardButton("✖ Cancelar", callback_data="rep_s:soc:cancelar")])

    titulo = obtener_mensaje("resumen_divisiones.soc_desglose_titulo").format(
        nombre="socios",
        periodo=periodo_label,
    )
    await cq.edit_message_text(
        titulo,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return DIV_SOC_SELECCION


def _render_soc_desglose(
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[str, InlineKeyboardMarkup]:
    """Build the desglose screen for a selected socio."""
    resultado: ResumenSplitPeriodo | None = context.user_data.get(_KEY_RESULTADO)  # type: ignore[union-attr]
    periodo_label: str = context.user_data.get(_KEY_PERIODO_LABEL, "")  # type: ignore[union-attr]
    nombre: str = context.user_data.get(_KEY_SOC_NOMBRE, "")  # type: ignore[union-attr]
    monto_parcial: Dinero | None = context.user_data.get(_KEY_SOC_MONTO)  # type: ignore[union-attr]

    # Get accumulated pendiente for this socio
    split_service = context.bot_data.get("split_socios_service")
    pendiente = Dinero(0)
    if split_service is not None:
        acumulado: ResumenSplitSocios = split_service.calcular_acumulado(
            desde=obtener_settings().socios_desde
        )
        for rs in acumulado.por_socio:
            if rs.nombre.lower() == nombre.lower():
                pendiente = rs.pendiente
                break

    # Build desglose lines from ventas_detalle
    lineas: list[str] = []
    periodo_total = Dinero(0)
    if resultado is not None:
        for venta in resultado.ventas_detalle:
            for s in venta.split_socios:
                if s.nombre.lower() == nombre.lower() and s.acumulado > Dinero(0):
                    fecha_str = venta.fecha.strftime("%d/%m")
                    lineas.append(
                        obtener_mensaje("resumen_divisiones.soc_desglose_item").format(
                            fecha=fecha_str,
                            bruto=fmt_cop(venta.valor_bruto),
                            parte=fmt_cop(s.acumulado),
                        )
                    )
                    periodo_total = periodo_total + s.acumulado

    titulo = obtener_mensaje("resumen_divisiones.soc_desglose_titulo").format(
        nombre=html.escape(nombre.capitalize()),
        periodo=html.escape(periodo_label),
    )
    partes: list[str] = [titulo, ""]
    if lineas:
        partes.extend(lineas)
    partes.append(
        obtener_mensaje("resumen_divisiones.soc_periodo_total").format(
            monto=fmt_cop(periodo_total)
        )
    )
    partes.append(
        obtener_mensaje("resumen_divisiones.soc_pendiente_total").format(
            monto=fmt_cop(pendiente)
        )
    )

    texto = "\n".join(partes)

    # Build buttons
    rows: list[list[InlineKeyboardButton]] = []
    if monto_parcial is not None:
        rows.append([InlineKeyboardButton(
            f"✅ Confirmar pago ({fmt_cop(monto_parcial)})",
            callback_data="rep_s:soc:confirmar",
        )])
    if pendiente > Dinero(0):
        rows.append([InlineKeyboardButton(
            f"✅ Pagar total pendiente ({fmt_cop(pendiente)})",
            callback_data="rep_s:soc:total",
        )])
        rows.append([InlineKeyboardButton(
            "💰 Ingresar otro monto",
            callback_data="rep_s:soc:parcial",
        )])
    else:
        partes.append(obtener_mensaje("resumen_divisiones.soc_sin_pendiente"))
        texto = "\n".join(partes)

    rows.append([InlineKeyboardButton("← Atrás", callback_data="rep_s:soc:atras")])
    rows.append([InlineKeyboardButton("✖ Cancelar", callback_data="rep_s:soc:cancelar")])

    return texto, InlineKeyboardMarkup(rows)


async def handle_div_soc_seleccion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry: callback rep_s:soc:sel:{nombre} from DIV_SOC_SELECCION."""
    cq = update.callback_query
    if cq is None:
        return DIV_SOC_SELECCION
    await cq.answer()

    data: str = cq.data or ""
    if data.startswith("rep_s:soc:cancelar"):
        await cq.edit_message_text(
            obtener_mensaje("resumen_divisiones.soc_cancelado"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    prefix = "rep_s:soc:sel:"
    if not data.startswith(prefix):
        return DIV_SOC_SELECCION

    nombre = data[len(prefix):]
    context.user_data[_KEY_SOC_NOMBRE] = nombre  # type: ignore[index]
    context.user_data[_KEY_SOC_MONTO] = None  # type: ignore[index]

    texto, markup = _render_soc_desglose(context)
    await cq.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
    return DIV_SOC_CONFIRMAR


def _registrar_pago_socio(
    context: ContextTypes.DEFAULT_TYPE,
    nombre: str,
    monto: Dinero,
) -> PagoSocio:
    """Create and save a PagoSocio. Returns the saved instance."""
    import uuid
    pagos_socio_repo = context.bot_data.get("pagos_socio_repo")
    pago = PagoSocio(
        id=uuid.uuid4(),
        nombre_socio=nombre,
        monto=monto,
        fecha=datetime.date.today(),
        tipo="parcial" if context.user_data.get(_KEY_SOC_MONTO) is not None else "total",
        nota=None,
        registrado_en=datetime.datetime.now(datetime.UTC),
    )
    if pagos_socio_repo is not None:
        pagos_socio_repo.guardar(pago)
    return pago


async def handle_div_soc_confirmar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle all actions in DIV_SOC_CONFIRMAR: callbacks and text amount input."""
    cq = update.callback_query

    # --- Callback branch ---
    if cq is not None:
        await cq.answer()
        data: str = cq.data or ""

        if data == "rep_s:soc:atras":
            return await handle_div_soc_start(update, context)

        if data == "rep_s:soc:cancelar":
            await cq.edit_message_text(
                obtener_mensaje("resumen_divisiones.soc_cancelado"),
                parse_mode="HTML",
            )
            return ConversationHandler.END

        if data == "rep_s:soc:parcial":
            await cq.edit_message_text(
                obtener_mensaje("resumen_divisiones.soc_pedir_monto"),
                parse_mode="HTML",
            )
            return DIV_SOC_CONFIRMAR

        if data == "rep_s:soc:total":
            nombre: str = context.user_data.get(_KEY_SOC_NOMBRE, "")  # type: ignore[union-attr]
            split_service = context.bot_data.get("split_socios_service")
            pendiente = Dinero(0)
            if split_service is not None:
                acumulado: ResumenSplitSocios = split_service.calcular_acumulado(
            desde=obtener_settings().socios_desde
        )
                for rs in acumulado.por_socio:
                    if rs.nombre.lower() == nombre.lower():
                        pendiente = rs.pendiente
                        break
            pago = _registrar_pago_socio(context, nombre, pendiente)
            success_text = obtener_mensaje("resumen_divisiones.soc_registrado").format(
                nombre=html.escape(nombre.capitalize()),
                monto=fmt_cop(pago.monto),
            )
            await cq.edit_message_text(success_text, parse_mode="HTML")
            return ConversationHandler.END

        if data == "rep_s:soc:confirmar":
            monto_parcial: Dinero | None = context.user_data.get(_KEY_SOC_MONTO)  # type: ignore[union-attr]
            if monto_parcial is None:
                return DIV_SOC_CONFIRMAR
            nombre2: str = context.user_data.get(_KEY_SOC_NOMBRE, "")  # type: ignore[union-attr]
            pago2 = _registrar_pago_socio(context, nombre2, monto_parcial)
            success_text2 = obtener_mensaje("resumen_divisiones.soc_registrado").format(
                nombre=html.escape(nombre2.capitalize()),
                monto=fmt_cop(pago2.monto),
            )
            await cq.edit_message_text(success_text2, parse_mode="HTML")
            return ConversationHandler.END

        return DIV_SOC_CONFIRMAR

    # --- Text message branch (amount input) ---
    if update.message is None:
        return DIV_SOC_CONFIRMAR

    texto_input: str = (update.message.text or "").strip()
    monto_decimal = parsear_monto(texto_input)
    if monto_decimal is None:
        await update.message.reply_text(
            obtener_mensaje("resumen_divisiones.soc_monto_invalido"),
            parse_mode="HTML",
        )
        return DIV_SOC_CONFIRMAR

    context.user_data[_KEY_SOC_MONTO] = Dinero(monto_decimal)  # type: ignore[index]
    texto_desglose, markup_desglose = _render_soc_desglose(context)
    await update.message.reply_text(
        texto_desglose,
        reply_markup=markup_desglose,
        parse_mode="HTML",
    )
    return DIV_SOC_CONFIRMAR


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
            DIV_RESULT: [
                CallbackQueryHandler(handle_div_venta, pattern=r"^rep_s:venta:"),
                CallbackQueryHandler(handle_div_atras, pattern=r"^rep_s:atras:resultado"),
                CallbackQueryHandler(handle_div_cerrar, pattern=r"^rep_s:menu:cerrar"),
                CallbackQueryHandler(handle_div_liq_start, pattern=r"^rep_s:liq:start$"),
                CallbackQueryHandler(handle_div_soc_start, pattern=r"^rep_s:soc:start$"),
            ],
            DIV_LIQ_FREELANCER: [
                CallbackQueryHandler(handle_div_liq_freelancer, pattern=r"^rep_s:liq:"),
            ],
            DIV_LIQ_CONFIRMAR: [
                CallbackQueryHandler(handle_div_liq_confirmar, pattern=r"^rep_s:liq:"),
            ],
            DIV_SOC_SELECCION: [
                CallbackQueryHandler(handle_div_soc_seleccion, pattern=r"^rep_s:soc:sel:"),
                CallbackQueryHandler(handle_div_atras, pattern=r"^rep_s:atras:resultado$"),
                CallbackQueryHandler(handle_div_soc_confirmar, pattern=r"^rep_s:soc:cancelar$"),
            ],
            DIV_SOC_CONFIRMAR: [
                CallbackQueryHandler(handle_div_soc_confirmar, pattern=r"^rep_s:soc:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_div_soc_confirmar),
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
