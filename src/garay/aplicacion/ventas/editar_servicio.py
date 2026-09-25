"""Application service: edit the tour service of a venta."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.aplicacion.ventas.comandos import EditarServicioVentaComando
from garay.aplicacion.ventas.errores import (
    ServicioMultipleNoSoportado,
    ServicioNoEncontrado,
    ServicioSinPrecio,
)
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones_financiero
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    AuditoriaVentaRepository,
    ComisionRegistradaRepository,
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


def calcular_neto_tour(
    servicio: Servicio,
    adultos: int,
    ninos: int,
    horario: str | None,
) -> Dinero | None:
    precio_adulto = servicio.neto_para_horario(horario)
    if precio_adulto is None:
        return None
    precio_nino = servicio.precio_neto_nino or Decimal("0")
    total = precio_adulto * adultos + precio_nino * ninos
    return Dinero(total)


class EditarServicioVentaService:
    """Orchestrate service change with audit, financial edit-limit, and commission recompute.

    Follows AUDIT-FIRST persist pattern, Crespo-gated commission recompute, and
    MotorComisiones -> ComisionRegistrada overwrite. MVP: only single-service ventas supported.
    """

    def __init__(
        self,
        ventas: VentaRepository,
        auditoria: AuditoriaVentaRepository,
        servicios: ServicioRepository,
        reglas_repo: ReglasComisionRepository,
        puntos_repo: PuntoDeVentaRepository,
        comisiones_repo: ComisionRegistradaRepository,
        motor: MotorComisiones,
    ) -> None:
        self._ventas = ventas
        self._auditoria = auditoria
        self._servicios = servicios
        self._reglas_repo = reglas_repo
        self._puntos_repo = puntos_repo
        self._comisiones_repo = comisiones_repo
        self._motor = motor

    def ejecutar(self, cmd: EditarServicioVentaComando) -> None:
        # Step 1: motivo guard
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el servicio de la venta.")

        # Step 2: load venta
        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Step 3: single-tour guard
        if len(venta.servicio_ids) != 1:
            raise ServicioMultipleNoSoportado(
                "Editar servicio solo soporta ventas con un único servicio en esta versión."
            )

        # Step 4: financial edit-limit check BEFORE mutation
        verificar_limite_ediciones_financiero(self._auditoria, cmd.venta_id)

        # Step 5: load nuevo servicio
        nuevo_servicio = self._servicios.buscar_por_id(cmd.nuevo_servicio_id)
        if nuevo_servicio is None or not nuevo_servicio.activo:
            raise ServicioNoEncontrado(
                f"No se encontró el servicio con id={cmd.nuevo_servicio_id} o no está activo."
            )

        # Step 6: get horario actual from the single service entry
        servicio_actual_id = venta.servicio_ids[0]
        horario_actual: str | None = None
        if venta.horarios_por_servicio is not None:
            horario_actual = venta.horarios_por_servicio.get(servicio_actual_id)

        # Step 7: calculate new neto
        nuevo_neto = calcular_neto_tour(nuevo_servicio, venta.adultos, venta.ninos, horario_actual)
        if nuevo_neto is None:
            raise ServicioSinPrecio(
                f"El servicio '{nuevo_servicio.nombre}' no tiene precio_neto_adulto en el catálogo."
            )

        # Step 8: capture datos_previos BEFORE mutation
        datos_previos = {
            "servicio_ids": [str(sid) for sid in venta.servicio_ids],
            "neto": str(venta.neto.monto),
            "valor_venta": str(venta.valor_venta.monto),
        }

        # Step 9: resolve punto for commission recompute (venta's CURRENT punto, before mutation)
        punto = None
        if venta.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(venta.participantes.punto_de_venta_id)

        # Step 10: mutate domain — may raise VentaYaAnulada, MismoServicio,
        #          NetoIgualOSuperaValorVenta, ValorVentaMenorQueAbono — propagated to caller
        venta.cambiar_servicio([cmd.nuevo_servicio_id], nuevo_neto, cmd.nuevo_valor_venta)

        # Step 11: recompute commission (Crespo gate, mirrors editar_neto.py)
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
            accion=AccionAuditoria.EDITAR_SERVICIO,
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
