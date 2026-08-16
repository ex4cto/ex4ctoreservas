"""Application service: Railway cost monitor.

Orchestrates domain cost logic to produce an alert when actual month-to-date
Railway spend crosses a configured USD threshold.  The alert also includes
the estimated end-of-month bill for owner context.

Design: stateless band-crossing (Option B)
------------------------------------------
Like MonitorCuotaResendService, this service uses two consecutive date
readings (ayer and anteayer) to detect a single-crossing event without
persisted state.  The domain function cruza_umbral encodes the rule
``previo < umbral <= actual``.

Month-boundary design decision
-------------------------------
The service computes the cost crossing using two consecutive readings:
  - costo_actual = costo_uso(proveedor.uso_mes_a_la_fecha(ayer), precios)
  - costo_previo = costo_uso(proveedor.uso_mes_a_la_fecha(anteayer), precios)

The port's uso_mes_a_la_fecha scopes the query to the calendar month of
its `hasta` argument.  This means:

  * Normal case (same month): uso_mes_a_la_fecha(anteayer) counts resources
    in the same month as ayer, up through anteayer — a valid delta window.

  * Month boundary (hoy = 2nd of month, anteayer = last day of prev month):
    uso_mes_a_la_fecha(anteayer) would count resources in the PREVIOUS month,
    not the current one.  Using that cost as "previo" for the current month's
    threshold check would suppress valid crossings.
    The correct previo for a fresh month is 0.0.

The boundary is detected by checking whether anteayer < first_day_of_month(ayer).
When true, previo is forced to 0.0.  This mirrors the identical rule in
MonitorCuotaResendService (cuota_resend.py).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from garay.dominio.infraestructura_monitor.costo_railway import (
    PreciosRailway,
    costo_factura,
    costo_uso,
    cruza_umbral,
)
from garay.dominio.puertos.proveedor_uso_railway import ProveedorUsoRailway


@dataclass(frozen=True)
class AvisoCostoRailway:
    """An alert ready to be delivered via Telegram (or any notifier).

    Attributes:
        costo_actual: Actual month-to-date cost in USD that triggered the alert.
        umbral: The configured alert threshold in USD.
        estimado_factura: Projected end-of-month Railway bill in USD
            (max of plan fee and estimated usage cost).
    """

    costo_actual: float
    umbral: float
    estimado_factura: float


class MonitorCostoRailwayService:
    """Evaluate Railway month-to-date cost and return an alert when the threshold is crossed.

    Depends on ProveedorUsoRailway (port) for resource usage queries.
    All cost and crossing logic is delegated to stateless domain functions.
    """

    def __init__(
        self,
        proveedor: ProveedorUsoRailway,
        precios: PreciosRailway,
        umbral: float,
        plan_fee: float,
    ) -> None:
        self._proveedor = proveedor
        self._precios = precios
        self._umbral = umbral
        self._plan_fee = plan_fee

    def avisos_para(self, hoy: datetime.date) -> list[AvisoCostoRailway]:
        """Compute Railway cost alerts for the completed day before *hoy*.

        Args:
            hoy: Reference date (typically today in Bogota timezone).
                The service evaluates the completed day (ayer = hoy - 1).

        Returns:
            A list of AvisoCostoRailway.  Contains at most one entry per call
            (the threshold is either crossed or not).
        """
        ayer = hoy - datetime.timedelta(days=1)
        anteayer = hoy - datetime.timedelta(days=2)

        # Month-to-date cost as of yesterday.
        costo_actual = costo_uso(self._proveedor.uso_mes_a_la_fecha(ayer), self._precios)

        # Month-boundary guard: if anteayer belongs to a different (previous)
        # calendar month than ayer, treat previo as 0.0 — the month just started.
        mes_ayer = ayer.replace(day=1)
        costo_previo: float = (
            0.0
            if anteayer < mes_ayer
            else costo_uso(self._proveedor.uso_mes_a_la_fecha(anteayer), self._precios)
        )

        if not cruza_umbral(costo_actual, costo_previo, self._umbral):
            return []

        # Threshold crossed: fetch estimate and build aviso.
        estimado = self._proveedor.estimado_mes(hoy)
        estimado_factura = costo_factura(costo_uso(estimado, self._precios), self._plan_fee)

        return [
            AvisoCostoRailway(
                costo_actual=costo_actual,
                umbral=self._umbral,
                estimado_factura=estimado_factura,
            )
        ]
