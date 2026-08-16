"""Application service: Resend email-quota monitor.

Orchestrates domain quota logic to produce alerts before the Resend free-tier
caps (3,000/month, 100/day) are hit.  Usage is derived entirely from our own
DB (facturas with estado_envio = ENVIADO); no external Resend API is called.
This is a conservative approximation (re-sends are not separately logged) —
an accepted product tradeoff.

Month-boundary design decision
-------------------------------
The service computes the monthly crossing using two consecutive readings:
  - conteo_actual  = contar_mes_a_la_fecha(ayer)       — cumulative up to yesterday
  - conteo_previo  = contar_mes_a_la_fecha(anteayer)   — cumulative up to the day before

The port's contar_mes_a_la_fecha scopes the query to the calendar month of
its `hasta` argument.  This means:

  * Normal case (same month): contar_mes_a_la_fecha(anteayer) counts invoices in
    the same month as ayer, up through anteayer — a valid delta window.

  * Month boundary (hoy = 2nd of month, anteayer = last day of prev month):
    contar_mes_a_la_fecha(anteayer) would count invoices in the PREVIOUS month,
    not the current one.  Using that count as "previo" for the current month's
    threshold check would either suppress valid crossings or produce noise.
    The correct previo for a fresh month is 0.

The boundary is detected by checking whether anteayer < first_day_of_month(ayer).
When true, previo is forced to 0.  This means:

  - On the first two days of a new month the service can fire all bands in one
    shot if ayer's count is already above a threshold — correct behaviour.
  - Past threshold crossings from the prior month are never carried over.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from garay.dominio.infraestructura_monitor.cuota import (
    banda_mensual_cruzada,
    bandas_absolutas,
    supera_umbral_diario,
)
from garay.dominio.puertos.contador_facturas import ContadorFacturasEnviadas


@dataclass(frozen=True)
class AvisoCuota:
    """An alert ready to be delivered via Telegram (or any notifier).

    Attributes:
        tipo: "mensual" or "diario".
        umbral: The absolute threshold that was crossed (monthly) or the
            configured daily threshold.
        conteo: The actual send count that triggered the alert.
        cap: The applicable cap (monthly or daily).
    """

    tipo: str
    umbral: int
    conteo: int
    cap: int


class MonitorCuotaResendService:
    """Evaluate Resend quota usage for a given date and return alerts.

    Depends on ContadorFacturasEnviadas (port) for DB reads.
    All quota logic is delegated to stateless domain functions.
    """

    def __init__(
        self,
        contador: ContadorFacturasEnviadas,
        cap_mensual: int,
        cap_diario: int,
        bandas_mensual: tuple[float, ...],
        umbral_diario: int,
    ) -> None:
        self._contador = contador
        self._cap_mensual = cap_mensual
        self._cap_diario = cap_diario
        self._umbrales_mensual = bandas_absolutas(cap_mensual, bandas_mensual)
        self._umbral_diario = umbral_diario

    def avisos_para(self, hoy: datetime.date) -> list[AvisoCuota]:
        """Compute quota alerts for the completed day before *hoy*.

        Args:
            hoy: Reference date (typically today in Bogota timezone).
                The service evaluates the completed day (ayer = hoy - 1).

        Returns:
            A list of AvisoCuota (possibly empty).  May contain at most one
            "mensual" entry and at most one "diario" entry per call.
        """
        avisos: list[AvisoCuota] = []

        ayer = hoy - datetime.timedelta(days=1)
        anteayer = hoy - datetime.timedelta(days=2)

        # --- Monthly band check ---
        conteo_actual = self._contador.contar_mes_a_la_fecha(ayer)

        # Month-boundary guard: if anteayer belongs to a different (previous)
        # calendar month than ayer, treat previo as 0 — the month just started.
        mes_ayer = ayer.replace(day=1)
        conteo_previo = (
            0
            if anteayer < mes_ayer
            else self._contador.contar_mes_a_la_fecha(anteayer)
        )

        banda = banda_mensual_cruzada(conteo_actual, conteo_previo, self._umbrales_mensual)
        if banda is not None:
            avisos.append(
                AvisoCuota(
                    tipo="mensual",
                    umbral=banda,
                    conteo=conteo_actual,
                    cap=self._cap_mensual,
                )
            )

        # --- Daily threshold check ---
        conteo_dia = self._contador.contar_dia(ayer)
        if supera_umbral_diario(conteo_dia, self._umbral_diario):
            avisos.append(
                AvisoCuota(
                    tipo="diario",
                    umbral=self._umbral_diario,
                    conteo=conteo_dia,
                    cap=self._cap_diario,
                )
            )

        return avisos
