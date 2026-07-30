"""RegistrarVentaService — application service for registering a sale."""

from __future__ import annotations

import uuid

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando, ResultadoRegistrarVenta
from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    TiqueteraRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.ventas.entidades import Venta


def _fmt_cop(d: Dinero) -> str:
    return "$" + f"{int(d.monto):,}".replace(",", ".")


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
        comisiones_repo: ComisionRegistradaRepository,
    ) -> None:
        self._ventas = ventas
        self._reglas_repo = reglas_repo
        self._tiqueteras = tiqueteras
        self._puntos_repo = puntos_repo
        self._motor = motor
        self._notificador = notificador
        self._grupo_id = grupo_id
        self._comisiones_repo = comisiones_repo

    def ejecutar(self, cmd: RegistrarVentaComando) -> ResultadoRegistrarVenta:
        # 1. Create the Venta aggregate
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=cmd.valor_venta,
            neto=cmd.neto,
            servicio_ids=cmd.servicio_ids,
            cliente_id=cmd.cliente_id,
            tipo_cliente=cmd.tipo_cliente,
            fecha=cmd.fecha,
            participantes=cmd.participantes,
            adultos=cmd.adultos,
            ninos=cmd.ninos,
            abono=cmd.abono,
            canal_origen=cmd.canal_origen,
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

        # 5b. Persist commission record
        comision = ComisionRegistrada(
            venta_id=venta.id,
            desglose=desglose,
            fecha=venta.fecha,
        )
        self._comisiones_repo.guardar(comision)

        # 6. Create tiquetera if a reference photo was provided
        if cmd.foto_referencia is not None:
            tiquetera = Tiquetera(
                id=uuid.uuid4(),
                venta_id=venta.id,
                foto_referencia=cmd.foto_referencia,
                numero_fisico=cmd.numero_fisico,
                procesada=False,
            )
            self._tiqueteras.guardar(tiquetera)

        # 7. Notify the group
        vendedor = cmd.participantes.vendedor_nombre or "—"
        cerrador = cmd.participantes.cerrador_nombre or "—"

        lineas: list[str] = ["🎉 <b>Nueva venta registrada</b>", ""]

        if cmd.servicio_nombres:
            lineas.append(f"📍 Destino: {', '.join(cmd.servicio_nombres)}")

        lineas.append(f"📅 Fecha: {cmd.fecha.strftime('%d/%m/%Y')}")

        if cmd.cliente_nombre:
            lineas.append(f"👤 Cliente: {cmd.cliente_nombre}")

        if cmd.cliente_telefono:
            lineas.append(f"📞 Teléfono: {cmd.cliente_telefono}")

        if cmd.hotel:
            hotel_line = f"🏨 Hotel: {cmd.hotel}"
            if cmd.habitacion:
                hotel_line += f" | Hab: {cmd.habitacion}"
            lineas.append(hotel_line)

        if cmd.ninos > 0:
            suffix = "s" if cmd.ninos != 1 else ""
            lineas.append(f"👥 Pax: {cmd.adultos} adultos / {cmd.ninos} niño{suffix}")
        else:
            lineas.append(f"👥 Pax: {cmd.adultos} adultos")

        valor_line = f"💰 Valor: {_fmt_cop(cmd.valor_venta)}"
        if cmd.abono is not None:
            valor_line += f" | Abono: {_fmt_cop(cmd.abono)}"
        lineas.append(valor_line)

        lineas.append(f"💼 Neto: {_fmt_cop(cmd.neto)}")

        if cmd.numero_fisico:
            lineas.append(f"🎫 Ticket: {cmd.numero_fisico}")

        lineas.append(f"🏷 Tipo: {cmd.tipo_cliente.value}")
        if cmd.canal_origen:
            lineas.append(f"📲 Canal: {cmd.canal_origen}")
        lineas.append("")
        lineas.append("Comisiones:")
        lineas.append(f"  Agencia: {_fmt_cop(desglose.agencia)}")

        if vendedor == cerrador:
            comision_total = _fmt_cop(desglose.vendedor + desglose.cerrador)
            lineas.append(f"  {vendedor}: {comision_total}")
        else:
            lineas.append(f"  Vendedor ({vendedor}): {_fmt_cop(desglose.vendedor)}")
            lineas.append(f"  Cerrador ({cerrador}): {_fmt_cop(desglose.cerrador)}")

        mensaje = "\n".join(lineas)
        self._notificador.notificar(mensaje, self._grupo_id)

        return ResultadoRegistrarVenta(venta_id=venta.id, desglose=desglose)
