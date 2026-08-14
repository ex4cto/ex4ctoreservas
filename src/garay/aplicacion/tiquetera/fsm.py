"""Pure FSM for the Telegram bot conversation flow.

No Telegram imports. Fully testable in isolation.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from rapidfuzz import fuzz

from garay.aplicacion.comun.fechas import (
    formatear_fechas_compactas,
)
from garay.aplicacion.comun.fechas import (
    parsear_fecha as _parsear_fecha,
)
from garay.dominio.comun.tipos import CanalOrigen, TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.mensajes.catalogo import obtener_mensaje


class EstadoFSM(StrEnum):
    METODO_INPUT = "metodo_input"
    ESPERANDO_FOTO = "esperando_foto"
    MODALIDAD_VENTA = "modalidad_venta"
    TIPO_RESERVA = "tipo_reserva"
    CANAL_ORIGEN = "canal_origen"
    PUNTO_DE_VENTA = "punto_de_venta"
    FAMILIA = "familia"
    SERVICIO_EN_FAMILIA = "servicio_en_familia"
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
    OTRO_TOUR = "otro_tour"
    TERMINADO = "terminado"
    CANCELADO = "cancelado"


@dataclass(frozen=True)
class SalidaFSM:
    nuevo_estado: EstadoFSM
    mensaje: str
    opciones: list[str] = field(default_factory=list)
    listo: bool = False
    contexto: ContextoVenta = field(default_factory=ContextoVenta)
    # Structured options carry (label, callback_data) pairs. When set, the
    # Telegram adapter renders these (encoded callback_data, multi-column grid)
    # instead of the plain `opciones` list where label == callback_data.
    opciones_estructuradas: list[tuple[str, str]] | None = None


_ESTADOS_FOTO_AVANZAR: frozenset[EstadoFSM] = frozenset(
    {
        EstadoFSM.CLIENTE_NOMBRE,
        EstadoFSM.CLIENTE_TELEFONO,
        EstadoFSM.CLIENTE_HOTEL,
        EstadoFSM.CLIENTE_HABITACION,
        EstadoFSM.FECHA_SALIDA,
        EstadoFSM.PAX_ADULTOS,
        EstadoFSM.PAX_NINOS,
        EstadoFSM.PUNTO_DE_VENTA,  # presencial only; DIGITAL never reaches this state
        EstadoFSM.MODALIDAD_VENTA,  # photo entry starts here; auto-advanceable
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
    ("Modalidad", EstadoFSM.MODALIDAD_VENTA),
    ("Tipo reserva", EstadoFSM.TIPO_RESERVA),
    ("Canal de origen", EstadoFSM.CANAL_ORIGEN),
    ("Punto de venta", EstadoFSM.PUNTO_DE_VENTA),
    ("Destinos", EstadoFSM.FAMILIA),
    ("Nombre cliente", EstadoFSM.CLIENTE_NOMBRE),
    ("Teléfono", EstadoFSM.CLIENTE_TELEFONO),
    ("Correo", EstadoFSM.CLIENTE_EMAIL),
    ("Identificación", EstadoFSM.CLIENTE_IDENTIFICACION),
    ("Hotel", EstadoFSM.CLIENTE_HOTEL),
    ("Habitación", EstadoFSM.CLIENTE_HABITACION),
    ("Fecha de salida", EstadoFSM.FECHA_SALIDA),
    ("Adultos/Niños", EstadoFSM.PAX_ADULTOS),
    ("Valor de venta", EstadoFSM.MONTO_VALOR),
    ("Abono", EstadoFSM.MONTO_ABONO),
    ("Vendedor/Cerrador", EstadoFSM.EDITAR_VENDEDOR),
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


def _siguiente_tour_sin_fecha(ctx: ContextoVenta) -> int | None:
    """Return the numero of the first tour in ctx.destinos_numeros that has no date yet.

    Returns None when every tour already has a date in ctx.fechas_por_servicio, or when
    ctx.destinos_numeros is empty (bare context / legacy path).
    """
    for numero in ctx.destinos_numeros:
        if numero not in ctx.fechas_por_servicio:
            return numero
    return None


class FSMTiquetera:
    """Pure finite state machine for the Telegram sale-registration conversation."""

    @staticmethod
    def _build_catalog(
        servicios: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]],
    ) -> tuple[
        dict[int, tuple[str, Decimal | None, Decimal | None]],
        dict[str, list[int]],
        dict[int, list[str]],
    ]:
        """Build catalog dicts from a flat list of 6-element service tuples.

        The 6th element (horarios) is stored in a separate dict so that the
        internal 3-tuple layout of _servicios is preserved unchanged and all
        existing unpack-sites remain valid.

        Returns:
            (_servicios, _familias, _horarios) — same structure as instance attrs.
        """
        servicios_dict: dict[int, tuple[str, Decimal | None, Decimal | None]] = {
            n: (nombre, neto_a, neto_n)
            for n, nombre, neto_a, neto_n, _cat, _hor in servicios
        }
        horarios_dict: dict[int, list[str]] = {
            n: list(hor) for n, _nombre, _a, _n, _cat, hor in servicios
        }
        familias_raw: dict[str, list[int]] = {}
        for numero, _nombre, _neto_a, _neto_n, categoria, _hor in servicios:
            familias_raw.setdefault(categoria, []).append(numero)
        familias_dict: dict[str, list[int]] = {
            categoria: sorted(numeros)
            for categoria, numeros in sorted(familias_raw.items())
            if numeros
        }
        return servicios_dict, familias_dict, horarios_dict

    def __init__(
        self,
        servicios: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]],
        puntos_venta: list[str],
        freelancers: list[tuple[uuid.UUID, str, bool]] | None = None,
        multi_tour_habilitado: bool = False,
    ) -> None:
        # dict for O(1) lookup: numero → (nombre, neto_adulto, neto_nino)
        # categoria → sorted list of service numeros (only non-empty families).
        # numero → list of configured departure times (empty = no time prompt).
        self._servicios, self._familias, self._horarios = self._build_catalog(servicios)
        self._puntos_venta = puntos_venta
        # Roster of (id, nombre, activo) for the counterpart picker.
        self._freelancers: list[tuple[uuid.UUID, str, bool]] = freelancers or []
        # Feature flag: False = one tour per reservation (default).
        # True = legacy multi-tour accumulator (DORMANT by default).
        self._multi_tour_habilitado: bool = multi_tour_habilitado

    def refrescar_servicios(
        self,
        servicios: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]],
    ) -> None:
        """Rebuild _servicios, _familias, and _horarios in place from a fresh repo snapshot.

        Safe on the shared singleton instance: per-conversation state lives in
        PTB user_data (ContextoVenta), not here. Any in-flight sale reads the
        catalog fresh on its next FSM transition and will see the updated data.
        """
        nuevos_servicios, nuevas_familias, nuevos_horarios = self._build_catalog(servicios)
        self._servicios.clear()
        self._servicios.update(nuevos_servicios)
        self._familias.clear()
        self._familias.update(nuevas_familias)
        self._horarios.clear()
        self._horarios.update(nuevos_horarios)

    def iniciar(self) -> SalidaFSM:
        return SalidaFSM(
            nuevo_estado=EstadoFSM.METODO_INPUT,
            mensaje=obtener_mensaje("pregunta_metodo_input"),
            opciones=["Manual", "Foto"],
            contexto=ContextoVenta(),
        )

    def iniciar_otro_tour(self, contexto: ContextoVenta) -> SalidaFSM:
        """Reset per-tour fields and route to FAMILIA for a subsequent tour.

        Preserves: client identity, hotel, modalidad/punto/canal/tipo.
        Clears: all per-tour fields including participants and numero_fisico.
        Sets: tour_adicional=True, modo_edicion=False.
        """
        ctx = _clonar(contexto)
        # Clear per-tour fields
        ctx.destinos_numeros = []
        ctx.destinos_nombres = []
        ctx.familia_seleccionada = None
        ctx.fechas_por_servicio = {}
        ctx.fecha_salida = None
        ctx.adultos = None
        ctx.ninos = None
        ctx.valor = None
        ctx.abono = None
        ctx.neto = None
        ctx.numero_fisico = None
        ctx.vendedor_nombre = None
        ctx.vendedor_id = None
        ctx.cerrador_nombre = None
        ctx.cerrador_id = None
        ctx.referido_nombre = None
        ctx.rol_registrante = None
        # Set discriminator and navigation flags
        ctx.tour_adicional = True
        ctx.modo_edicion = False
        return self._salida_familia(ctx)

    def procesar(
        self,
        estado: EstadoFSM,
        entrada: str,
        contexto: ContextoVenta,
    ) -> SalidaFSM:
        handlers = {
            EstadoFSM.METODO_INPUT: self._handle_metodo_input,
            EstadoFSM.ESPERANDO_FOTO: self._handle_esperando_foto,
            EstadoFSM.MODALIDAD_VENTA: self._handle_modalidad_venta,
            EstadoFSM.TIPO_RESERVA: self._handle_tipo_reserva,
            EstadoFSM.CANAL_ORIGEN: self._handle_canal_origen,
            EstadoFSM.PUNTO_DE_VENTA: self._handle_punto_de_venta,
            EstadoFSM.FAMILIA: self._handle_familia,
            EstadoFSM.SERVICIO_EN_FAMILIA: self._handle_servicio_en_familia,
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

    def _familias_ordenadas(self) -> list[str]:
        """Return family (categoria) names in the picker's deterministic order."""
        return list(self._familias.keys())

    def _opciones_familia(self) -> list[tuple[str, str]]:
        """Structured options for the FAMILIA state: (categoria, 'fam:{indice}')."""
        return [
            (categoria, f"fam:{indice}")
            for indice, categoria in enumerate(self._familias_ordenadas())
        ]

    def _opciones_servicio_en_familia(self, categoria: str) -> list[tuple[str, str]]:
        """Structured options for tours within a family: ('{numero} — {nombre}', 'srv:{numero}')."""
        opciones: list[tuple[str, str]] = []
        for numero in self._familias.get(categoria, []):
            info = self._servicios.get(numero)
            nombre = info[0] if info is not None else str(numero)
            opciones.append((f"{numero} — {nombre}", f"srv:{numero}"))
        return opciones

    def _opciones_freelancers(self, solo_activos: bool) -> list[tuple[str, str]]:
        """Structured options for the freelancer picker: (label, 'fl:{id}').

        When solo_activos=True, only active freelancers are included.
        When solo_activos=False (edit flows), all freelancers are included;
        inactive entries get an '[inactivo]' suffix on their label.
        """
        opciones: list[tuple[str, str]] = []
        for fl_id, nombre, activo in self._freelancers:
            if solo_activos and not activo:
                continue
            label = nombre if activo else f"{nombre} [inactivo]"
            opciones.append((label, f"fl:{fl_id}"))
        return opciones

    def _acumulador_mensaje(self, ctx: ContextoVenta) -> str:
        """Message for the DESTINO accumulator: list selected tours by name."""
        num_map = {n: info[0] for n, info in self._servicios.items()}
        nombres = [num_map.get(n, str(n)) for n in ctx.destinos_numeros]
        return obtener_mensaje("info_destinos_acumulados").format(
            seleccionados=", ".join(nombres) if nombres else "—"
        )

    # DORMANT: multi-tour-en-una-venta — reserva-por-tour (owner 2026-08-11).
    # Reactivable con multi_tour_habilitado=True.
    def _opciones_acumulador(
        self, ctx: ContextoVenta
    ) -> list[tuple[str, str]]:
        """Structured options for the DESTINO accumulator.

        Each currently-selected tour gets a removable button with encoded
        callback_data 'del:{numero}' (~11 bytes, well under Telegram's 64-byte
        limit). 'Otro tour' and 'Confirmar' keep label == callback_data so the
        DESTINO handler can still match them by their message text.
        """
        opciones: list[tuple[str, str]] = []
        for numero in ctx.destinos_numeros:
            info = self._servicios.get(numero)
            nombre = info[0] if info is not None else str(numero)
            etiqueta = obtener_mensaje("opcion_quitar_tour").format(nombre=nombre)
            opciones.append((etiqueta, f"del:{numero}"))
        otro = obtener_mensaje("opcion_otro_tour")
        confirmar = obtener_mensaje("opcion_confirmar_destinos")
        opciones.append((otro, otro))
        opciones.append((confirmar, confirmar))
        return opciones

    # DORMANT: multi-tour-en-una-venta — reserva-por-tour (owner 2026-08-11).
    # Reactivable con multi_tour_habilitado=True.
    def _salida_acumulador(self, ctx: ContextoVenta) -> SalidaFSM:
        return SalidaFSM(
            nuevo_estado=EstadoFSM.DESTINO,
            mensaje=self._acumulador_mensaje(ctx),
            opciones_estructuradas=self._opciones_acumulador(ctx),
            contexto=ctx,
        )

    def _salida_familia(self, ctx: ContextoVenta) -> SalidaFSM:
        return SalidaFSM(
            nuevo_estado=EstadoFSM.FAMILIA,
            mensaje=obtener_mensaje("pregunta_familia"),
            opciones_estructuradas=self._opciones_familia(),
            contexto=ctx,
        )

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

    def _tours_sin_precio(self, ctx: ContextoVenta) -> list[str]:
        """Names of selected tours that have no neto_adulto in the catalog."""
        nombres = []
        for numero in ctx.destinos_numeros:
            info = self._servicios.get(numero)
            if info is not None and info[1] is None:
                nombres.append(info[0])
        return nombres

    # ── private handlers ────────────────────────────────────────────────────

    def _handle_metodo_input(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        opcion = entrada.strip()
        if opcion == "Manual":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MODALIDAD_VENTA,
                mensaje=obtener_mensaje("pregunta_modalidad_venta"),
                opciones=["Presencial", "Digital"],
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

    def _handle_modalidad_venta(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        """New state: asks Presencial vs Digital before asking for the punto."""
        ctx = _clonar(contexto)
        opcion = entrada.strip()
        if opcion == "Digital":
            ctx.tipo_cliente = TipoCliente.DIGITAL
            if ctx.modo_edicion:
                ctx.punto_de_venta_nombre = None  # digital has no punto
                ctx.tipo_cliente = TipoCliente.DIGITAL
                ctx.modo_edicion = False
                if not ctx.canal_origen:
                    return SalidaFSM(
                        nuevo_estado=EstadoFSM.CANAL_ORIGEN,
                        mensaje=obtener_mensaje("pregunta_canal_origen"),
                        opciones=[c.value for c in CanalOrigen],
                        contexto=ctx,
                    )
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=self._construir_resumen(ctx),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CANAL_ORIGEN,
                mensaje=obtener_mensaje("pregunta_canal_origen"),
                opciones=[c.value for c in CanalOrigen],
                contexto=ctx,
            )
        if opcion == "Presencial":
            if ctx.modo_edicion:
                ctx.canal_origen = None  # presencial has no canal
                ctx.tipo_cliente = None  # will be determined at TIPO_RESERVA or Crespo branch
                # If no punto set yet, ask for it (keep modo_edicion=True so
                # _handle_punto_de_venta routes back to CONFIRMACION afterwards).
                if not ctx.punto_de_venta_nombre:
                    return SalidaFSM(
                        nuevo_estado=EstadoFSM.PUNTO_DE_VENTA,
                        mensaje=obtener_mensaje("pregunta_punto_de_venta"),
                        opciones=list(self._puntos_venta),
                        contexto=ctx,
                    )
                # Punto already set — apply Crespo sentinel or re-ask TIPO_RESERVA.
                if ctx.punto_de_venta_nombre == "Crespo":
                    ctx.tipo_cliente = TipoCliente.EXTERNO
                    ctx.modo_edicion = False
                    return SalidaFSM(
                        nuevo_estado=EstadoFSM.CONFIRMACION,
                        mensaje=self._construir_resumen(ctx),
                        opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                        contexto=ctx,
                    )
                # Non-Crespo presencial with existing punto: re-ask TIPO_RESERVA.
                # Keep modo_edicion=True so the handler returns to CONFIRMACION.
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.TIPO_RESERVA,
                    mensaje=obtener_mensaje("pregunta_tipo_reserva"),
                    opciones=["INTERNO", "EXTERNO"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PUNTO_DE_VENTA,
                mensaje=obtener_mensaje("pregunta_punto_de_venta"),
                opciones=list(self._puntos_venta),
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MODALIDAD_VENTA,
            mensaje=obtener_mensaje("error_modalidad_invalida"),
            opciones=["Presencial", "Digital"],
            contexto=ctx,
        )

    def _handle_tipo_reserva(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        # TIPO_RESERVA now only appears for presencial non-Crespo sales.
        # DIGITAL is decided at MODALIDAD_VENTA; Crespo is decided at PUNTO_DE_VENTA.
        tipo_map = {
            "INTERNO": TipoCliente.INTERNO,
            "EXTERNO": TipoCliente.EXTERNO,
        }
        tipo = tipo_map.get(entrada.strip().upper())
        if tipo is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.TIPO_RESERVA,
                mensaje=obtener_mensaje("error_tipo_reserva_invalido"),
                opciones=["INTERNO", "EXTERNO"],
                contexto=_clonar(contexto),
            )
        ctx = _clonar(contexto)
        ctx.tipo_cliente = tipo
        if ctx.modo_edicion:
            ctx.canal_origen = None  # presencial options have no canal
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        if ctx.foto_modo:
            # Photo presencial non-Crespo: consume foto_modo and jump to PARTICIPANTE_ROL
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
        # Non-edit, non-foto: punto was already chosen at PUNTO_DE_VENTA, go to FAMILIA
        return self._salida_familia(ctx)

    def _handle_canal_origen(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        valores_validos = {c.value for c in CanalOrigen}
        seleccion = entrada.strip()
        if seleccion not in valores_validos:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CANAL_ORIGEN,
                mensaje=obtener_mensaje("error_canal_invalido"),
                opciones=[c.value for c in CanalOrigen],
                contexto=ctx,
            )
        ctx.canal_origen = seleccion
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
        return self._salida_familia(ctx)

    def _handle_punto_de_venta(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        ctx.punto_de_venta_nombre = entrada.strip()
        if ctx.destinos_nombres:
            nombres_norm = {n.lower().strip() for n in ctx.destinos_nombres}
            for numero, (nombre, _, _) in self._servicios.items():
                if nombre.lower().strip() in nombres_norm and numero not in ctx.destinos_numeros:
                    ctx.destinos_numeros.append(numero)
        if ctx.modo_edicion:
            # Determine what the nuevo punto is (already set on ctx above).
            nuevo_punto = ctx.punto_de_venta_nombre
            viejo_punto = contexto.punto_de_venta_nombre  # pre-edit value
            if nuevo_punto == "Crespo":
                # New punto is Crespo → sentinel EXTERNO, go to CONFIRMACION.
                ctx.tipo_cliente = TipoCliente.EXTERNO
                ctx.modo_edicion = False
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.CONFIRMACION,
                    mensaje=self._construir_resumen(ctx),
                    opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                    contexto=ctx,
                )
            if viejo_punto == "Crespo" or ctx.tipo_cliente is None:
                # Was Crespo→non-Crespo, or tipo is unresolved (e.g. Digital→Presencial
                # edit path cleared tipo): must ask TIPO_RESERVA.
                # Keep modo_edicion=True so _handle_tipo_reserva returns to CONFIRMACION.
                ctx.tipo_cliente = None
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.TIPO_RESERVA,
                    mensaje=obtener_mensaje("pregunta_tipo_reserva"),
                    opciones=["INTERNO", "EXTERNO"],
                    contexto=ctx,
                )
            # Non-Crespo → non-Crespo edit with existing tipo: keep it, return to CONFIRMACION.
            ctx.modo_edicion = False
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )
        # Crespo: skip TIPO_RESERVA, set sentinel EXTERNO.
        # In foto mode, jump to PARTICIPANTE_ROL; otherwise go to FAMILIA.
        if ctx.punto_de_venta_nombre == "Crespo":
            ctx.tipo_cliente = TipoCliente.EXTERNO
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
            return self._salida_familia(ctx)
        # Non-Crespo presencial: in foto mode keep foto_modo=True so TIPO_RESERVA
        # handler will consume it and jump to PARTICIPANTE_ROL.
        # In normal mode ask TIPO_RESERVA (INTERNO or EXTERNO only).
        return SalidaFSM(
            nuevo_estado=EstadoFSM.TIPO_RESERVA,
            mensaje=obtener_mensaje("pregunta_tipo_reserva"),
            opciones=["INTERNO", "EXTERNO"],
            contexto=ctx,
        )

    def _handle_familia(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        familias = self._familias_ordenadas()
        indice: int | None = None
        if entrada.strip().startswith("fam:"):
            try:
                indice = int(entrada.strip().removeprefix("fam:"))
            except ValueError:
                indice = None
        if indice is None or indice < 0 or indice >= len(familias):
            return self._salida_familia(ctx)
        ctx.familia_seleccionada = familias[indice]
        return SalidaFSM(
            nuevo_estado=EstadoFSM.SERVICIO_EN_FAMILIA,
            mensaje=obtener_mensaje("pregunta_servicio_en_familia"),
            opciones_estructuradas=self._opciones_servicio_en_familia(ctx.familia_seleccionada),
            contexto=ctx,
        )

    def _handle_servicio_en_familia(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        # Defensive: stale state (e.g. bot restart mid-flow) can leave the family
        # unset. Route back to FAMILIA so the user can re-pick instead of showing
        # an empty grid with no escape.
        if not ctx.familia_seleccionada:
            return self._salida_familia(ctx)
        categoria = ctx.familia_seleccionada
        numeros_familia = set(self._familias.get(categoria, []))
        numero: int | None = None
        if entrada.strip().startswith("srv:"):
            try:
                numero = int(entrada.strip().removeprefix("srv:"))
            except ValueError:
                numero = None
        if numero is None or numero not in numeros_familia:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.SERVICIO_EN_FAMILIA,
                mensaje=obtener_mensaje("pregunta_servicio_en_familia"),
                opciones_estructuradas=self._opciones_servicio_en_familia(categoria),
                contexto=ctx,
            )
        if numero not in ctx.destinos_numeros:
            ctx.destinos_numeros.append(numero)
            nombre_tour = self._servicios[numero][0] if numero in self._servicios else str(numero)
            ctx.destinos_nombres.append(nombre_tour)

        # DORMANT: multi-tour-en-una-venta — reserva-por-tour (owner 2026-08-11).
        # Reactivable con multi_tour_habilitado=True.
        if self._multi_tour_habilitado:
            return self._salida_acumulador(ctx)

        # One-tour mode (default): skip the accumulator entirely.
        if ctx.modo_edicion:
            # User is editing "Destinos" from CONFIRMACION — single-tour edit.
            # Mirror the logic from _handle_destino's confirm-in-edit branch:
            # prune stale per-tour dates, recompute neto, handle missing date.
            had_per_tour_dates = bool(ctx.fechas_por_servicio)
            ctx.fechas_por_servicio = {
                n: f for n, f in ctx.fechas_por_servicio.items() if n in ctx.destinos_numeros
            }
            computed = self._calcular_neto(ctx)
            if computed is not None:
                ctx.neto = computed
            if had_per_tour_dates and _siguiente_tour_sin_fecha(ctx) is not None:
                # The new tour still needs a date — enter capture loop.
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.FECHA_SALIDA,
                    mensaje=self._mensaje_entrada_fecha_salida(ctx),
                    contexto=ctx,
                )
            ctx.modo_edicion = False
            if ctx.fechas_por_servicio:
                ctx.fecha_salida = min(ctx.fechas_por_servicio.values())
            return SalidaFSM(
                nuevo_estado=EstadoFSM.CONFIRMACION,
                mensaje=self._construir_resumen(ctx),
                opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
                contexto=ctx,
            )

        # Subsequent tour: client already captured — skip straight to date capture.
        if ctx.tour_adicional:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje=self._mensaje_entrada_fecha_salida(ctx),
                contexto=ctx,
            )
        # Normal registration: route straight to CLIENTE_NOMBRE (one tour confirmed).
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CLIENTE_NOMBRE,
            mensaje=obtener_mensaje("pregunta_cliente_nombre"),
            contexto=ctx,
        )

    def _handle_destino(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        """DESTINO is the accumulator: add, remove, or confirm the selection."""
        ctx = _clonar(contexto)
        texto = entrada.strip()

        # DORMANT: multi-tour-en-una-venta — reserva-por-tour (owner 2026-08-11).
        # Reactivable con multi_tour_habilitado=True.
        if texto == obtener_mensaje("opcion_otro_tour"):
            return self._salida_familia(ctx)

        # Per-tour deselection: 'del:{numero}' removes that tour and re-shows the
        # accumulator. If it empties the selection, route back to FAMILIA (FIX 1).
        if texto.startswith("del:"):
            try:
                numero = int(texto.removeprefix("del:"))
            except ValueError:
                numero = None
            if numero is not None and numero in ctx.destinos_numeros:
                idx = ctx.destinos_numeros.index(numero)
                ctx.destinos_numeros.remove(numero)
                if idx < len(ctx.destinos_nombres):
                    ctx.destinos_nombres.pop(idx)
            if not ctx.destinos_numeros:
                return self._salida_familia(ctx)
            return self._salida_acumulador(ctx)

        if texto == obtener_mensaje("opcion_confirmar_destinos"):
            # Defense-in-depth: a venta must never be registered with zero tours.
            if not ctx.destinos_numeros:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.FAMILIA,
                    mensaje=obtener_mensaje("error_sin_destinos"),
                    opciones_estructuradas=self._opciones_familia(),
                    contexto=ctx,
                )
            if ctx.modo_edicion:
                # 1. Prune dates for tours no longer in the selection.
                #    Remember whether per-tour dates were in use BEFORE pruning.
                had_per_tour_dates = bool(ctx.fechas_por_servicio)
                ctx.fechas_por_servicio = {
                    n: f
                    for n, f in ctx.fechas_por_servicio.items()
                    if n in ctx.destinos_numeros
                }
                # 2. Recompute neto with the new tour set (must happen before routing
                #    because the FECHA_SALIDA completion path does not recompute it).
                computed = self._calcular_neto(ctx)
                if computed is not None:
                    ctx.neto = computed
                # 3. If this sale was using per-tour dates and any selected tour still
                #    lacks a date, enter the capture loop (keeping modo_edicion=True so
                #    the loop returns here after completion).
                if had_per_tour_dates and _siguiente_tour_sin_fecha(ctx) is not None:
                    return SalidaFSM(
                        nuevo_estado=EstadoFSM.FECHA_SALIDA,
                        mensaje=self._mensaje_entrada_fecha_salida(ctx),
                        contexto=ctx,
                    )
                # 4. All selected tours already have dates (or no per-tour dates were
                #    in use) — recompute min and return to CONFIRMACION.
                ctx.modo_edicion = False
                if ctx.fechas_por_servicio:
                    ctx.fecha_salida = min(ctx.fechas_por_servicio.values())
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

        # Any other input: re-render the accumulator (buttons only).
        return self._salida_acumulador(ctx)

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
                mensaje=self._mensaje_entrada_fecha_salida(ctx),
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
            mensaje=self._mensaje_entrada_fecha_salida(ctx),
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

        # Determine which tour we are currently answering — the first one without a date.
        tour_actual = _siguiente_tour_sin_fecha(ctx)
        if tour_actual is not None:
            ctx.fechas_por_servicio[tour_actual] = fecha
        else:
            # No pending tour (e.g. bare ctx with no destinos_numeros) — legacy path.
            ctx.fecha_salida = fecha

        # Check if all tours now have a date.
        siguiente = _siguiente_tour_sin_fecha(ctx)
        if siguiente is not None:
            # More tours need dates — stay in FECHA_SALIDA and ask for the next one.
            if siguiente in self._servicios:
                nombre = self._servicios[siguiente][0]
            else:
                nombre = str(siguiente)
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje=obtener_mensaje("pregunta_fecha_salida_tour").format(tour=nombre),
                contexto=ctx,
            )

        # All tours have dates — compute primary date and advance.
        if ctx.fechas_por_servicio:
            ctx.fecha_salida = min(ctx.fechas_por_servicio.values())

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
        if ctx.valor is not None and ctx.abono > ctx.valor:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.MONTO_ABONO,
                mensaje=obtener_mensaje("error_abono_supera_valor").format(
                    abono=_formatear_monto(monto),
                    valor=_formatear_monto(ctx.valor),
                ),
                contexto=ctx,
            )
        neto = self._calcular_neto(ctx)
        if neto is not None:
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
        sin_precio = self._tours_sin_precio(ctx)
        tours_str = ", ".join(sin_precio) if sin_precio else "algún tour seleccionado"
        return SalidaFSM(
            nuevo_estado=EstadoFSM.MONTO_NETO,
            mensaje=obtener_mensaje("pregunta_neto_sin_precio").format(tours=tours_str),
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
            opciones_fl = self._opciones_freelancers(solo_activos=True)
            if not opciones_fl:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
                    mensaje=obtener_mensaje("tiquetera.sin_freelancers_activos"),
                    opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje=obtener_mensaje("pregunta_participante_otro_cerrador"),
                opciones_estructuradas=opciones_fl,
                contexto=ctx,
            )
        if opcion == "Solo cerrador":
            ctx.rol_registrante = "cerrador"
            opciones_fl = self._opciones_freelancers(solo_activos=True)
            if not opciones_fl:
                return SalidaFSM(
                    nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
                    mensaje=obtener_mensaje("tiquetera.sin_freelancers_activos"),
                    opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
                    contexto=ctx,
                )
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje=obtener_mensaje("pregunta_participante_otro_vendedor"),
                opciones_estructuradas=opciones_fl,
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje=obtener_mensaje("error_rol_invalido"),
            opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
            contexto=ctx,
        )

    def _parse_fl_id(self, entrada: str) -> uuid.UUID | None:
        """Parse a 'fl:{uuid}' callback value; return None on bad format or missing prefix."""
        stripped = entrada.removeprefix("fl:")
        if stripped == entrada:
            # No prefix was removed — free text, not a picker selection.
            return None
        try:
            return uuid.UUID(stripped)
        except ValueError:
            return None

    def _lookup_fl_nombre(self, fl_id: uuid.UUID) -> str | None:
        """Return the nombre of the freelancer with the given id, or None if not found."""
        for rid, nombre, _ in self._freelancers:
            if rid == fl_id:
                return nombre
        return None

    def _handle_participante_otro(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)

        fl_id = self._parse_fl_id(entrada.strip())
        if fl_id is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje=obtener_mensaje("error_seleccion_freelancer_invalida"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=True),
                contexto=ctx,
            )

        nombre = self._lookup_fl_nombre(fl_id)
        if nombre is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.PARTICIPANTE_OTRO,
                mensaje=obtener_mensaje("error_seleccion_freelancer_invalida"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=True),
                contexto=ctx,
            )

        if ctx.rol_registrante == "vendedor":
            ctx.cerrador_id = fl_id
            ctx.cerrador_nombre = nombre
        elif ctx.rol_registrante == "cerrador":
            ctx.vendedor_id = fl_id
            ctx.vendedor_nombre = nombre
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
        if not ctx.punto_de_venta_nombre and ctx.tipo_cliente != TipoCliente.DIGITAL:
            faltantes.append("Punto de venta")
        if not ctx.rol_registrante:
            faltantes.append("Participantes (vendedor/cerrador)")
        if ctx.tipo_cliente == TipoCliente.DIGITAL and not ctx.canal_origen:
            faltantes.append("Canal de origen")
        return faltantes

    def _opciones_editables(self, ctx: ContextoVenta) -> list[str]:
        """Return the list of editable field labels filtered by client type and punto."""
        es_crespo = ctx.punto_de_venta_nombre == "Crespo"
        return [
            label
            for label, est in _CAMPOS_EDITABLES
            if (est != EstadoFSM.CANAL_ORIGEN or ctx.tipo_cliente == TipoCliente.DIGITAL)
            and (est != EstadoFSM.PUNTO_DE_VENTA or ctx.tipo_cliente != TipoCliente.DIGITAL)
            # Hide "Tipo reserva" for Crespo (type is fixed as sentinel EXTERNO)
            and (est != EstadoFSM.TIPO_RESERVA or not es_crespo)
            # Hide "Modalidad" for Digital (modalidad is already decided)
            and (est != EstadoFSM.MODALIDAD_VENTA or ctx.tipo_cliente != TipoCliente.DIGITAL)
        ]

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
            opciones_editar = self._opciones_editables(ctx)
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("pregunta_campo_editar"),
                opciones=opciones_editar,
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CANCELADO,
            mensaje=obtener_mensaje("venta_cancelada"),
            contexto=ctx,
        )

    def _handle_editar_selector(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)
        label_elegido = entrada.strip()
        if label_elegido == "Canal de origen" and ctx.tipo_cliente != TipoCliente.DIGITAL:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("error_campo_editar_invalido"),
                opciones=self._opciones_editables(ctx),
                contexto=ctx,
            )
        if label_elegido == "Punto de venta" and ctx.tipo_cliente == TipoCliente.DIGITAL:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("error_campo_editar_invalido"),
                opciones=self._opciones_editables(ctx),
                contexto=ctx,
            )
        # Bounce "Tipo reserva" edit for Crespo (type is fixed as sentinel EXTERNO)
        if label_elegido == "Tipo reserva" and ctx.punto_de_venta_nombre == "Crespo":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("error_campo_editar_invalido"),
                opciones=self._opciones_editables(ctx),
                contexto=ctx,
            )
        campo_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        estado_destino = campo_map.get(label_elegido)
        if estado_destino is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_SELECTOR,
                mensaje=obtener_mensaje("error_campo_editar_invalido"),
                opciones=self._opciones_editables(ctx),
                contexto=ctx,
            )
        ctx.modo_edicion = True
        if estado_destino == EstadoFSM.FAMILIA:
            # Editing destinations: re-pick from scratch.
            ctx.destinos_numeros = []
            ctx.familia_seleccionada = None
            return self._salida_familia(ctx)
        if estado_destino == EstadoFSM.FECHA_SALIDA:
            # Editing date: clear per-tour dates so the loop re-runs from scratch.
            ctx.fechas_por_servicio = {}
            # For single-tour, show the edit prompt with the current date so the user
            # can see what they are replacing.  For multi-tour, use the per-tour prompt.
            if len(ctx.destinos_numeros) <= 1:
                fecha_actual = (
                    ctx.fecha_salida.strftime("%d/%m/%Y %H:%M") if ctx.fecha_salida else "—"
                )
                msg = obtener_mensaje("pregunta_editar_fecha_salida").format(
                    actual=fecha_actual
                )
            else:
                msg = self._mensaje_entrada_fecha_salida(ctx)
            return SalidaFSM(
                nuevo_estado=EstadoFSM.FECHA_SALIDA,
                mensaje=msg,
                contexto=ctx,
            )
        if estado_destino in (EstadoFSM.EDITAR_VENDEDOR, EstadoFSM.EDITAR_CERRADOR):
            # Participant edit: show the freelancer picker (includes inactive)
            return SalidaFSM(
                nuevo_estado=estado_destino,
                mensaje=self._mensaje_para_estado(estado_destino, ctx),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
                contexto=ctx,
            )
        return SalidaFSM(
            nuevo_estado=estado_destino,
            mensaje=self._mensaje_para_estado(estado_destino, ctx),
            opciones=self._opciones_para_estado(estado_destino, ctx),
            contexto=ctx,
        )

    def _handle_editar_vendedor(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
        ctx = _clonar(contexto)

        fl_id = self._parse_fl_id(entrada.strip())
        if fl_id is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_VENDEDOR,
                mensaje=obtener_mensaje("error_seleccion_freelancer_invalida"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
                contexto=ctx,
            )
        nombre = self._lookup_fl_nombre(fl_id)
        if nombre is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_VENDEDOR,
                mensaje=obtener_mensaje("error_seleccion_freelancer_invalida"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
                contexto=ctx,
            )

        if ctx.rol_registrante not in ("ambos", "vendedor", "cerrador"):
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_VENDEDOR,
                mensaje=obtener_mensaje("error_interno_rol_no_definido"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
                contexto=ctx,
            )

        ctx.vendedor_id = fl_id
        ctx.vendedor_nombre = nombre

        if ctx.rol_registrante == "ambos":
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_CERRADOR,
                mensaje=obtener_mensaje("pregunta_editar_cerrador").format(
                    actual=ctx.cerrador_nombre or "—"
                ),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
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

        fl_id = self._parse_fl_id(entrada.strip())
        if fl_id is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_CERRADOR,
                mensaje=obtener_mensaje("error_seleccion_freelancer_invalida"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
                contexto=ctx,
            )
        nombre = self._lookup_fl_nombre(fl_id)
        if nombre is None:
            return SalidaFSM(
                nuevo_estado=EstadoFSM.EDITAR_CERRADOR,
                mensaje=obtener_mensaje("error_seleccion_freelancer_invalida"),
                opciones_estructuradas=self._opciones_freelancers(solo_activos=False),
                contexto=ctx,
            )

        ctx.cerrador_id = fl_id
        ctx.cerrador_nombre = nombre
        ctx.modo_edicion = False
        return SalidaFSM(
            nuevo_estado=EstadoFSM.CONFIRMACION,
            mensaje=self._construir_resumen(ctx),
            opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"],
            contexto=ctx,
        )

    def _mensaje_entrada_fecha_salida(self, ctx: ContextoVenta) -> str:
        """Return the FECHA_SALIDA entry prompt appropriate for the current context.

        For a single-tour sale, returns the original catalog text verbatim to preserve
        byte-identical behavior.  For multi-tour sales, names the first undated tour.
        """
        if len(ctx.destinos_numeros) <= 1:
            return obtener_mensaje("pregunta_fecha_salida")
        siguiente = _siguiente_tour_sin_fecha(ctx)
        if siguiente is None:
            return obtener_mensaje("pregunta_fecha_salida")
        nombre = self._servicios[siguiente][0] if siguiente in self._servicios else str(siguiente)
        return obtener_mensaje("pregunta_fecha_salida_tour").format(tour=nombre)

    def _mensaje_para_estado(self, estado: EstadoFSM, ctx: ContextoVenta) -> str:
        msgs: dict[EstadoFSM, str] = {
            EstadoFSM.MODALIDAD_VENTA: obtener_mensaje("pregunta_modalidad_venta"),
            EstadoFSM.TIPO_RESERVA: obtener_mensaje("pregunta_tipo_reserva"),
            EstadoFSM.CANAL_ORIGEN: obtener_mensaje("pregunta_editar_canal").format(
                actual=ctx.canal_origen or "—"
            ),
            EstadoFSM.PUNTO_DE_VENTA: obtener_mensaje("pregunta_punto_de_venta"),
            EstadoFSM.DESTINO: self._acumulador_mensaje(ctx),
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
            EstadoFSM.MODALIDAD_VENTA: ["Presencial", "Digital"],
            EstadoFSM.TIPO_RESERVA: ["INTERNO", "EXTERNO"],
            EstadoFSM.CANAL_ORIGEN: [c.value for c in CanalOrigen],
            EstadoFSM.PUNTO_DE_VENTA: list(self._puntos_venta),
            EstadoFSM.CLIENTE_TIPO_ID: ["CC", "NIT"],
            EstadoFSM.PARTICIPANTE_ROL: ["Ambos", "Solo vendedor", "Solo cerrador"],
        }
        return opts.get(estado, [])

    def _get_valor_prefilled(self, estado: EstadoFSM, ctx: ContextoVenta) -> str | None:
        if estado == EstadoFSM.PUNTO_DE_VENTA:
            return ctx.punto_de_venta_nombre
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
            # Stop auto-advance when we are mid-loop (fechas_por_servicio has been partially
            # populated but some tours still need a date).  Fall through to the legacy path
            # when fechas_por_servicio is empty (photo extraction pre-set fecha_salida only).
            if ctx.fechas_por_servicio and _siguiente_tour_sin_fecha(ctx) is not None:
                return None
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
        if (
            len(ctx.destinos_numeros) > 1
            and ctx.fecha_salida is not None
            and ctx.fechas_por_servicio
        ):
            pares = [
                (
                    self._servicios[n][0] if n in self._servicios else str(n),
                    ctx.fechas_por_servicio.get(n, ctx.fecha_salida),
                )
                for n in ctx.destinos_numeros
            ]
            fecha_str = formatear_fechas_compactas(pares)
        else:
            fecha_str = ctx.fecha_salida.strftime("%d/%m/%Y") if ctx.fecha_salida else "—"
        hotel_str = "Sin hotel" if ctx.sin_hotel else (ctx.cliente_hotel or "—")
        hab_str = "—" if ctx.sin_hotel else (ctx.cliente_habitacion or "—")
        vendedor_str = ctx.vendedor_nombre or _tú_si(ctx.rol_registrante, "ambos", "vendedor")
        cerrador_str = ctx.cerrador_nombre or _tú_si(ctx.rol_registrante, "ambos", "cerrador")
        if ctx.valor is None:
            saldo_pendiente = None
        elif ctx.abono is None:
            saldo_pendiente = ctx.valor
        else:
            saldo_pendiente = ctx.valor - ctx.abono
        return obtener_mensaje("confirmacion_resumen").format(
            tipo=ctx.tipo_cliente or "—",
            canal=ctx.canal_origen or "—",
            punto_de_venta=ctx.punto_de_venta_nombre or "—",
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
            saldo_pendiente=_formatear_monto(saldo_pendiente),
            neto=_formatear_monto(ctx.neto),
            vendedor=vendedor_str,
            cerrador=cerrador_str,
        )
