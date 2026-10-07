"""Pure detection and formatting functions for external operator notifications."""
from __future__ import annotations

import datetime
import html
from dataclasses import dataclass

from garay.aplicacion.comun.formato import fmt_cop
from garay.dominio.comun.dinero import Dinero

_PATRONES: dict[str, list[str]] = {
    "isla_palma": ["ISLA PALMA"],
    "palmarito": ["PALMARITO"],
    "bonavida": ["BONAVIDA", "BONA VIDA"],
}


def detectar_operador(servicio_nombres: list[str]) -> str | None:
    for nombre in servicio_nombres:
        nombre_upper = nombre.upper()
        for key, patrones in _PATRONES.items():
            if any(p in nombre_upper for p in patrones):
                return key
    return None


@dataclass(frozen=True)
class DatosNotificacion:
    servicio_nombres: list[str]
    fecha: datetime.date
    cliente_nombre: str | None
    cliente_cedula: str | None
    cliente_telefono: str | None
    cliente_email: str | None
    adultos: int
    ninos: int
    valor_venta: Dinero
    abono: Dinero | None
    ganancia: Dinero


def formatear_notificacion(operador: str, datos: DatosNotificacion) -> str | None:
    if operador == "palmarito":
        return _fmt_palmarito(datos)
    if operador == "isla_palma":
        return _fmt_isla_palma(datos)
    if operador == "bonavida":
        return _fmt_bonavida(datos)
    return None


def _esc(v: object) -> str:
    return html.escape(str(v) if v is not None else "—", quote=False)


def _fmt_palmarito(datos: DatosNotificacion) -> str:
    saldo = (
        datos.valor_venta - datos.abono
        if datos.abono is not None
        else datos.valor_venta
    )
    pax_parts = [f"{datos.adultos} adulto{'s' if datos.adultos != 1 else ''}"]
    if datos.ninos > 0:
        pax_parts.append(f"{datos.ninos} niño{'s' if datos.ninos != 1 else ''}")
    pax = ", ".join(pax_parts)

    fecha_str = datos.fecha.strftime("%d/%m/%Y")

    lineas = [
        "FORMATO PASADÍA",
        "Para reservar por favor llene el siguiente formato con los datos del titular de la reserva en un sólo texto y completo:",
        f"- Fecha: {fecha_str}",
        f"- Nombre : {datos.cliente_nombre or '—'}",
        f"- Cédula o pasaporte: {datos.cliente_cedula or '—'}",
        f"- Celular: {datos.cliente_telefono or '—'}",
        f"- Correo: {datos.cliente_email or '—'}",
        f"- Nº Personas: {pax}",
        f"- Total: {fmt_cop(datos.valor_venta)}",
        f"- Abono: {fmt_cop(datos.abono)}",
        f"- Saldo: {fmt_cop(saldo)}",
        "-Reservó: Agencia Garay Tour",
        "",
        "Pregunta por nuestro servicio de ALOJAMIENTO ⭐🌜",
        "🚫 ES PROHIBIDO EL INGRESO DE BEBIDAS Y ALIMENTOS EN EL HOTEL 🚫",
    ]
    return "\n".join(lineas)


def _fmt_isla_palma(datos: DatosNotificacion) -> str:
    tours = ", ".join(datos.servicio_nombres) if datos.servicio_nombres else "—"
    fecha_str = datos.fecha.strftime("%d/%m/%Y")
    pax_parts = [f"{datos.adultos} adulto{'s' if datos.adultos != 1 else ''}"]
    if datos.ninos > 0:
        pax_parts.append(f"{datos.ninos} niño{'s' if datos.ninos != 1 else ''}")
    pax = ", ".join(pax_parts)

    lineas = [
        "📄 <b>Isla Palma — cuenta de cobro pendiente</b>",
        "",
        f"Tour: {_esc(tours)}",
        f"Fecha: {fecha_str} | Pax: {pax}",
        f"Ganancia: {fmt_cop(datos.ganancia)}",
        "",
        "Recuerda generar la cuenta de cobro al final del día.",
    ]
    return "\n".join(lineas)


def _fmt_bonavida(datos: DatosNotificacion) -> str:
    tours = ", ".join(datos.servicio_nombres) if datos.servicio_nombres else "—"
    fecha_str = datos.fecha.strftime("%d/%m/%Y")

    lineas = [
        "✉️ <b>Comisión Bonavida</b>",
        "",
        f"Tour: {_esc(tours)}",
        f"Fecha: {fecha_str}",
        "",
        "Bonavida enviará la comisión en 7 días hábiles por correo electrónico.",
    ]
    return "\n".join(lineas)
