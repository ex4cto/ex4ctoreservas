"""RegistrarVentaService — application service for registering a sale."""

from __future__ import annotations

import uuid

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando, ResultadoRegistrarVenta
from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.puertos.repositorios import (
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    TiqueteraRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.ventas.entidades import Venta


class RegistrarVentaService:
    """Orchestrates sale registration: creates the aggregate, calculates
    commissions, persists, optionally creates a tiquetera, and notifies."""

    def __init__(
        self,
        ventas: VentaRepository,
        reglas_repo: ReglasComisionRepository,
        tiqueteras: TiqueteraRepository,
        puntos_repo: PuntoDeVentaRepository,
        motor: MotorComisiones,
        notificador: NotificadorGrupo,
        grupo_id: str,
    ) -> None:
        self._ventas = ventas
        self._reglas_repo = reglas_repo
        self._tiqueteras = tiqueteras
        self._puntos_repo = puntos_repo
        self._motor = motor
        self._notificador = notificador
        self._grupo_id = grupo_id

    def ejecutar(self, cmd: RegistrarVentaComando) -> ResultadoRegistrarVenta:
        # 1. Create the Venta aggregate
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=cmd.valor_venta,
            neto=cmd.neto,
            servicio_id=cmd.servicio_id,
            cliente_id=cmd.cliente_id,
            tipo_cliente=cmd.tipo_cliente,
            fecha=cmd.fecha,
            participantes=cmd.participantes,
            cantidad=cmd.cantidad,
            abono=cmd.abono,
        )

        # 2. Fetch commission rules — raise if not found
        reglas = self._reglas_repo.buscar_por_tipo_cliente(cmd.tipo_cliente)
        if reglas is None:
            raise ReglasComisionNoEncontradas(
                f"No se encontraron reglas de comision para el tipo de cliente: {cmd.tipo_cliente}"
            )

        # 3. Resolve punto de venta if present
        punto = None
        if cmd.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(cmd.participantes.punto_de_venta_id)

        # 4. Calculate commission breakdown
        desglose = self._motor.calcular(venta, reglas, punto, cmd.porcentaje_referido)

        # 5. Persist the sale
        self._ventas.guardar(venta)

        # 6. Create tiquetera if a reference photo was provided
        if cmd.foto_referencia is not None:
            tiquetera = Tiquetera(
                id=uuid.uuid4(),
                venta_id=venta.id,
                foto_referencia=cmd.foto_referencia,
                procesada=False,
            )
            self._tiqueteras.guardar(tiquetera)

        # 7. Notify the group
        vendedor = cmd.participantes.vendedor_nombre or "—"
        cerrador = cmd.participantes.cerrador_nombre or "—"
        mensaje = (
            f"Nueva venta registrada [{venta.id}] | "
            f"Valor: {cmd.valor_venta} | "
            f"Ganancia agencia: {desglose.agencia} | "
            f"Vendedor: {vendedor} | "
            f"Cerrador: {cerrador}"
        )
        self._notificador.notificar(mensaje, self._grupo_id)

        return ResultadoRegistrarVenta(venta_id=venta.id, desglose=desglose)
