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
from garay.mensajes.catalogo import obtener_mensaje


class EstadoFSM(StrEnum):
    METODO_INPUT = "metodo_input"
    ESPERANDO_FOTO = "esperando_foto"
    TIPO_RESERVA = "tipo_reserva"
    PUNTO_DE_VENTA = "punto_de_venta"
    DESTINO = "destino"
    CLIENTE_NOMBRE = "cliente_nombre"
    CLIENTE_TELEFONO = "cliente_telefono"
    CLIENTE_EMAIL = "cliente_email"
    CLIENTE_TIPO_ID = "cliente_tipo_id"
    CLIENTE_IDENTIFICACION = "cliente_identificacion"
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
    EDITAR_VENDEDOR = "editar_vendedor"
    EDITAR_CERRADOR = "editar_cerrador"
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
    ("Correo", EstadoFSM.CLIENTE_EMAIL),
    ("Identificación", EstadoFSM.CLIENTE_IDENTIFICACION),
    ("Hotel", EstadoFSM.CLIENTE_HOTEL),
    ("Habitación", EstadoFSM.CLIENTE_HABITACION),
    ("Fecha", EstadoFSM.FECHA_SALIDA),
    ("Adultos/Niños", EstadoFSM.PAX_ADULTOS),
    ("Monto valor", EstadoFSM.MONTO_VALOR),
    ("Abono", EstadoFSM.MONTO_ABONO),
    ("Participantes", EstadoFSM.EDITAR_VENDEDOR),
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
    # i18n debt: "(tú)" and "—" are user-visible strings bypassing the catalog
    return "(tú)" if rol in roles else "—"


def _parsear_monto(texto: str) -> Decimal | None:
    """Parse a Colombian peso amount string.

    Accepts full notation ('500000', '500.000') and miles shorthand ('500' → 500,000).
    Plain numbers < 1000 are treated as miles de pesos (Colombian everyday convention).
    """
    limpio = texto.strip().replace(".", "").replace(",", "")
    try:
        valor = Decimal(limpio)
        if valor < Decimal("0"):
            return None
        if Decimal("0") < valor < Decimal("1000"):
            valor = valor * 1000
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
            mensaje=obtener_mensaje("pregunta_metodo_input"),
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
            EstadoFSM.ESPERANDO_FOTO: self._handle_esperando_foto,
            EstadoFSM.TIPO_RESERVA: self._handle_tipo_reserva,
            EstadoFSM.PUNTO_DE_VENTA: self._handle_punto_de_venta,
            EstadoFSM.DESTINO: self._handle_destino,
            EstadoFSM.CLIENTE_NOMBRE: self._handle_cliente_nombre,
            EstadoFSM.CLIENTE_TELEFONO: self._handle_cliente_telefono,
            EstadoFSM.CLIENTE_EMAIL: self._handle_cliente_email,
            EstadoFSM.CLIENTE_TIPO_ID: self._handle_cliente_tipo_id,
            EstadoFSM.CLIENTE_IDENTIFICACION: self._handle_cliente_identificacion,
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
            EstadoFSM.EDITAR_VENDEDOR: self._handle_editar_vendedor,
            EstadoFSM.EDITAR_CERRADOR: self._handle_editar_cerrador,
        }
        handler = handlers.get(estado)
        if handler is None:
            ctx = _clonar(contexto)
            return SalidaFSM(
                nuevo_estado=estado,
                mensaje=obtener_mensaje("error_estado_no_manejable"),
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
        while salida.nuevo_estado in _ESTADOS_FOTO_AVANZAR and not salida.contexto.modo_edicion:
            valor = self._get_valor_prefilled(salida.nuevo_estado, salida.contexto)
            if valor is None:
                break
            salida = self.procesar(salida.nuevo_estado, valor, salida.contexto)
        return salida

    def cancelar(self, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje=obtener_mensaje("venta_cancelada"),
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
            return obtener_mensaje("info_destinos_seleccionados").format(
                seleccionados=", ".join(seleccionados)
            )
        # No selection: show instruction + optional IA hint
        lineas = [obtener_mensaje("pregunta_destino_numero")]
        if ctx.destinos_nombres:
            nombres = ", ".join(ctx.destinos_nombres)
            lineas.append(obtener_mensaje("info_ia_detecto_destinos").format(nombres=nombres))
        lineas.append(obtener_mensaje("info_sin_tours_seleccionados"))
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
        if opcion == "Manual":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.TIPO_RESERVA,
                mensaje=obtener_mensaje("pregunta_tipo_reserva"),
                opciones=["INTERNO", "EXTERNO", "DIGITAL"],
                contexto=ctx,
            )
        if opcion == "Foto":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.ESPERANDO_FOTO,
                mensaje=obtener_mensaje("pregunta_enviar_foto"),
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.METODO_INPUT,
            mensaje=obtener_mensaje("error_metodo_invalido"),
            opciones=["Manual", "Foto"],
            contexto=ctx,
        )

    def _handle_esperando_foto(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        return SalidaFSM(
            nuevo_estado=EstadoFSM.ESPERANDO_FOTO,
            mensaje=obtener_mensaje("error_esperando_foto_texto"),
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
                mensaje=obtener_mensaje("error_tipo_reserva_invalido"),
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
            mensaje=obtener_mensaje("pregunta_punto_de_venta"),
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
        if ctx.foto_modo:
            ctx.foto_modo = False
            computed = self._calcular_neto(ctx)
            if computed is not None:
                ctx.neto = computed
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
                mensaje=obtener_mensaje("pregunta_rol_venta"),
                opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
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
                    mensaje=(
                        obtener_mensaje("error_sin_destino_numero")
                        + "\n"
                        + self._destinos_mensaje(ctx)
                    ),
                    opciones=self._opciones_destino(ctx),
                    contexto=ctx,
                )
            if ctx.modo_edicion:
                ctx.modo_edicion = False
                computed = self._calcular_neto(ctx)
                if computed is not None:
                    ctx.neto = computed
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=self._construir_resumen(ctx),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CLIENTE_NOMBRE,
                mensaje=obtener_mensaje("pregunta_cliente_nombre"),
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
                mensaje=obtener_mensaje("error_destino_no_encontrado").format(
                    invalidos=", ".join(invalidos),
                    destinos_mensaje=self._destinos_mensaje(ctx),
                ),
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
            mensaje=obtener_mensaje("pregunta_cliente_telefono"),
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
            nuevo_estado=EstadoFSM.CLIENTE_EMAIL,
            mensaje=obtener_mensaje("pregunta_cliente_email"),
            contexto=ctx,
        )

    def _handle_cliente_email(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        email = entrada.strip()
        if "@" not in email:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CLIENTE_EMAIL,
                mensaje=obtener_mensaje("error_email_invalido"),
                contexto=ctx,
            )
        ctx.cliente_email = email
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_TIPO_ID,
            mensaje=obtener_mensaje("pregunta_cliente_tipo_id"),
            opciones=["CC", "NIT"],
            contexto=ctx,
        )

    def _handle_cliente_tipo_id(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        tipo = entrada.strip().upper()
        if tipo not in ("CC", "NIT"):
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CLIENTE_TIPO_ID,
                mensaje=obtener_mensaje("error_tipo_id_invalido"),
                opciones=["CC", "NIT"],
                contexto=ctx,
            )
        ctx.cliente_tipo_identificacion = tipo
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_IDENTIFICACION,
            mensaje=obtener_mensaje("pregunta_cliente_identificacion"),
            contexto=ctx,
        )

    def _handle_cliente_identificacion(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        identificacion = entrada.strip()
        if not identificacion:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CLIENTE_IDENTIFICACION,
                mensaje=obtener_mensaje("error_identificacion_vacia"),
                contexto=ctx,
            )
        ctx.cliente_identificacion = identificacion
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
            mensaje=obtener_mensaje("pregunta_cliente_hotel"),
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
                mensaje=obtener_mensaje("pregunta_fecha_salida"),
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
            mensaje=obtener_mensaje("pregunta_cliente_habitacion"),
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
            mensaje=obtener_mensaje("pregunta_fecha_salida"),
            contexto=ctx,
        )

    def _handle_fecha_salida(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        fecha = _parsear_fecha(entrada)
        if fecha is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje=obtener_mensaje("error_fecha_invalida"),
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
            mensaje=obtener_mensaje("pregunta_adultos"),
            contexto=ctx,
        )

    def _handle_pax_adultos(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        try:
            n = int(entrada.strip())
        except ValueError:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_ADULTOS,
                mensaje=obtener_mensaje("error_adultos_invalido"),
                contexto=ctx,
            )
        if n < 1:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_ADULTOS,
                mensaje=obtener_mensaje("error_adultos_minimo"),
                contexto=ctx,
            )
        ctx.adultos = n
        if ctx.modo_edicion:
            # Keep modo_edicion=True so PAX_NINOS handler returns to CONFIRMACION
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_NINOS,
                mensaje=obtener_mensaje("pregunta_ninos"),
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PAX_NINOS,
            mensaje=obtener_mensaje("pregunta_ninos"),
            contexto=ctx,
        )

    def _handle_pax_ninos(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        try:
            n = int(entrada.strip())
        except ValueError:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_NINOS,
                mensaje=obtener_mensaje("error_ninos_invalido"),
                contexto=ctx,
            )
        if n < 0:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PAX_NINOS,
                mensaje=obtener_mensaje("error_ninos_negativo"),
                contexto=ctx,
            )
        ctx.ninos = n
        if ctx.modo_edicion:
            ctx.modo_edicion = False
            computed = self._calcular_neto(ctx)
            if computed is not None:
                ctx.neto = computed
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_VALOR,
            mensaje=obtener_mensaje("pregunta_valor"),
            contexto=ctx,
        )

    def _handle_monto_valor(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        monto = _parsear_monto(entrada)
        if monto is None or monto <= Decimal("0"):
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_VALOR,
                mensaje=obtener_mensaje("error_monto_invalido"),
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
            mensaje=obtener_mensaje("pregunta_abono"),
            contexto=ctx,
        )

    def _handle_monto_abono(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        monto = _parsear_monto(entrada)
        if monto is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_ABONO,
                mensaje=obtener_mensaje("error_abono_invalido"),
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
                    mensaje=obtener_mensaje("error_abono_supera_neto").format(
                        abono=abono_fmt,
                        neto=neto_fmt,
                    ),
                    contexto=ctx,
                )
            if ctx.valor is not None and neto > ctx.valor:
                neto_fmt = _formatear_monto(neto)
                valor_fmt = _formatear_monto(ctx.valor)
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.MONTO_VALOR,
                    mensaje=obtener_mensaje("error_neto_supera_valor_detalle").format(
                        neto=neto_fmt,
                        valor=valor_fmt,
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
                mensaje=obtener_mensaje("pregunta_rol_venta"),
                opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_NETO,
            mensaje=obtener_mensaje("pregunta_neto_sin_precio"),
            contexto=ctx,
        )

    def _handle_monto_neto(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        monto = _parsear_monto(entrada)
        if monto is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_NETO,
                mensaje=obtener_mensaje("error_neto_invalido"),
                contexto=ctx,
            )
        if ctx.valor is not None and monto > ctx.valor:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_NETO,
                mensaje=obtener_mensaje("error_neto_supera_valor_monto_neto").format(
                    neto=_formatear_monto(monto),
                    valor=_formatear_monto(ctx.valor),
                ),
                contexto=ctx,
            )
        ctx.neto = monto
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje=obtener_mensaje("pregunta_rol_venta"),
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
                mensaje=obtener_mensaje("pregunta_participante_otro_cerrador"),
                contexto=ctx,
            )
        if opcion == "Solo cerrador":
            ctx.rol_registrante = "cerrador"
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje=obtener_mensaje("pregunta_participante_otro_vendedor"),
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje=obtener_mensaje("error_rol_invalido"),
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
                mensaje=obtener_mensaje("error_interno_rol_no_definido"),
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CONFIRMACION,
            mensaje=self._construir_resumen(ctx),
            opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
            contexto=ctx,
        )

    def _validar_datos_confirmacion(self, ctx: ContextoVenta) -> list[str]:
        """Return a list of missing required field labels for confirmation.

        An empty list means the context is complete and confirmation can proceed.
        """
        faltantes: list[str] = []
        if not ctx.cliente_nombre:
            faltantes.append("Nombre del cliente")
        if not ctx.cliente_telefono:
            faltantes.append("Teléfono")
        if not ctx.cliente_email:
            faltantes.append("Correo electrónico")
        if not ctx.cliente_identificacion:
            faltantes.append("Identificación")
        if ctx.tipo_cliente == "INTERNO":
            if not ctx.cliente_hotel:
                faltantes.append("Hotel")
            if not ctx.cliente_habitacion:
                faltantes.append("Habitación")
        if ctx.fecha_salida is None:
            faltantes.append("Fecha de salida")
        if ctx.adultos is None or ctx.adultos < 1:
            faltantes.append("Adultos (mínimo 1)")
        if ctx.ninos is None:
            faltantes.append("Niños (puede ser 0)")
        if not ctx.destinos_numeros:
            faltantes.append("Destinos (pendientes de confirmar)")
        if ctx.valor is None:
            faltantes.append("Valor total")
        if ctx.abono is None:
            faltantes.append("Abono")
        if not ctx.tipo_cliente:
            faltantes.append("Tipo de reserva")
        if not ctx.punto_de_venta_nombre:
            faltantes.append("Punto de venta")
        if not ctx.rol_registrante:
            faltantes.append("Participantes (vendedor/cerrador)")
        return faltantes

    def _handle_confirmacion(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        if entrada.strip() == "✅ Confirmar":
            faltantes = self._validar_datos_confirmacion(ctx)
            if faltantes:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=(
                        obtener_mensaje("error_datos_incompletos").format(
                            campos="\n• ".join(faltantes)
                        )
                        + "\n\n"
                        + self._construir_resumen(ctx)
                    ),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.TERMINADO,
                mensaje=obtener_mensaje("confirmacion_venta_exitosa"),
                listo=True,
                contexto=ctx,
            )
        if entrada.strip() == "✏️ Editar":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("pregunta_campo_editar"),
                opciones=[label for label, _ in _CAMPOS_EDITABLES],
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje=obtener_mensaje("venta_cancelada"),
            contexto=ctx,
        )

    def _handle_editar_selector(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        campo_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        estado_destino = campo_map.get(entrada.strip())
        if estado_destino is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("error_campo_editar_invalido"),
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

    def _handle_editar_vendedor(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.vendedor_nombre = entrada.strip()
        if ctx.rol_registrante == "ambos":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_CERRADOR,
                mensaje=obtener_mensaje("pregunta_editar_cerrador").format(
                    actual=ctx.cerrador_nombre or "—"
                ),
                contexto=ctx,
            )
        ctx.modo_edicion = False
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CONFIRMACION,
            mensaje=self._construir_resumen(ctx),
            opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
            contexto=ctx,
        )

    def _handle_editar_cerrador(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.cerrador_nombre = entrada.strip()
        ctx.modo_edicion = False
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CONFIRMACION,
            mensaje=self._construir_resumen(ctx),
            opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
            contexto=ctx,
        )

    def _mensaje_para_estado(self, estado: EstadoFSM, ctx: ContextoVenta) -> str:
        msgs: dict[EstadoFSM, str] = {
            EstadoFSM.TIPO_RESERVA: obtener_mensaje("pregunta_tipo_reserva"),
            EstadoFSM.PUNTO_DE_VENTA: obtener_mensaje("pregunta_punto_de_venta"),
            EstadoFSM.DESTINO: self._destinos_mensaje(ctx),
            EstadoFSM.CLIENTE_NOMBRE: obtener_mensaje("pregunta_editar_cliente_nombre").format(
                actual=ctx.cliente_nombre or "—"
            ),
            EstadoFSM.CLIENTE_TELEFONO: obtener_mensaje("pregunta_editar_cliente_telefono").format(
                actual=ctx.cliente_telefono or "—"
            ),
            EstadoFSM.CLIENTE_EMAIL: obtener_mensaje("pregunta_editar_cliente_email").format(
                actual=ctx.cliente_email or "—"
            ),
            EstadoFSM.CLIENTE_IDENTIFICACION: obtener_mensaje(
                "pregunta_editar_cliente_identificacion"
            ).format(actual=ctx.cliente_identificacion or "—"),
            EstadoFSM.CLIENTE_HOTEL: obtener_mensaje("pregunta_editar_cliente_hotel").format(
                actual="Sin hotel" if ctx.sin_hotel else (ctx.cliente_hotel or "—")
            ),
            EstadoFSM.CLIENTE_HABITACION: obtener_mensaje(
                "pregunta_editar_cliente_habitacion"
            ).format(actual=ctx.cliente_habitacion or "—"),
            EstadoFSM.FECHA_SALIDA: obtener_mensaje("pregunta_editar_fecha_salida").format(
                actual=ctx.fecha_salida.strftime("%d/%m/%Y %H:%M") if ctx.fecha_salida else "—"
            ),
            EstadoFSM.PAX_ADULTOS: obtener_mensaje("pregunta_editar_adultos_ninos").format(
                adultos=ctx.adultos if ctx.adultos is not None else "—",
                ninos=ctx.ninos if ctx.ninos is not None else "—",
            ),
            EstadoFSM.MONTO_VALOR: obtener_mensaje("pregunta_editar_monto_valor").format(
                actual=_formatear_monto(ctx.valor)
            ),
            EstadoFSM.MONTO_ABONO: obtener_mensaje("pregunta_editar_monto_abono").format(
                actual=_formatear_monto(ctx.abono)
            ),
            EstadoFSM.PARTICIPANTE_ROL: obtener_mensaje("pregunta_rol_venta"),
            EstadoFSM.EDITAR_VENDEDOR: obtener_mensaje("pregunta_editar_vendedor").format(
                actual=ctx.vendedor_nombre or "—"
            ),
            EstadoFSM.EDITAR_CERRADOR: obtener_mensaje("pregunta_editar_cerrador").format(
                actual=ctx.cerrador_nombre or "—"
            ),
        }
        return msgs.get(estado, "")

    def _opciones_para_estado(self, estado: EstadoFSM, ctx: ContextoVenta) -> list[str]:
        opts: dict[EstadoFSM, list[str]] = {
            EstadoFSM.TIPO_RESERVA: ["INTERNO", "EXTERNO", "DIGITAL"],
            EstadoFSM.PUNTO_DE_VENTA: list(self._puntos_venta),
            EstadoFSM.DESTINO: self._opciones_destino(ctx),
            EstadoFSM.CLIENTE_TIPO_ID: ["CC", "NIT"],
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
        vendedor_str = ctx.vendedor_nombre or _tú_si(ctx.rol_registrante, "ambos", "vendedor")
        cerrador_str = ctx.cerrador_nombre or _tú_si(ctx.rol_registrante, "ambos", "cerrador")
        return obtener_mensaje("confirmacion_resumen").format(
            tipo=ctx.tipo_cliente or "—",
            punto_de_venta=ctx.punto_de_venta_nombre or "Sin punto",
            destinos=destinos_str,
            cliente_nombre=ctx.cliente_nombre or "—",
            cliente_telefono=ctx.cliente_telefono or "—",
            cliente_email=ctx.cliente_email or "—",
            cliente_identificacion=ctx.cliente_identificacion or "—",
            cliente_hotel=hotel_str,
            cliente_habitacion=hab_str,
            fecha_salida=fecha_str,
            adultos=ctx.adultos or 0,
            ninos=ctx.ninos or 0,
            valor=_formatear_monto(ctx.valor),
            abono=_formatear_monto(ctx.abono),
            neto=_formatear_monto(ctx.neto),
            vendedor=vendedor_str,
            cerrador=cerrador_str,
        )
