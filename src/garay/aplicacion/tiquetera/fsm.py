"""Pure FSM for the Telegram bot conversation flow.

No Telegram imports. Fully testable in isolation.
"""
from __future__ import annotations

import copy
import datetime
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta


class EstadoFSM(StrEnum):
    TIPO_RESERVA = "tipo_reserva"
    PUNTO_DE_VENTA = "punto_de_venta"
    DESTINO = "destino"
    CLIENTE_NOMBRE = "cliente_nombre"
    CLIENTE_TELEFONO = "cliente_telefono"
    CLIENTE_HOTEL = "cliente_hotel"
    CLIENTE_HABITACION = "cliente_habitacion"
    FECHA_SALIDA = "fecha_salida"
    PAX_ADULTOS = "pax_adultos"
    PAX_NINOS = "pax_ninos"
    NUMERO_TICKET = "numero_ticket"
    MONTO_VALOR = "monto_valor"
    MONTO_ABONO = "monto_abono"
    MONTO_NETO = "monto_neto"
    PARTICIPANTE_NOMBRE = "participante_nombre"
    PARTICIPANTE_ROL = "participante_rol"
    PARTICIPANTE_OTRO = "participante_otro"
    CONFIRMACION = "confirmacion"
    TERMINADO = "terminado"
    CANCELADO = "cancelado"


@dataclass(frozen=True)
class SalidaFSM:
    nuevo_estado: EstadoFSM
    mensaje: str
    opciones: list[str] = field(default_factory=list)
    listo: bool = False
    contexto: ContextoVenta = field(default_factory=ContextoVenta)


def _clonar(ctx: ContextoVenta) -> ContextoVenta:
    return copy.deepcopy(ctx)


def _parsear_monto(texto: str) -> Decimal | None:
    """Accept '500000', '500.000', '500,000' as thousands-separated numbers."""
    limpio = texto.strip().replace(".", "").replace(",", "")
    try:
        valor = Decimal(limpio)
        if valor < Decimal("0"):
            return None
        return valor
    except InvalidOperation:
        return None


def _parsear_fecha(texto: str) -> datetime.datetime | None:
    """Try DD/MM, DD/MM/YYYY, DD/MM HH:MM."""
    texto = texto.strip()
    now = datetime.datetime.now()
    formatos_con_año = ["%d/%m/%Y %H:%M", "%d/%m/%Y"]
    for fmt in formatos_con_año:
        try:
            return datetime.datetime.strptime(texto, fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.strptime(f"{texto}/{now.year}", "%d/%m/%Y")
    except ValueError:
        pass
    return None


class FSMTiquetera:
    """Pure finite state machine for the Telegram sale-registration conversation."""

    def __init__(
        self,
        servicios: list[tuple[int, str]],  # (numero, nombre)
        puntos_venta: list[str],
    ) -> None:
        self._servicios = servicios
        self._puntos_venta = puntos_venta

    def iniciar(self) -> SalidaFSM:
        return SalidaFSM(
            nuevo_estado=EstadoFSM.TIPO_RESERVA,
            mensaje="¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO, DIGITAL",
            opciones=["INTERNO", "EXTERNO", "DIGITAL"],
            contexto=ContextoVenta(),
        )

    def procesar(
        self,
        estado: EstadoFSM,
        entrada: str,
        contexto: ContextoVenta,
    ) -> SalidaFSM:
        handlers = {
            EstadoFSM.TIPO_RESERVA: self._handle_tipo_reserva,
            EstadoFSM.PUNTO_DE_VENTA: self._handle_punto_de_venta,
            EstadoFSM.DESTINO: self._handle_destino,
            EstadoFSM.CLIENTE_NOMBRE: self._handle_cliente_nombre,
            EstadoFSM.CLIENTE_TELEFONO: self._handle_cliente_telefono,
            EstadoFSM.CLIENTE_HOTEL: self._handle_cliente_hotel,
            EstadoFSM.CLIENTE_HABITACION: self._handle_cliente_habitacion,
            EstadoFSM.FECHA_SALIDA: self._handle_fecha_salida,
            EstadoFSM.PAX_ADULTOS: self._handle_pax_adultos,
            EstadoFSM.PAX_NINOS: self._handle_pax_ninos,
            EstadoFSM.NUMERO_TICKET: self._handle_numero_ticket,
            EstadoFSM.MONTO_VALOR: self._handle_monto_valor,
            EstadoFSM.MONTO_ABONO: self._handle_monto_abono,
            EstadoFSM.MONTO_NETO: self._handle_monto_neto,
            EstadoFSM.PARTICIPANTE_NOMBRE: self._handle_participante_nombre,
            EstadoFSM.PARTICIPANTE_ROL: self._handle_participante_rol,
            EstadoFSM.PARTICIPANTE_OTRO: self._handle_participante_otro,
            EstadoFSM.CONFIRMACION: self._handle_confirmacion,
        }
        handler = handlers.get(estado)
        if handler is None:
            ctx = _clonar(contexto)
            return SalidaFSM(
                nuevo_estado=estado,
                mensaje="Estado no manejable.",
                contexto=ctx,
            )
        return handler(entrada, contexto)

    def cancelar(self, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje="Operación cancelada. Escribí /start para comenzar de nuevo.",
            contexto=ctx,
        )

    # ── private helpers ─────────────────────────────────────────────────────

    def _destinos_mensaje(self, destinos_sel: list[int]) -> str:
        lineas = []
        for numero, nombre in self._servicios:
            marca = "✅" if numero in destinos_sel else "⬜"
            lineas.append(f"{marca} {numero} — {nombre}")
        return "Seleccioná los destinos (podés elegir varios):\n" + "\n".join(lineas)

    def _opciones_destino(self) -> list[str]:
        opciones = [f"toggle:{n}" for n, _ in self._servicios]
        opciones.append("confirmar")
        return opciones

    # ── private handlers ────────────────────────────────────────────────────

    def _handle_tipo_reserva(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        tipo_map = {
            "INTERNO": TipoCliente.INTERNO,
            "EXTERNO": TipoCliente.EXTERNO,
            "DIGITAL": TipoCliente.DIGITAL,
        }
        tipo = tipo_map.get(entrada.strip().upper())
        if tipo is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.TIPO_RESERVA,
                mensaje="Opción inválida. Elegí INTERNO, EXTERNO o DIGITAL.",
                opciones=["INTERNO", "EXTERNO", "DIGITAL"],
                contexto=_clonar(contexto),
            )
        ctx = _clonar(contexto)
        ctx.tipo_cliente = tipo
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PUNTO_DE_VENTA,
            mensaje="¿Cuál es el punto de venta?",
            opciones=list(self._puntos_venta),
            contexto=ctx,
        )

    def _handle_punto_de_venta(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        if entrada.strip() == "Sin punto":
            ctx.punto_de_venta_nombre = None
        else:
            ctx.punto_de_venta_nombre = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.DESTINO,
            mensaje=self._destinos_mensaje(ctx.destinos_numeros),
            opciones=self._opciones_destino(),
            contexto=ctx,
        )

    def _handle_destino(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        if entrada.startswith("toggle:"):
            clave_str = entrada[len("toggle:"):]
            try:
                clave = int(clave_str)
            except ValueError:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.DESTINO,
                    mensaje=self._destinos_mensaje(ctx.destinos_numeros),
                    opciones=self._opciones_destino(),
                    contexto=ctx,
                )
            if clave in ctx.destinos_numeros:
                ctx.destinos_numeros.remove(clave)
            else:
                ctx.destinos_numeros.append(clave)
            return SalidaFSM(
                nuevo_estado=EstadoFSM.DESTINO,
                mensaje=self._destinos_mensaje(ctx.destinos_numeros),
                opciones=self._opciones_destino(),
                contexto=ctx,
            )
        if entrada.strip() == "confirmar":
            if not ctx.destinos_numeros:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.DESTINO,
                    mensaje="Tenés que seleccionar al menos un destino.\n"
                    + self._destinos_mensaje(ctx.destinos_numeros),
                    opciones=self._opciones_destino(),
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CLIENTE_NOMBRE,
                mensaje="¿Cuál es el nombre del cliente?",
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.DESTINO,
            mensaje=self._destinos_mensaje(ctx.destinos_numeros),
            opciones=self._opciones_destino(),
            contexto=ctx,
        )

    def _handle_cliente_nombre(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_nombre = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_TELEFONO,
            mensaje="¿Cuál es el teléfono del cliente?",
            contexto=ctx,
        )

    def _handle_cliente_telefono(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_telefono = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_HOTEL,
            mensaje="¿En qué hotel está hospedado el cliente?",
            contexto=ctx,
        )

    def _handle_cliente_hotel(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_hotel = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_HABITACION,
            mensaje="¿Cuál es el número de habitación?",
            contexto=ctx,
        )

    def _handle_cliente_habitacion(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_habitacion = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.FECHA_SALIDA,
            mensaje="¿Cuál es la fecha de salida? (formato: DD/MM o DD/MM/YYYY)",
            contexto=ctx,
        )

    def _handle_fecha_salida(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        fecha = _parsear_fecha(entrada)
        if fecha is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje="Fecha inválida. Usá el formato DD/MM o DD/MM/YYYY.",
                contexto=ctx,
            )
        ctx.fecha_salida = fecha
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PAX_ADULTOS,
            mensaje="¿Cuántos adultos? (mínimo 1)",
            contexto=ctx,
        )

    def _handle_pax_adultos(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        try:
            n = int(entrada.strip())
        except ValueError:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_ADULTOS,
                mensaje="Número inválido. Ingresá un entero mayor a 0.",
                contexto=ctx,
            )
        if n < 1:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_ADULTOS,
                mensaje="Debe haber al menos 1 adulto.",
                contexto=ctx,
            )
        ctx.adultos = n
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PAX_NINOS,
            mensaje="¿Cuántos niños? (puede ser 0)",
            contexto=ctx,
        )

    def _handle_pax_ninos(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        try:
            n = int(entrada.strip())
        except ValueError:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_NINOS,
                mensaje="Número inválido. Ingresá un entero >= 0.",
                contexto=ctx,
            )
        if n < 0:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_NINOS,
                mensaje="El número de niños no puede ser negativo.",
                contexto=ctx,
            )
        ctx.ninos = n
        return SalidaFSM(
            nuevo_estado=EstadoFSM.NUMERO_TICKET,
            mensaje="¿Cuál es el número de tiquetera? (ingresá 0 si no tenés el número)",
            contexto=ctx,
        )

    def _handle_numero_ticket(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        limpio = entrada.strip()
        if limpio == "0" or limpio.lower() in ("sin número", "sin numero", ""):
            ctx.numero_ticket = None
        else:
            try:
                ctx.numero_ticket = int(limpio)
            except ValueError:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.NUMERO_TICKET,
                    mensaje="Número inválido. Ingresá el número de tiquetera o 0 si no lo tenés.",
                    contexto=ctx,
                )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_VALOR,
            mensaje="¿Cuál es el valor total de la venta?",
            contexto=ctx,
        )

    def _handle_monto_valor(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        monto = _parsear_monto(entrada)
        if monto is None or monto <= Decimal("0"):
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_VALOR,
                mensaje="Monto inválido. Ingresá un valor positivo (ej: 500000 o 500.000).",
                contexto=ctx,
            )
        ctx.valor = monto
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_ABONO,
            mensaje="¿Cuánto abonó el cliente? (0 si no hubo abono)",
            contexto=ctx,
        )

    def _handle_monto_abono(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        monto = _parsear_monto(entrada)
        if monto is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_ABONO,
                mensaje="Monto inválido. Ingresá 0 si no hubo abono.",
                contexto=ctx,
            )
        ctx.abono = monto
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_NETO,
            mensaje="¿Cuál es el monto neto?",
            contexto=ctx,
        )

    def _handle_monto_neto(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        monto = _parsear_monto(entrada)
        if monto is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_NETO,
                mensaje="Monto inválido. Ingresá un número >= 0.",
                contexto=ctx,
            )
        if ctx.valor is not None and monto > ctx.valor:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_NETO,
                mensaje=f"El neto ({monto}) no puede superar el valor ({ctx.valor}).",
                contexto=ctx,
            )
        ctx.neto = monto
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_NOMBRE,
            mensaje="¿Cuál es tu nombre?",
            contexto=ctx,
        )

    def _handle_participante_nombre(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.vendedor_nombre = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje="¿Cuál fue tu rol en esta venta?",
            opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
            contexto=ctx,
        )

    def _handle_participante_rol(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        opcion = entrada.strip()
        if opcion == "Ambos":
            ctx.cerrador_nombre = ctx.vendedor_nombre
            ctx.rol_registrante = "ambos"
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "❌ Cancelar"],
                contexto=ctx,
            )
        if opcion == "Solo vendedor":
            ctx.rol_registrante = "vendedor"
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje="¿Cuál es el nombre del cerrador?",
                contexto=ctx,
            )
        if opcion == "Solo cerrador":
            ctx.rol_registrante = "cerrador"
            # swap: quien se registró es el cerrador, pedimos el vendedor
            ctx.cerrador_nombre = ctx.vendedor_nombre
            ctx.vendedor_nombre = None
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje="¿Cuál es el nombre del vendedor?",
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje="Opción inválida. Elegí: Ambos, Solo vendedor, o Solo cerrador.",
            opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
            contexto=ctx,
        )

    def _handle_participante_otro(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        if ctx.rol_registrante == "vendedor":
            ctx.cerrador_nombre = entrada.strip()
        else:  # cerrador
            ctx.vendedor_nombre = entrada.strip()
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CONFIRMACION,
            mensaje=self._construir_resumen(ctx),
            opciones=["✅ Confirmar", "❌ Cancelar"],
            contexto=ctx,
        )

    def _handle_confirmacion(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        if entrada.strip() == "✅ Confirmar":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.TERMINADO,
                mensaje="¡Venta registrada con éxito!",
                listo=True,
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje="Operación cancelada. Escribí /start para comenzar de nuevo.",
            contexto=ctx,
        )

    @staticmethod
    def _construir_resumen(ctx: ContextoVenta) -> str:
        destinos_str = (
            ", ".join(str(n) for n in ctx.destinos_numeros) if ctx.destinos_numeros else "—"
        )
        fecha_str = ctx.fecha_salida.strftime("%d/%m/%Y") if ctx.fecha_salida else "—"
        return (
            "📋 *Resumen de la venta:*\n"
            f"Tipo: {ctx.tipo_cliente or '—'}\n"
            f"Punto de venta: {ctx.punto_de_venta_nombre or 'Sin punto'}\n"
            f"Destinos: {destinos_str}\n"
            f"Cliente: {ctx.cliente_nombre or '—'}\n"
            f"Teléfono: {ctx.cliente_telefono or '—'}\n"
            f"Hotel: {ctx.cliente_hotel or '—'}\n"
            f"Habitación: {ctx.cliente_habitacion or '—'}\n"
            f"Fecha salida: {fecha_str}\n"
            f"Ticket N°: {ctx.numero_ticket or '—'}\n"
            f"Adultos: {ctx.adultos} | Niños: {ctx.ninos}\n"
            f"Valor: {ctx.valor or '—'}\n"
            f"Abono: {ctx.abono or '—'}\n"
            f"Neto: {ctx.neto or '—'}\n"
            f"Vendedor: {ctx.vendedor_nombre or '—'}\n"
            f"Cerrador: {ctx.cerrador_nombre or '—'}\n\n"
            "¿Confirmamos?"
        )
