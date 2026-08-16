"""Pure alert-message builders for the infrastructure monitor.

Side-effect-free and unit-testable in isolation.
All dynamic values are HTML-escaped because Telegram uses parse_mode=HTML
and the service name comes from config (could contain special chars).

Mirrors the style of garay.infraestructura.webhook.alertas.
"""

from __future__ import annotations

import datetime
import html


def construir_alerta_renovacion(
    *,
    nombre: str,
    dias: int,
    fecha: datetime.date,
) -> str:
    """Mensaje HTML en espanol para el chat privado del propietario.

    Args:
        nombre: Nombre del servicio de infraestructura (HTML-escaped).
        dias: Dias restantes hasta la renovacion.
        fecha: Fecha exacta de renovacion.

    Returns:
        String HTML listo para enviar con parse_mode=HTML.
    """
    return (
        "<b>⏰ Renovación próxima</b>\n"
        f"<b>Servicio:</b> {html.escape(nombre)}\n"
        f"<b>Vence en:</b> {dias} días\n"
        f"<b>Fecha de renovación:</b> {fecha.isoformat()}"
    )


def construir_alerta_costo_railway(
    *,
    costo_actual: float,
    umbral: float,
    estimado_factura: float,
) -> str:
    """Mensaje HTML en español para alertar al propietario sobre el costo de Railway.

    Args:
        costo_actual: Costo real acumulado en el mes hasta hoy (USD).
        umbral: Umbral configurado en USD que se cruzó.
        estimado_factura: Estimado de la factura a fin de mes (USD).

    Returns:
        String HTML listo para enviar con parse_mode=HTML.
    """
    return (
        f"<b>⚠️ Railway: límite de costo cruzado</b>\n"
        f"Ya llevas <b>${costo_actual:.2f}</b> este mes "
        f"(cruzaste el límite de ${umbral:.0f}).\n"
        f"Estimado a fin de mes: ~<b>${estimado_factura:.2f}</b>."
    )


def construir_alerta_cuota(
    *,
    tipo: str,
    conteo: int,
    cap: int,
    umbral: int,
) -> str:
    """Mensaje HTML en español para alertar al propietario sobre la cuota de Resend.

    Args:
        tipo: "mensual" o "diario".
        conteo: Número de correos enviados en el período.
        cap: Límite máximo del período (mensual o diario).
        umbral: Umbral absoluto que se cruzó (mensual) o umbral configurado (diario).

    Returns:
        String HTML listo para enviar con parse_mode=HTML.
    """
    if tipo == "diario":
        return (
            "<b>⚠️ Resend: límite diario cruzado</b>\n"
            f"Ayer enviaste <b>{conteo}</b> correos "
            f"(límite diario configurado: {cap}/día).\n"
            "Revisa el volumen de facturas para no saturar la cuota."
        )
    # mensual
    pct = int(conteo * 100 / cap) if cap > 0 else 0
    return (
        "<b>⚠️ Resend: cuota mensual</b>\n"
        f"Llevas <b>{conteo}</b> de {cap} correos este mes "
        f"(cruzaste el umbral de {umbral}).\n"
        f"Vas al <b>{pct}%</b> del cupo mensual."
    )
