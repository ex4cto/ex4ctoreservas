"""RegenerarFacturaService — regenerates and resends a client invoice after a date edit.

Called after a successful fecha edit so the client receives an updated invoice
without the agent having to trigger a full registration flow again.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from enum import StrEnum

from garay.aplicacion.factura.servicio import GenerarFacturaService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.facturas.tipos import EstadoEnvioFactura
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    FacturaRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import NotificadorEmail
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.contexto import ContextoVenta
from garay.dominio.ventas.entidades import Venta
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)


class ResultadoRegenerarFactura(StrEnum):
    """Outcome of a regenerate-and-resend attempt."""

    SIN_VENTA = "SIN_VENTA"
    SIN_FACTURA = "SIN_FACTURA"
    REENVIADA = "REENVIADA"
    ERROR_ENVIO = "ERROR_ENVIO"


def reconstruir_contexto(
    venta: Venta,
    cliente: Cliente,
    servicios: ServicioRepository,
) -> ContextoVenta:
    """Reconstruct a ContextoVenta from persisted domain entities.

    The ``sin_hotel`` flag is not recoverable from stored data; it is set to
    ``False`` (accepted limitation — the hotel name or "—" will render normally).
    """
    ctx = ContextoVenta()

    # Client fields
    ctx.cliente_nombre = cliente.nombre
    ctx.cliente_email = cliente.email
    ctx.cliente_telefono = cliente.telefono
    ctx.cliente_hotel = cliente.hotel
    ctx.cliente_habitacion = cliente.numero_habitacion
    ctx.cliente_identificacion = cliente.identificacion
    ctx.cliente_tipo_identificacion = cliente.tipo_identificacion
    ctx.sin_hotel = False  # not recoverable; accepted limitation

    # Venta financials
    ctx.valor = venta.valor_venta.monto
    ctx.abono = venta.abono.monto if venta.abono is not None else None
    ctx.adultos = venta.adultos
    ctx.ninos = venta.ninos

    # Invoice language — carried so a reenvío keeps the client's original choice.
    ctx.factura_idioma = venta.factura_idioma

    # Resolve servicios; build destinos lists in venta.servicio_ids order
    servicio_objects: dict[uuid.UUID, Servicio | None] = {}
    for sid in venta.servicio_ids:
        s = servicios.buscar_por_id(sid)
        servicio_objects[sid] = s

    ctx.destinos_numeros = []
    ctx.destinos_nombres = []
    for sid in venta.servicio_ids:
        s = servicio_objects.get(sid)
        if s is not None:
            ctx.destinos_numeros.append(s.numero)
            ctx.destinos_nombres.append(s.nombre)
        else:
            ctx.destinos_numeros.append(0)
            ctx.destinos_nombres.append("?")

    # Map fechas_por_servicio from {uuid: dt} to {servicio.numero: dt}
    if venta.fechas_por_servicio:
        int_key_fechas: dict[int, datetime.datetime] = {}
        for sid, dt in venta.fechas_por_servicio.items():
            s = servicio_objects.get(sid)
            if s is not None:
                int_key_fechas[s.numero] = dt
            # If servicio is missing, skip (fallback handled by render)
        ctx.fechas_por_servicio = int_key_fechas
        ctx.fecha_salida = (
            min(int_key_fechas.values())
            if int_key_fechas
            else datetime.datetime.combine(venta.fecha, datetime.time.min)
        )
    else:
        ctx.fechas_por_servicio = {}
        ctx.fecha_salida = datetime.datetime.combine(venta.fecha, datetime.time.min)

    # Map horarios_por_servicio from {uuid: str} to {servicio.numero: str}
    # Reads the snapshot — never queries the live catalogue.
    if venta.horarios_por_servicio:
        int_key_horarios: dict[int, str] = {}
        for sid, h in venta.horarios_por_servicio.items():
            s = servicio_objects.get(sid)
            if s is not None:
                int_key_horarios[s.numero] = h
        ctx.horarios_por_servicio = int_key_horarios
    else:
        ctx.horarios_por_servicio = {}

    return ctx


class RegenerarFacturaService:
    """Regenerates an existing invoice's HTML and resends it to the client.

    Used when a venta's fecha is edited via /gestionar_ventas.  The edit has
    already been committed; this service updates and resends the document without
    touching the venta or auditoria.
    """

    def __init__(
        self,
        ventas: VentaRepository,
        clientes: ClienteRepository,
        servicios: ServicioRepository,
        facturas: FacturaRepository,
        generador: GenerarFacturaService,
        email: NotificadorEmail,
    ) -> None:
        self._ventas = ventas
        self._clientes = clientes
        self._servicios = servicios
        self._facturas = facturas
        self._generador = generador
        self._email = email

    def ejecutar(self, venta_id: uuid.UUID) -> ResultadoRegenerarFactura:
        """Regenerate and resend the invoice for *venta_id*.

        Steps:
          1. Load venta; return SIN_VENTA if missing.
          2. Load existing factura; return SIN_FACTURA if none (client had no email).
          3. Load cliente for reconstruction; return SIN_FACTURA defensively if None.
          4. Reconstruct ContextoVenta and regenerate HTML.
          5. Update factura fields (keep id/numero/fecha_emision).
          6. Persist PENDIENTE, then send email.
          7. Persist ENVIADO on success or ERROR on failure.
        """
        venta = self._ventas.buscar_por_id(venta_id)
        if venta is None:
            logger.warning("regenerar_factura: venta %s not found", venta_id)
            return ResultadoRegenerarFactura.SIN_VENTA

        factura = self._facturas.buscar_por_venta_id(venta_id)
        if factura is None:
            logger.info("regenerar_factura: no factura for venta %s — skipping", venta_id)
            return ResultadoRegenerarFactura.SIN_FACTURA

        cliente = self._clientes.buscar_por_id(venta.cliente_id)
        if cliente is None:
            logger.error(
                "regenerar_factura: cliente %s not found for venta %s — inconsistency",
                venta.cliente_id,
                venta_id,
            )
            return ResultadoRegenerarFactura.SIN_FACTURA

        ctx = reconstruir_contexto(venta, cliente, self._servicios)
        html = self._generador.generar(ctx, venta_id, numero=factura.numero)

        # Update the existing factura — keep legal identity (id, numero, fecha_emision)
        factura.html_contenido = html
        factura.monto_total = venta.valor_venta
        factura.abono = venta.abono
        factura.estado_envio = EstadoEnvioFactura.PENDIENTE
        self._facturas.guardar(factura)

        destinatario = factura.cliente_email or (cliente.email or "")
        if not destinatario:
            return ResultadoRegenerarFactura.SIN_FACTURA
        asunto = obtener_mensaje("factura.asunto_email")

        try:
            self._email.enviar(destinatario, asunto, html)
        except Exception:
            logger.exception("regenerar_factura: email send failed for venta %s", venta_id)
            factura.estado_envio = EstadoEnvioFactura.ERROR
            self._facturas.guardar(factura)
            return ResultadoRegenerarFactura.ERROR_ENVIO

        factura.estado_envio = EstadoEnvioFactura.ENVIADO
        self._facturas.guardar(factura)
        return ResultadoRegenerarFactura.REENVIADA
