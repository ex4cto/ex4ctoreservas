"""Application service: edit the canal (tipo_cliente) of a venta."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.aplicacion.ventas.comandos import EditarCanalVentaComando
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


class EditarCanalVentaService:
    """Orchestrate tipo_cliente change with audit, edit-limit, and commission recompute.

    Follows the AUDIT-FIRST pattern. Commission logic mirrors RegistrarVentaService (Crespo gate).
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

    def ejecutar(self, cmd: EditarCanalVentaComando) -> None:
        # Step 1: motivo guard
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el canal de la venta.")

        # Step 2: load venta
        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Step 3: verificar_limite_ediciones BEFORE mutation
        verificar_limite_ediciones(self._auditoria, cmd.venta_id)

        # Step 4: capture datos_previos BEFORE mutation
        datos_previos = {"tipo_cliente": venta.tipo_cliente.value}

        # Step 5: resolve punto object (needed for commission recompute)
        punto = None
        if cmd.punto_id is not None:
            punto = self._puntos_repo.buscar_por_id(cmd.punto_id)

        # Step 6: mutate domain — may raise VentaYaAnulada, MismoCanal, PuntoDeVentaRequerido,
        #         DigitalConPuntoDeVenta — all propagated to caller
        venta.cambiar_tipo_cliente(cmd.nuevo_tipo, cmd.punto_id)

        # Step 7: recompute commission — mirrors RegistrarVentaService lines 143-168
        es_crespo = punto is not None and punto.nombre == "Crespo"
        lookup_punto: str | None = punto.nombre if (es_crespo and punto is not None) else None
        lookup_personas = _derivar_numero_personas(venta.participantes) if es_crespo else None

        reglas = self._reglas_repo.buscar_regla(
            cmd.nuevo_tipo,
            lookup_punto,
            lookup_personas,
        )
        if reglas is None:
            raise ReglasComisionNoEncontradas(
                f"No se encontraron reglas de comision para tipo={cmd.nuevo_tipo!r}, "
                f"punto={lookup_punto!r}, personas={lookup_personas!r}"
            )

        desglose = self._motor.calcular(venta, reglas, punto, Decimal("0"))

        # Step 8: build audit record
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_CANAL,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        # Step 9: AUDIT-FIRST persist order
        self._auditoria.guardar(registro)
        self._ventas.guardar(venta)
        self._comisiones_repo.guardar(
            ComisionRegistrada(
                venta_id=cmd.venta_id,
                desglose=desglose,
                fecha=venta.fecha,
            )
        )
