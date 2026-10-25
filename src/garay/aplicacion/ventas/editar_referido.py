"""Application service: edit the referido_alias of a venta with audit and commission recompute."""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.aplicacion.ventas.comandos import EditarReferidoVentaComando
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones_informativo
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
from garay.dominio.ventas.errores import MotivoRequerido, PermisoDenegado, VentaNoEncontrada

# Admin-only: only these telegram_ids may edit the referido on a venta.
_ADMIN_TELEGRAM_IDS: frozenset[int] = frozenset({5870211102, 8710698734, 1379898979})


class EditarReferidoVentaService:
    """Orchestrate referido_alias change with admin guard, audit, and commission recompute.

    Mirrors EditarNetoVentaService at the structural level (AUDIT-FIRST persist,
    commission recompute via MotorComisiones -> ComisionRegistrada overwrite).
    Admin-only: caller telegram_id must be Ryan, Sharimel, or Garay.
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

    def ejecutar(self, cmd: EditarReferidoVentaComando) -> None:
        # Step 1: admin guard (first — cheapest, no DB needed)
        if cmd.realizada_por_telegram_id not in _ADMIN_TELEGRAM_IDS:
            raise PermisoDenegado(
                f"Solo administradores pueden editar el referido. "
                f"ID={cmd.realizada_por_telegram_id} no autorizado."
            )

        # Step 2: motivo guard
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el referido.")

        # Step 3: load venta
        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Step 4: edit-limit check BEFORE mutation
        verificar_limite_ediciones_informativo(self._auditoria, cmd.venta_id)

        # Step 5: capture datos_previos BEFORE mutation
        datos_previos = {"referido_alias": venta.participantes.referido_alias}

        # Step 6: resolve punto for commission recompute
        punto = None
        if venta.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(venta.participantes.punto_de_venta_id)

        # Step 7: mutate domain — may raise MismoReferido or VentaYaAnulada
        venta.cambiar_referido(cmd.nuevo_referido_alias)

        # Step 8: recompute commission (Crespo gate, mirrors editar_neto.py)
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

        desglose = self._motor.calcular(venta, reglas, punto)

        # Step 9: build audit record
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_REFERIDO,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        # Step 10: AUDIT-FIRST persist order
        self._auditoria.guardar(registro)
        self._ventas.guardar(venta)
        self._comisiones_repo.guardar(
            ComisionRegistrada(
                venta_id=cmd.venta_id,
                desglose=desglose,
                fecha=venta.fecha,
            )
        )
