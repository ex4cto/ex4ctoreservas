"""Application service: edit adultos and ninos (pax) of a venta, recalculating neto."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.aplicacion.ventas.comandos import EditarPaxVentaComando
from garay.aplicacion.ventas.editar_servicio import calcular_neto_tour
from garay.aplicacion.ventas.errores import ServicioNoEncontrado
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones_financiero
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.puertos.repositorios import (
    AuditoriaVentaRepository,
    ComisionRegistradaRepository,
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class EditarPaxVentaService:
    """Orchestrate pax (adultos/ninos) change with neto recalculation, audit, and Crespo gate.

    Follows the same AUDIT-FIRST persist pattern as EditarValorVentaService.
    Neto is recalculated using calcular_neto_tour — the same function used by
    editar_servicio. When the tour has no price (calcular_neto_tour returns None),
    a ServicioNoEncontrado error is raised so the caller can surface it.
    """

    def __init__(
        self,
        ventas: VentaRepository,
        servicios: ServicioRepository,
        auditoria: AuditoriaVentaRepository,
        reglas_repo: ReglasComisionRepository,
        puntos_repo: PuntoDeVentaRepository,
        comisiones_repo: ComisionRegistradaRepository,
        motor: MotorComisiones,
    ) -> None:
        self._ventas = ventas
        self._servicios = servicios
        self._auditoria = auditoria
        self._reglas_repo = reglas_repo
        self._puntos_repo = puntos_repo
        self._comisiones_repo = comisiones_repo
        self._motor = motor

    def ejecutar(self, cmd: EditarPaxVentaComando) -> None:
        # Step 1: motivo guard
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el pax de la venta.")

        # Step 2: load venta
        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Step 3: financial edit-limit check BEFORE mutation
        verificar_limite_ediciones_financiero(self._auditoria, cmd.venta_id)

        # Step 4: capture datos_previos BEFORE mutation
        datos_previos = {
            "adultos": str(venta.adultos),
            "ninos": str(venta.ninos),
            "neto": str(venta.neto.monto),
        }

        # Step 5: resolve horario for the current single-service entry (may be None)
        servicio_actual_id = venta.servicio_ids[0] if venta.servicio_ids else None
        horario_actual: str | None = None
        if venta.horarios_por_servicio is not None and servicio_actual_id is not None:
            horario_actual = venta.horarios_por_servicio.get(servicio_actual_id)

        # Step 6: load the servicio to recalculate neto
        servicio = None
        if servicio_actual_id is not None:
            servicio = self._servicios.buscar_por_id(servicio_actual_id)
        if servicio is None:
            raise ServicioNoEncontrado(
                f"No se encontró el servicio con id={servicio_actual_id}."
            )

        # Step 7: recalculate neto with NEW pax values
        nuevo_neto = calcular_neto_tour(servicio, cmd.adultos, cmd.ninos, horario_actual)
        if nuevo_neto is None:
            raise ServicioNoEncontrado(
                f"El servicio '{getattr(servicio, 'nombre', servicio_actual_id)}'"
                " no tiene precio neto en el catálogo."
            )

        # Step 8: resolve punto for commission recompute (CURRENT punto, before mutation)
        punto = None
        if venta.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(venta.participantes.punto_de_venta_id)

        # Step 9: mutate domain — cambiar_pax may raise VentaYaAnulada, CantidadInvalida
        venta.cambiar_pax(cmd.adultos, cmd.ninos)

        # Step 10: apply recalculated neto — may raise NetoIgualOSuperaValorVenta
        venta.cambiar_neto(nuevo_neto)

        # Step 11: recompute commission (Crespo gate, mirrors editar_valor_venta.py)
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

        # porcentaje_referido = Decimal("0") per ADR-2
        desglose = self._motor.calcular(venta, reglas, punto, Decimal("0"))

        # Step 12: build audit record
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_PAX,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        # Step 13: AUDIT-FIRST persist order
        self._auditoria.guardar(registro)
        self._ventas.guardar(venta)
        self._comisiones_repo.guardar(
            ComisionRegistrada(
                venta_id=cmd.venta_id,
                desglose=desglose,
                fecha=venta.fecha,
            )
        )
