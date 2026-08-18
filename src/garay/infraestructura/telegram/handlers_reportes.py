"""Telegram handlers for dashboard reports — /dashboard_ventas, /flujo_caja and /movimientos."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from garay.infraestructura.telegram.auth import (
    requiere_admin,
    requiere_admin_o_propietario,
    requiere_propietario,
)
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


def _formatear_tours(waterfall: object, ranking: object, reconciliacion: object,
                     mes: int, año: int) -> str:
    from garay.aplicacion.reportes.ranking_tour import RankingTour
    from garay.aplicacion.reportes.reconciliacion_ventas_ingresos import (
        ReconciliacionVentasIngresos,
    )
    from garay.aplicacion.reportes.waterfall_ventas import WaterfallVentas

    assert isinstance(waterfall, WaterfallVentas)
    assert isinstance(ranking, RankingTour)
    assert isinstance(reconciliacion, ReconciliacionVentasIngresos)

    if waterfall.valor_bruto.monto == 0:
        return obtener_mensaje("reporte.sin_datos")

    lineas = [
        obtener_mensaje("reporte.tours.encabezado").format(
            mes=_MESES_ES[mes],
            año=año,
            bruto=f"{waterfall.valor_bruto.monto:,.0f}",
            neto=f"{waterfall.costo_neto.monto:,.0f}",
            margen=f"{waterfall.margen.monto:,.0f}",
            comisiones=f"{waterfall.comisiones.monto:,.0f}",
            agencia=f"{waterfall.ganancia_agencia.monto:,.0f}",
        ),
    ]
    if ranking.filas:
        lineas.append("")
        lineas.append("🏝️ *Top familias:*")
        for f in ranking.filas[:5]:
            lineas.append(
                obtener_mensaje("reporte.tours.familia_item").format(
                    familia=f.familia,
                    vendidos=f.vendidos,
                    margen=f"{f.margen.monto:,.0f}",
                )
            )
    if reconciliacion.total_ingresos_banco.monto > 0:
        lineas.append("")
        lineas.append(
            obtener_mensaje("reporte.tours.conciliacion").format(
                agencia=f"{reconciliacion.total_agencia_esperada.monto:,.0f}",
                banco=f"{reconciliacion.total_ingresos_banco.monto:,.0f}",
                desviacion=f"{reconciliacion.porcentaje_desviacion:.1f}",
            )
        )
    return "\n".join(lineas)


def _tours_para(context: ContextTypes.DEFAULT_TYPE, mes: int, año: int) -> str:
    waterfall = context.bot_data["waterfall_service"].ejecutar(mes, año)
    ranking = context.bot_data["ranking_tour_service"].ejecutar(mes, año)
    reconciliacion = context.bot_data["reconciliacion_service"].ejecutar(mes, año)
    return _formatear_tours(waterfall, ranking, reconciliacion, mes, año)


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


@requiere_propietario
async def cmd_tours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hoy = date.today()
    texto = _tours_para(context, hoy.month, hoy.year)
    teclado = _teclado_navegacion(hoy.month, hoy.year, "rep_t")
    if update.effective_message:
        await update.effective_message.reply_text(
            texto, reply_markup=teclado, parse_mode="Markdown"
        )


async def cb_tours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    _, periodo = (query.data or "").split(":", 1)
    año_str, mes_str = periodo.split("-")
    mes, año = int(mes_str), int(año_str)

    texto = _tours_para(context, mes, año)
    teclado = _teclado_navegacion(mes, año, "rep_t")
    if query.message:
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")


def _fmt_cop(valor: Decimal) -> str:
    # Replicates the per-module pattern from handlers.py and handlers_egresos.py.
    # E.g.: Decimal("208929.30") → "$208.929"
    return "$" + f"{int(valor):,}".replace(",", ".")


_BOGOTA = ZoneInfo("America/Bogota")


def _hora_bogota(dt: datetime) -> str:
    # fecha_recibido may be naive (SQLite) or aware (Postgres); normalize to UTC first.
    aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    return aware.astimezone(_BOGOTA).strftime("%H:%M")


def _formatear_movimientos(movimientos: object, horas: int) -> str:
    from garay.aplicacion.reportes.movimientos_recientes import MovimientosRecientes

    assert isinstance(movimientos, MovimientosRecientes)

    lineas = [
        obtener_mensaje("movimientos.encabezado").format(horas=horas),
    ]

    if not movimientos.ingresos and not movimientos.egresos:
        lineas.append(obtener_mensaje("movimientos.sin_movimientos"))
        return "\n".join(lineas)

    tag_reenvio = obtener_mensaje("movimientos.tag_reenvio")

    if movimientos.ingresos:
        lineas.append("")
        lineas.append(obtener_mensaje("movimientos.seccion_ingresos"))
        for ing in movimientos.ingresos:
            hora_str = (
                _hora_bogota(ing.fecha_recibido)
                if ing.fecha_recibido is not None
                else "—"
            )
            monto_str = _fmt_cop(ing.monto.monto)
            reenvio_tag = f" {tag_reenvio}" if ing.reenviado else ""
            lineas.append(
                obtener_mensaje("movimientos.linea").format(
                    monto=monto_str,
                    detalle=f"{ing.banco}{reenvio_tag}",
                    hora=hora_str,
                )
            )

    if movimientos.egresos:
        lineas.append("")
        lineas.append(obtener_mensaje("movimientos.seccion_egresos"))
        for egr in movimientos.egresos:
            hora_str = (
                _hora_bogota(egr.fecha_recibido)
                if egr.fecha_recibido is not None
                else "—"
            )
            monto_str = _fmt_cop(egr.monto.monto)
            reenvio_tag = f" {tag_reenvio}" if egr.reenviado else ""
            lineas.append(
                obtener_mensaje("movimientos.linea").format(
                    monto=monto_str,
                    detalle=f"{egr.descripcion}{reenvio_tag}",
                    hora=hora_str,
                )
            )

    return "\n".join(lineas)


@requiere_admin_o_propietario
async def cmd_movimientos(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    from garay.aplicacion.reportes.movimientos_recientes import MovimientosRecientesService

    horas = 24
    servicio: MovimientosRecientesService = context.bot_data["movimientos_service"]
    movimientos = servicio.ejecutar(horas=horas)
    texto = _formatear_movimientos(movimientos, horas=horas)
    if update.effective_message:
        await update.effective_message.reply_text(texto)


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
    app.add_handler(CommandHandler("tours", cmd_tours), group=1)
    app.add_handler(
        CallbackQueryHandler(cb_tours, pattern=r"^rep_t:\d{4}-\d{2}$"),
        group=1,
    )
    app.add_handler(CommandHandler("movimientos", cmd_movimientos), group=1)
