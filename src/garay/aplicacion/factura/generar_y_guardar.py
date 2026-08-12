"""GenerarYGuardarFacturaService — genera, persiste y envia la factura.

Orden garantizado: se persiste PENDIENTE antes de intentar el envio, de modo que
un fallo de correo siempre deja un registro (ERROR) y un reintento nunca reenvia
una factura ya entregada (ENVIADO).
"""

from __future__ import annotations

import logging
import uuid

from garay.aplicacion.factura.servicio import (
    GenerarFacturaService,
    _hoy_bogota,
    _numero_factura,
)
from garay.aplicacion.tiquetera.comandos import ResultadoRegistrarVenta
from garay.dominio.comun.dinero import Dinero
from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura
from garay.dominio.puertos.repositorios import FacturaRepository
from garay.dominio.puertos.servicios_externos import NotificadorEmail
from garay.dominio.ventas.contexto import ContextoVenta
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)


class GenerarYGuardarFacturaService:
    def __init__(
        self,
        generador: GenerarFacturaService,
        facturas: FacturaRepository,
        notificador: NotificadorEmail | None,
    ) -> None:
        self._generador = generador
        self._facturas = facturas
        self._notificador = notificador

    def ejecutar(
        self, ctx: ContextoVenta, resultado: ResultadoRegistrarVenta
    ) -> Factura | None:
        # Sin correo o sin valor no hay nada que facturar.
        if not ctx.cliente_email:
            return None
        if ctx.valor is None:
            return None

        existente = self._facturas.buscar_por_venta_id(resultado.venta_id)
        if existente is not None and existente.estado_envio is EstadoEnvioFactura.ENVIADO:
            # Idempotente: nunca reenviamos una factura ya entregada.
            return existente

        if existente is not None:
            # Reintento: reenviamos el MISMO documento ya emitido. El numero, la
            # fecha y el html son la identidad legal de la factura y no deben
            # cambiar entre intentos de envio.
            factura = existente
            factura.estado_envio = EstadoEnvioFactura.PENDIENTE
        else:
            factura = Factura(
                id=uuid.uuid4(),
                numero=_numero_factura(resultado.venta_id),
                venta_id=resultado.venta_id,
                cliente_nombre=ctx.cliente_nombre,
                cliente_email=ctx.cliente_email,
                monto_total=Dinero(ctx.valor),
                abono=Dinero(ctx.abono) if ctx.abono is not None else None,
                fecha_emision=_hoy_bogota(),
                html_contenido=self._generador.generar(ctx, resultado.venta_id),
                estado_envio=EstadoEnvioFactura.PENDIENTE,
            )

        # Persistimos PENDIENTE primero: si el envio falla, queda el registro.
        self._facturas.guardar(factura)

        if self._notificador is None:
            factura.estado_envio = EstadoEnvioFactura.SIN_EMAIL
            self._facturas.guardar(factura)
            return factura

        asunto = obtener_mensaje("factura.asunto_email")
        try:
            self._notificador.enviar(ctx.cliente_email, asunto, factura.html_contenido)
        except Exception:
            logger.exception("Error al enviar factura por correo")
            factura.estado_envio = EstadoEnvioFactura.ERROR
        else:
            factura.estado_envio = EstadoEnvioFactura.ENVIADO

        self._facturas.guardar(factura)
        return factura
