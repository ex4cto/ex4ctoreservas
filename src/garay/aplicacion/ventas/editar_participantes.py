"""Application service: edit the participants (vendedor/cerrador) of a venta."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.aplicacion.ventas.comandos import EditarParticipantesVentaComando
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.puertos.repositorios import (
    AuditoriaVentaRepository,
    ComisionRegistradaRepository,
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    VentaRepository,
)
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class EditarParticipantesVentaService:
    """Orchestrate vendedor/cerrador change with audit, edit-limit, and commission recompute.

    Follows the AUDIT-FIRST pattern. Commission logic mirrors EditarCanalVentaService (Crespo gate).
    Only replacement is allowed — participants cannot be set to null.
    """

    def __init__(
        self,
        ventas: VentaRepository,
        auditoria: AuditoriaVentaRepository,
        reglas_repo: ReglasComisionRepository,
        puntos_repo: PuntoDeVentaRepository,
        comisiones_repo: ComisionRegistradaRepository,
        motor: MotorComisiones,
    ) -> None:
        self._ventas = ventas
        self._auditoria = auditoria
        self._reglas_repo = reglas_repo
        self._puntos_repo = puntos_repo
        self._comisiones_repo = comisiones_repo
        self._motor = motor

    def ejecutar(self, cmd: EditarParticipantesVentaComando) -> None:
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar los participantes.")

        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        verificar_limite_ediciones(self._auditoria, cmd.venta_id)

        datos_previos = {
            "vendedor_nombre": venta.participantes.vendedor_nombre,
            "cerrador_nombre": venta.participantes.cerrador_nombre,
        }

        punto = None
        if venta.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(venta.participantes.punto_de_venta_id)

        # May raise VentaYaAnulada or MismosParticipantes — propagated to caller
        venta.cambiar_participantes(
            nuevo_vendedor_id=cmd.nuevo_vendedor_id,
            nuevo_vendedor_nombre=cmd.nuevo_vendedor_nombre,
            nuevo_cerrador_id=cmd.nuevo_cerrador_id,
            nuevo_cerrador_nombre=cmd.nuevo_cerrador_nombre,
        )

        es_crespo = punto is not None and punto.nombre == "Crespo"
        lookup_punto: str | None = punto.nombre if (es_crespo and punto is not None) else None
        lookup_personas = _derivar_numero_personas(venta.participantes) if es_crespo else None

        reglas = self._reglas_repo.buscar_regla(
            venta.tipo_cliente,
            lookup_punto,
            lookup_personas,
        )
        if reglas is None:
            raise ReglasComisionNoEncontradas(
                f"No se encontraron reglas de comision para tipo={venta.tipo_cliente!r}, "
                f"punto={lookup_punto!r}, personas={lookup_personas!r}"
            )

        desglose = self._motor.calcular(venta, reglas, punto, Decimal("0"))

        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_PARTICIPANTES,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        self._auditoria.guardar(registro)
        self._ventas.guardar(venta)
        self._comisiones_repo.guardar(
            ComisionRegistrada(
                venta_id=cmd.venta_id,
                desglose=desglose,
                fecha=venta.fecha,
            )
        )
