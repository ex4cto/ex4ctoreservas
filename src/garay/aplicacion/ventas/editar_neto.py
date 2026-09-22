"""Application service: edit the neto of a venta."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.aplicacion.ventas.comandos import EditarNetoVentaComando
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones_financiero
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


class EditarNetoVentaService:
    """Orchestrate neto change with audit, financial edit-limit, and commission recompute.

    Mirrors EditarCanalVentaService exactly at the structural level (AUDIT-FIRST
    persist, Crespo-gated commission recompute, MotorComisiones -> ComisionRegistrada
    overwrite). Uses the financial verifier (MAX=3 counting EDITAR_CANAL + EDITAR_NETO +
    EDITAR_VALOR_VENTA).
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

    def ejecutar(self, cmd: EditarNetoVentaComando) -> None:
        # Step 1: motivo guard
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el neto de la venta.")

        # Step 2: load venta
        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Step 3: financial edit-limit check BEFORE mutation
        verificar_limite_ediciones_financiero(self._auditoria, cmd.venta_id)

        # Step 4: capture datos_previos BEFORE mutation
        datos_previos = {"neto": str(venta.neto.monto)}

        # Step 5: resolve punto object for commission recompute (venta's CURRENT punto)
        punto = None
        if venta.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(venta.participantes.punto_de_venta_id)

        # Step 6: mutate domain — may raise VentaYaAnulada, MismoNeto,
        #         NetoIgualOSuperaValorVenta — all propagated to caller
        venta.cambiar_neto(cmd.nuevo_neto)

        # Step 7: recompute commission (Crespo gate, mirrors editar_canal.py)
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

        # Step 8: build audit record
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_NETO,
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
