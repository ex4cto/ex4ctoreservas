"""Pure alert-message builder for the infrastructure monitor.

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
