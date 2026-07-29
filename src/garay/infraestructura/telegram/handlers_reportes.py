"""Telegram handlers for dashboard reports — /dashboard_ventas and /flujo_caja."""

from __future__ import annotations

import logging
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from garay.infraestructura.telegram.auth import requiere_admin, requiere_propietario
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

_MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def _mes_anterior(mes: int, año: int) -> tuple[int, int]:
    return (12, año - 1) if mes == 1 else (mes - 1, año)


def _mes_siguiente(mes: int, año: int) -> tuple[int, int]:
    return (1, año + 1) if mes == 12 else (mes + 1, año)


def _teclado_navegacion(mes: int, año: int, prefijo: str) -> InlineKeyboardMarkup:
    mes_ant, año_ant = _mes_anterior(mes, año)
    mes_sig, año_sig = _mes_siguiente(mes, año)
    hoy = date.today()
    botones = [
        InlineKeyboardButton(
            obtener_mensaje("reporte.nav_anterior").format(
                label=f"{_MESES_ES[mes_ant]} {año_ant}"
            ),
            callback_data=f"{prefijo}:{año_ant}-{mes_ant:02d}",
        ),
    ]
    # Only show "next" if not pointing to a future month
    if (año, mes) < (hoy.year, hoy.month):
        botones.append(
            InlineKeyboardButton(
                obtener_mensaje("reporte.nav_siguiente").format(
                    label=f"{_MESES_ES[mes_sig]} {año_sig}"
                ),
                callback_data=f"{prefijo}:{año_sig}-{mes_sig:02d}",
            )
        )
    return InlineKeyboardMarkup([botones])


def _formatear_resumen_ventas(resumen: object, mes: int, año: int) -> str:
    from garay.aplicacion.reportes.resumen_ventas import ResumenVentas

    assert isinstance(resumen, ResumenVentas)

    if resumen.total_ventas == 0:
        return obtener_mensaje("reporte.sin_datos")

    lineas = [
        obtener_mensaje("reporte.ventas.encabezado").format(
            mes=_MESES_ES[mes],
            año=año,
            total_ventas=resumen.total_ventas,
            total_valor=f"{resumen.total_valor.monto:,.0f}",
            ganancia=f"{resumen.ganancia_agencia.monto:,.0f}",
        ),
    ]
    if resumen.por_vendedor:
        lineas.append("")
        lineas.append("👥 *Por vendedor:*")
        for v in resumen.por_vendedor:
            if v.ventas > 0:
                lineas.append(
                    obtener_mensaje("reporte.ventas.vendedor_item").format(
                        nombre=v.nombre,
                        ventas=v.ventas,
                        comision=f"{v.comision.monto:,.0f}",
                    )
                )
    return "\n".join(lineas)


def _formatear_flujo_caja(flujo: object, mes: int, año: int) -> str:
    from garay.aplicacion.reportes.flujo_caja import FlujoCaja

    assert isinstance(flujo, FlujoCaja)

    if flujo.total_ingresos.monto == 0 and flujo.total_egresos.monto == 0:
        return obtener_mensaje("reporte.sin_datos")

    signo = "+" if flujo.balance.monto >= 0 else "-"
    lineas = [
        obtener_mensaje("reporte.caja.encabezado").format(
            mes=_MESES_ES[mes],
            año=año,
            ingresos=f"{flujo.total_ingresos.monto:,.0f}",
            egresos=f"{flujo.total_egresos.monto:,.0f}",
            signo=signo,
            balance=f"{abs(flujo.balance.monto):,.0f}",
            conciliados=flujo.ingresos_conciliados,
            pendientes=flujo.ingresos_pendientes,
        ),
    ]
    if flujo.egresos_por_categoria:
        lineas.append("")
        lineas.append("📤 *Egresos por categoría:*")
        for cat, monto in flujo.egresos_por_categoria:
            lineas.append(
                obtener_mensaje("reporte.caja.categoria_item").format(
                    categoria=cat,
                    monto=f"{monto.monto:,.0f}",
                )
            )
    return "\n".join(lineas)


@requiere_admin
async def cmd_dashboard_ventas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService
    from garay.config.settings import obtener_settings

    hoy = date.today()
    servicio: ResumenVentasService = context.bot_data["resumen_ventas_service"]
    resumen = servicio.ejecutar(hoy.month, hoy.year)
    texto = _formatear_resumen_ventas(resumen, hoy.month, hoy.year)
    url = obtener_settings().dashboard_url
    texto += f"\n\n📊 [Ver dashboard completo]({url})"
    teclado = _teclado_navegacion(hoy.month, hoy.year, "rep_v")
    if update.effective_message:
        await update.effective_message.reply_text(
            texto, reply_markup=teclado, parse_mode="Markdown"
        )


@requiere_propietario
async def cmd_flujo_caja(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    from garay.aplicacion.reportes.flujo_caja import FlujoCajaService

    hoy = date.today()
    servicio: FlujoCajaService = context.bot_data["flujo_caja_service"]
    flujo = servicio.ejecutar(hoy.month, hoy.year)
    texto = _formatear_flujo_caja(flujo, hoy.month, hoy.year)
    teclado = _teclado_navegacion(hoy.month, hoy.year, "rep_c")
    if update.effective_message:
        await update.effective_message.reply_text(
            texto, reply_markup=teclado, parse_mode="Markdown"
        )


async def cb_dashboard_ventas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService

    query = update.callback_query
    if query is None:
        return
    await query.answer()
    _, periodo = (query.data or "").split(":", 1)
    año_str, mes_str = periodo.split("-")
    mes, año = int(mes_str), int(año_str)

    servicio: ResumenVentasService = context.bot_data["resumen_ventas_service"]
    resumen = servicio.ejecutar(mes, año)
    texto = _formatear_resumen_ventas(resumen, mes, año)
    teclado = _teclado_navegacion(mes, año, "rep_v")
    if query.message:
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")


async def cb_flujo_caja(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    from garay.aplicacion.reportes.flujo_caja import FlujoCajaService

    query = update.callback_query
    if query is None:
        return
    await query.answer()
    _, periodo = (query.data or "").split(":", 1)
    año_str, mes_str = periodo.split("-")
    mes, año = int(mes_str), int(año_str)

    servicio: FlujoCajaService = context.bot_data["flujo_caja_service"]
    flujo = servicio.ejecutar(mes, año)
    texto = _formatear_flujo_caja(flujo, mes, año)
    teclado = _teclado_navegacion(mes, año, "rep_c")
    if query.message:
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")


def registrar_handlers(app: object) -> None:
    from telegram.ext import Application

    assert isinstance(app, Application)
    app.add_handler(CommandHandler("dashboard_ventas", cmd_dashboard_ventas), group=1)
    app.add_handler(CommandHandler("flujo_caja", cmd_flujo_caja), group=1)
    app.add_handler(
        CallbackQueryHandler(cb_dashboard_ventas, pattern=r"^rep_v:\d{4}-\d{2}$"),
        group=1,
    )
    app.add_handler(
        CallbackQueryHandler(cb_flujo_caja, pattern=r"^rep_c:\d{4}-\d{2}$"),
        group=1,
    )
