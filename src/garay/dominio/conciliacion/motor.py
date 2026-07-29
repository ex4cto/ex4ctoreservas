"""Motor de conciliacion de ingresos bancarios contra ventas.

Implementa MotorConciliacionBase calculando un score por similitud de
monto y fecha, y tomando una decision automatica si la confianza supera
el umbral configurado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import CandidatoMatch, Conciliacion, Ingreso
from garay.dominio.conciliacion.servicio import MotorConciliacionBase
from garay.dominio.conciliacion.tipos import EstadoConciliacion
from garay.dominio.ventas.entidades import Venta


@dataclass
class _DecisionInterna:
    estado: EstadoConciliacion
    match_principal: Venta | None
    score: Decimal
    confianza: Decimal


class MotorConciliacion(MotorConciliacionBase):
    """Implementacion concreta del motor de conciliacion basado en scoring."""

    def __init__(
        self,
        *,
        tolerancia_pct: Decimal,
        ventana_dias: int,
        confianza_auto: Decimal,
        peso_monto: Decimal,
        peso_fecha: Decimal,
    ) -> None:
        self._tolerancia_pct = tolerancia_pct
        self._ventana_dias = ventana_dias
        self._confianza_auto = confianza_auto
        self._peso_monto = peso_monto
        self._peso_fecha = peso_fecha

    def conciliar(self, ingreso: Ingreso, ventas_candidatas: list[Venta]) -> Conciliacion:
        """Evalua candidatos y produce una Conciliacion con estado y score."""
        candidatos = self._calcular_candidatos(ingreso, ventas_candidatas)
        decision = self._decidir(candidatos)
        return Conciliacion(
            id=uuid.uuid4(),
            ingreso_id=ingreso.id,
            venta_id=decision.match_principal.id if decision.match_principal else None,
            estado=decision.estado,
            score=decision.score,
            confianza=decision.confianza,
        )

    def _calcular_candidatos(
        self,
        ingreso: Ingreso,
        ventas: list[Venta],
    ) -> list[CandidatoMatch]:
        """Filtra y puntua ventas candidatas contra el ingreso."""
        candidatos: list[CandidatoMatch] = []

        if ingreso.monto.monto == Decimal("0"):
            return candidatos

        for venta in ventas:
            diff_relativa = (
                abs(venta.valor_venta.monto - ingreso.monto.monto) / ingreso.monto.monto
            )
            if diff_relativa > self._tolerancia_pct:
                continue

            similitud_monto = max(Decimal("0"), Decimal("1") - diff_relativa)

            dias_diff = Decimal(abs((venta.fecha - ingreso.fecha).days))
            similitud_fecha = max(
                Decimal("0"),
                Decimal("1") - dias_diff / Decimal(self._ventana_dias),
            )

            score = self._peso_monto * similitud_monto + self._peso_fecha * similitud_fecha
            diferencia = Dinero(abs(venta.valor_venta.monto - ingreso.monto.monto))
            candidatos.append(
                CandidatoMatch(venta=venta, score=score, diferencia_monto=diferencia)
            )

        return sorted(candidatos, key=lambda c: c.score, reverse=True)

    def _decidir(self, candidatos: list[CandidatoMatch]) -> _DecisionInterna:
        """Selecciona el estado final a partir de la lista ordenada de candidatos."""
        if not candidatos:
            return _DecisionInterna(
                estado=EstadoConciliacion.SIN_MATCH,
                match_principal=None,
                score=Decimal("0"),
                confianza=Decimal("0"),
            )

        mejor = candidatos[0]

        if mejor.score >= self._confianza_auto:
            return _DecisionInterna(
                estado=EstadoConciliacion.MATCHEADO,
                match_principal=mejor.venta,
                score=mejor.score,
                confianza=mejor.score,
            )

        # Hay candidatos pero ninguno supera el umbral de confianza automatica.
        return _DecisionInterna(
            estado=EstadoConciliacion.PENDIENTE,
            match_principal=mejor.venta,
            score=mejor.score,
            confianza=mejor.score,
        )
