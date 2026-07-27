"""Pure FSM for the Telegram bot conversation flow.

No Telegram imports. Fully testable in isolation.
"""

from __future__ import annotations

import copy
import datetime
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from rapidfuzz import fuzz

from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta


class EstadoFSM(StrEnum):
    METODO_INPUT = "metodo_input"
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
    MONTO_VALOR = "monto_valor"
    MONTO_ABONO = "monto_abono"
    MONTO_NETO = "monto_neto"
    PARTICIPANTE_ROL = "participante_rol"
    PARTICIPANTE_OTRO = "participante_otro"
    CONFIRMACION = "confirmacion"
    EDITAR_SELECTOR = "editar_selector"
    TERMINADO = "terminado"
    CANCELADO = "cancelado"


@dataclass(frozen=True)
class SalidaFSM:
    nuevo_estado: EstadoFSM
    mensaje: str
    opciones: list[str] = field(default_factory=list)
    listo: bool = False
    contexto: ContextoVenta = field(default_factory=ContextoVenta)


_ESTADOS_FOTO_AVANZAR: frozenset[EstadoFSM] = frozenset(
    {
        EstadoFSM.CLIENTE_NOMBRE,
        EstadoFSM.CLIENTE_TELEFONO,
        EstadoFSM.CLIENTE_HOTEL,
        EstadoFSM.CLIENTE_HABITACION,
        EstadoFSM.FECHA_SALIDA,
        EstadoFSM.PAX_ADULTOS,
        EstadoFSM.PAX_NINOS,
    }
)

_SIN_HOTEL_EXACTOS: frozenset[str] = frozenset(
    {
        "no",
        "no.",
        "n/a",
        "na",
        "sin hotel",
        "no hotel",
        "sin",
        "ninguno",
        "ningún",
        "ninguna",
        "no hay",
        "no tengo",
        "no tiene",
        "no estoy",
        "no esta",
        "no está",
        "fuera",
        "sin hospedaje",
    }
)


def _es_sin_hotel(entrada: str) -> bool:
    """Return True when the input clearly means 'no hotel'."""
    t = entrada.strip().lower()
    if t in _SIN_HOTEL_EXACTOS:
        return True
    # Short phrase starting with "no " or "sin " is likely no-hotel
    if len(t) <= 35 and (t.startswith("no ") or t.startswith("sin ")):
        return True
    # Fuzzy match for short inputs — catches common typos (e.g. "nignuno" → "ninguno")
    if len(t) <= 15:
        return any(fuzz.ratio(t, known) >= 80 for known in _SIN_HOTEL_EXACTOS)
    return False


_CAMPOS_EDITABLES: list[tuple[str, EstadoFSM]] = [
    ("Tipo reserva", EstadoFSM.TIPO_RESERVA),
    ("Punto de venta", EstadoFSM.PUNTO_DE_VENTA),
    ("Destinos", EstadoFSM.DESTINO),
    ("Cliente", EstadoFSM.CLIENTE_NOMBRE),
    ("Teléfono", EstadoFSM.CLIENTE_TELEFONO),
    ("Hotel", EstadoFSM.CLIENTE_HOTEL),
    ("Fecha", EstadoFSM.FECHA_SALIDA),
    ("Adultos/Niños", EstadoFSM.PAX_ADULTOS),
    ("Monto valor", EstadoFSM.MONTO_VALOR),
    ("Abono", EstadoFSM.MONTO_ABONO),
    ("Participantes", EstadoFSM.PARTICIPANTE_ROL),
]


def _formatear_monto(valor: Decimal | int | None) -> str:
    """Format amount as Colombian pesos. E.g.: 200000 → '$200.000'"""
    if valor is None:
        return "—"
    return "$" + f"{int(valor):,}".replace(",", ".")


def _clonar(ctx: ContextoVenta) -> ContextoVenta:
    return copy.deepcopy(ctx)


def _tú_si(rol: str | None, *roles: str) -> str:
    """Return '(tú)' when `rol` is in `roles`, otherwise '—'."""
    return "(tú)" if rol in roles else "—"


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
    """Try DD/MM, DD/MM/YY, DD/MM/YYYY, DD/MM/YYYY HH:MM."""
    texto = texto.strip()
    now = datetime.datetime.now()
    formatos_con_año = ["%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%m/%y"]
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
        servicios: list[tuple[int, str, Decimal | None, Decimal | None]],
        puntos_venta: list[str],
    ) -> None:
        # dict for O(1) lookup: numero → (nombre, neto_adulto, neto_nino)
        self._servicios: dict[int, tuple[str, Decimal | None, Decimal | None]] = {
            n: (nombre, neto_a, neto_n) for n, nombre, neto_a, neto_n in servicios
        }
        self._puntos_venta = puntos_venta

    def iniciar(self) -> SalidaFSM:
        return SalidaFSM(
            nuevo_estado=EstadoFSM.METODO_INPUT,
            mensaje=(
                "¿Cómo querés registrar la venta?\n\n"
                "_Podés modificar cualquier dato en el resumen antes de confirmar._"
            ),
            opciones=["Manual", "Foto"],
            contexto=ContextoVenta(),
        )

    def procesar(
        self,
        estado: EstadoFSM,
        entrada: str,
        contexto: ContextoVenta,
    ) -> SalidaFSM:
        handlers = {
            EstadoFSM.METODO_INPUT: self._handle_metodo_input,
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
            EstadoFSM.MONTO_VALOR: self._handle_monto_valor,
            EstadoFSM.MONTO_ABONO: self._handle_monto_abono,
            EstadoFSM.MONTO_NETO: self._handle_monto_neto,
            EstadoFSM.PARTICIPANTE_ROL: self._handle_participante_rol,
            EstadoFSM.PARTICIPANTE_OTRO: self._handle_participante_otro,
            EstadoFSM.CONFIRMACION: self._handle_confirmacion,
            EstadoFSM.EDITAR_SELECTOR: self._handle_editar_selector,
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

    def procesar_foto(
        self,
        estado: EstadoFSM,
        entrada: str,
        ctx: ContextoVenta,
    ) -> SalidaFSM:
        """Like procesar() but auto-advances through photo-prefilled states."""
        salida = self.procesar(estado, entrada, ctx)
        while salida.nuevo_estado in _ESTADOS_FOTO_AVANZAR:
            valor = self._get_valor_prefilled(salida.nuevo_estado, salida.contexto)
            if valor is None:
                break
            salida = self.procesar(salida.nuevo_estado, valor, salida.contexto)
        return salida

    def cancelar(self, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje="Operación cancelada. Escribí /start para comenzar de nuevo.",
            contexto=ctx,
        )

    # ── private helpers ─────────────────────────────────────────────────────

    def _destinos_mensaje(self, ctx: ContextoVenta) -> str:
        if ctx.destinos_numeros:
            # With selection: show only what is selected + prompt to add/confirm
            seleccionados = []
            num_map = {n: info[0] for n, info in self._servicios.items()}
            for n in ctx.destinos_numeros:
                nombre = num_map.get(n, str(n))
                seleccionados.append(f"{n} — {nombre}")
            return (
                f"Seleccionados: {', '.join(seleccionados)}\n"
                "Agregá más números o escribí *confirmar* para continuar."
            )
        # No selection: show instruction + optional IA hint
        lineas = [
            "Ingresá el número del tour "
            "(podés poner varios separados por coma, ej: *15* o *15, 23*)."
        ]
        if ctx.destinos_nombres:
            nombres = ', '.join(ctx.destinos_nombres)
            lineas.append(
                f"La IA detectó: {nombres} (ingresá los números correspondientes)."
            )
        lineas.append("Aún no seleccionaste ningún tour.")
        return "\n".join(lineas)

    def _opciones_destino(self, ctx: ContextoVenta) -> list[str]:
        return ["confirmar"] if ctx.destinos_numeros else []

    def _calcular_neto(self, ctx: ContextoVenta) -> Decimal | None:
        """Sum neto across all selected services. Returns None if any service lacks pricing."""
        if not ctx.destinos_numeros or ctx.adultos is None:
            return None
        total = Decimal("0")
        for numero in ctx.destinos_numeros:
            info = self._servicios.get(numero)
            if info is None:
                return None
            _, neto_adulto, neto_nino = info
            if neto_adulto is None:
                return None
            total += neto_adulto * ctx.adultos
            if ctx.ninos and ctx.ninos > 0:
                # Business rule: neto_nino=None → use neto_adulto as proxy price
                efectivo_nino = neto_nino if neto_nino is not None else neto_adulto
                total += efectivo_nino * ctx.ninos
        return total

    # ── private handlers ────────────────────────────────────────────────────

    def _handle_metodo_input(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        opcion = entrada.strip()
        if opcion in ("Manual", "Foto"):
            return SalidaFSM(
                nuevo_estado=EstadoFSM.TIPO_RESERVA,
                mensaje="¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO, DIGITAL",
                opciones=["INTERNO", "EXTERNO", "DIGITAL"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.METODO_INPUT,
            mensaje="Opción inválida. Elegí Manual o Foto.",
            opciones=["Manual", "Foto"],
            contexto=ctx,
        )

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
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
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
        if ctx.destinos_nombres:
            nombres_norm = {n.lower().strip() for n in ctx.destinos_nombres}
            for numero, (nombre, _, _) in self._servicios.items():
                if nombre.lower().strip() in nombres_norm and numero not in ctx.destinos_numeros:
                    ctx.destinos_numeros.append(numero)
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.DESTINO,
            mensaje=self._destinos_mensaje(ctx),
            opciones=self._opciones_destino(ctx),
            contexto=ctx,
        )

    def _handle_destino(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        texto = entrada.strip()

        if texto.lower() in ("confirmar", "listo"):
            if not ctx.destinos_numeros:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.DESTINO,
                    mensaje="Tenés que ingresar al menos un número de tour.\n"
                    + self._destinos_mensaje(ctx),
                    opciones=self._opciones_destino(ctx),
                    contexto=ctx,
                )
            if ctx.modo_edicion:
                ctx.modo_edicion = False
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=self._construir_resumen(ctx),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CLIENTE_NOMBRE,
                mensaje="¿Cuál es el nombre del cliente?",
                contexto=ctx,
            )

        # Deselection: "-15" or "-15, 23"
        if texto.startswith("-"):
            partes_quitar = [
                p.strip().lstrip("-")
                for p in texto.replace(",", " ").split()
                if p.strip().lstrip("-")
            ]
            for parte in partes_quitar:
                try:
                    n = int(parte)
                    if n in ctx.destinos_numeros:
                        ctx.destinos_numeros.remove(n)
                except ValueError:
                    pass
            return SalidaFSM(
                nuevo_estado=EstadoFSM.DESTINO,
                mensaje=self._destinos_mensaje(ctx),
                opciones=self._opciones_destino(ctx),
                contexto=ctx,
            )

        numeros_validos = set(self._servicios.keys())
        partes = [p.strip() for p in texto.replace(",", " ").split() if p.strip()]
        invalidos: list[str] = []
        for parte in partes:
            try:
                n = int(parte)
                if n in numeros_validos:
                    if n not in ctx.destinos_numeros:
                        ctx.destinos_numeros.append(n)
                else:
                    invalidos.append(parte)
            except ValueError:
                invalidos.append(parte)

        if invalidos and not ctx.destinos_numeros:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.DESTINO,
                mensaje=f"Número(s) no encontrado(s): {', '.join(invalidos)}. Revisá el catálogo.\n"
                + self._destinos_mensaje(ctx),
                opciones=self._opciones_destino(ctx),
                contexto=ctx,
            )

        return SalidaFSM(
            nuevo_estado=EstadoFSM.DESTINO,
            mensaje=self._destinos_mensaje(ctx),
            opciones=self._opciones_destino(ctx),
            contexto=ctx,
        )

    def _handle_cliente_nombre(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_nombre = entrada.strip()
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_TELEFONO,
            mensaje="¿Cuál es el teléfono del cliente?",
            contexto=ctx,
        )

    def _handle_cliente_telefono(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_telefono = entrada.strip()
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_HOTEL,
            mensaje="¿En qué hotel está hospedado el cliente?",
            contexto=ctx,
        )

    def _handle_cliente_hotel(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        if _es_sin_hotel(entrada):
            ctx.sin_hotel = True
            ctx.cliente_hotel = None
            ctx.cliente_habitacion = None
            if ctx.modo_edicion:
                ctx.modo_edicion = False
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=self._construir_resumen(ctx),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje="¿Cuál es la fecha de salida? (formato: DD/MM, DD/MM/YY o DD/MM/YYYY)",
                contexto=ctx,
            )
        ctx.sin_hotel = False
        ctx.cliente_hotel = entrada.strip()
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_HABITACION,
            mensaje="¿Cuál es el número de habitación?",
            contexto=ctx,
        )

    def _handle_cliente_habitacion(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cliente_habitacion = entrada.strip()
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.FECHA_SALIDA,
            mensaje="¿Cuál es la fecha de salida? (formato: DD/MM, DD/MM/YY o DD/MM/YYYY)",
            contexto=ctx,
        )

    def _handle_fecha_salida(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        fecha = _parsear_fecha(entrada)
        if fecha is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje="Fecha inválida. Usá el formato DD/MM, DD/MM/YY o DD/MM/YYYY.",
                contexto=ctx,
            )
        ctx.fecha_salida = fecha
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
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
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
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
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
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
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
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
        neto = self._calcular_neto(ctx)
        if neto is not None:
            if ctx.abono > neto:
                abono_fmt = _formatear_monto(monto)
                neto_fmt = _formatear_monto(neto)
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.MONTO_ABONO,
                    mensaje=(
                        f"El abono ({abono_fmt}) no puede superar "
                        f"el neto calculado ({neto_fmt})."
                    ),
                    contexto=ctx,
                )
            if ctx.valor is not None and neto > ctx.valor:
                neto_fmt = _formatear_monto(neto)
                valor_fmt = _formatear_monto(ctx.valor)
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.MONTO_VALOR,
                    mensaje=(
                        f"El neto calculado ({neto_fmt}) supera el valor de la venta "
                        f"({valor_fmt}). Ingresá un valor mayor o igual a {neto_fmt}."
                    ),
                    contexto=ctx,
                )
            ctx.neto = neto
            if ctx.modo_edicion:
                ctx.modo_edicion = False
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=self._construir_resumen(ctx),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
                mensaje="¿Cuál fue tu rol en esta venta?",
                opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_NETO,
            mensaje=(
                "¿Cuál es el monto neto? "
                "(no se encontró precio en el catálogo para algún tour seleccionado)"
            ),
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
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje="¿Cuál fue tu rol en esta venta?",
            opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
            contexto=ctx,
        )

    def _handle_participante_rol(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        opcion = entrada.strip()
        if opcion == "Ambos":
            ctx.rol_registrante = "ambos"
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
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
        elif ctx.rol_registrante == "cerrador":
            ctx.vendedor_nombre = entrada.strip()
        else:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje="Error interno: rol no definido. Escribí /cancelar y comenzá de nuevo.",
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CONFIRMACION,
            mensaje=self._construir_resumen(ctx),
            opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
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
        if entrada.strip() == "✏️ Editar":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje="¿Qué campo querés modificar?",
                opciones=[label for label, _ in _CAMPOS_EDITABLES],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje="Operación cancelada. Escribí /start para comenzar de nuevo.",
            contexto=ctx,
        )

    def _handle_editar_selector(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        campo_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        estado_destino = campo_map.get(entrada.strip())
        if estado_destino is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje="Opción inválida. Elegí uno de los campos.",
                opciones=[label for label, _ in _CAMPOS_EDITABLES],
                contexto=ctx,
            )
        ctx.modo_edicion = True
        return SalidaFSM(
            nuevo_estado=estado_destino,
            mensaje=self._mensaje_para_estado(estado_destino, ctx),
            opciones=self._opciones_para_estado(estado_destino, ctx),
            contexto=ctx,
        )

    def _mensaje_para_estado(self, estado: EstadoFSM, ctx: ContextoVenta) -> str:
        msgs: dict[EstadoFSM, str] = {
            EstadoFSM.TIPO_RESERVA: "¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO, DIGITAL",
            EstadoFSM.PUNTO_DE_VENTA: "¿Cuál es el punto de venta?",
            EstadoFSM.DESTINO: self._destinos_mensaje(ctx),
            EstadoFSM.CLIENTE_NOMBRE: "¿Cuál es el nombre del cliente?",
            EstadoFSM.CLIENTE_TELEFONO: "¿Cuál es el teléfono del cliente?",
            EstadoFSM.CLIENTE_HOTEL: (
                "¿En qué hotel está hospedado el cliente? (escribí 'no' si no aplica)"
            ),
            EstadoFSM.FECHA_SALIDA: "¿Cuál es la fecha de salida? (DD/MM, DD/MM/YY o DD/MM/YYYY)",
            EstadoFSM.PAX_ADULTOS: "¿Cuántos adultos? (mínimo 1)",
            EstadoFSM.MONTO_VALOR: "¿Cuál es el valor total de la venta?",
            EstadoFSM.MONTO_ABONO: "¿Cuánto abonó el cliente? (0 si no hubo abono)",
            EstadoFSM.PARTICIPANTE_ROL: "¿Cuál fue tu rol en esta venta?",
        }
        return msgs.get(estado, "")

    def _opciones_para_estado(self, estado: EstadoFSM, ctx: ContextoVenta) -> list[str]:
        opts: dict[EstadoFSM, list[str]] = {
            EstadoFSM.TIPO_RESERVA: ["INTERNO", "EXTERNO", "DIGITAL"],
            EstadoFSM.PUNTO_DE_VENTA: list(self._puntos_venta),
            EstadoFSM.DESTINO: self._opciones_destino(ctx),
            EstadoFSM.PARTICIPANTE_ROL: ["Ambos", "Solo vendedor", "Solo cerrador"],
        }
        return opts.get(estado, [])

    def _get_valor_prefilled(self, estado: EstadoFSM, ctx: ContextoVenta) -> str | None:
        if estado == EstadoFSM.CLIENTE_NOMBRE:
            return ctx.cliente_nombre
        if estado == EstadoFSM.CLIENTE_TELEFONO:
            return ctx.cliente_telefono
        if estado == EstadoFSM.CLIENTE_HOTEL:
            if ctx.sin_hotel:
                return "no"
            return ctx.cliente_hotel
        if estado == EstadoFSM.CLIENTE_HABITACION:
            return ctx.cliente_habitacion
        if estado == EstadoFSM.FECHA_SALIDA:
            return ctx.fecha_salida.strftime("%d/%m/%Y %H:%M") if ctx.fecha_salida else None
        if estado == EstadoFSM.PAX_ADULTOS:
            return str(ctx.adultos) if ctx.adultos is not None and ctx.adultos >= 1 else None
        if estado == EstadoFSM.PAX_NINOS:
            return str(ctx.ninos) if ctx.ninos is not None else None
        if estado == EstadoFSM.MONTO_VALOR:
            return str(ctx.valor) if ctx.valor is not None else None
        if estado == EstadoFSM.MONTO_ABONO:
            return str(ctx.abono) if ctx.abono is not None else None
        return None

    def _construir_resumen(self, ctx: ContextoVenta) -> str:
        if ctx.destinos_numeros:
            nombres = [self._servicios[n][0] for n in ctx.destinos_numeros if n in self._servicios]
            destinos_str = (
                ", ".join(nombres) if nombres else ", ".join(str(n) for n in ctx.destinos_numeros)
            )
        elif ctx.destinos_nombres:
            destinos_str = ", ".join(ctx.destinos_nombres) + " (pendiente confirmar)"
        else:
            destinos_str = "—"
        fecha_str = ctx.fecha_salida.strftime("%d/%m/%Y") if ctx.fecha_salida else "—"
        hotel_str = "Sin hotel" if ctx.sin_hotel else (ctx.cliente_hotel or "—")
        hab_str = "—" if ctx.sin_hotel else (ctx.cliente_habitacion or "—")
        return (
            "📋 *Resumen de la venta:*\n"
            f"Tipo: {ctx.tipo_cliente or '—'}\n"
            f"Punto de venta: {ctx.punto_de_venta_nombre or 'Sin punto'}\n"
            f"Destinos: {destinos_str}\n"
            f"Cliente: {ctx.cliente_nombre or '—'}\n"
            f"Teléfono: {ctx.cliente_telefono or '—'}\n"
            f"Hotel: {hotel_str}\n"
            f"Habitación: {hab_str}\n"
            f"Fecha salida: {fecha_str}\n"
            f"Adultos: {ctx.adultos or 0} | Niños: {ctx.ninos or 0}\n"
            f"Valor: {_formatear_monto(ctx.valor)}\n"
            f"Abono: {_formatear_monto(ctx.abono)}\n"
            f"Neto: {_formatear_monto(ctx.neto)}\n"
            f"Vendedor: {ctx.vendedor_nombre or _tú_si(ctx.rol_registrante, 'ambos', 'vendedor')}\n"
            "Cerrador: "
            f"{ctx.cerrador_nombre or _tú_si(ctx.rol_registrante, 'ambos', 'cerrador')}\n\n"
            "¿Confirmamos?"
        )
