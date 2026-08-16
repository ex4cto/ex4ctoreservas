"""Port interface: fetching Railway resource usage for cost monitoring.

This ABC defines the read contract that the application service uses to
retrieve resource usage data from the Railway GraphQL API.  The concrete
HTTP adapter is implemented in the infrastructure layer (Batch 2).

Method semantics:
- uso_mes_a_la_fecha: Returns actual resource usage (measurement→value)
  from the first day of `hasta`'s month through `hasta` (inclusive).
  Used to compute month-to-date cost.
- estimado_mes: Returns projected resource usage for the current billing
  period (typically the full calendar month).  Used to compute the
  estimated end-of-month bill shown in the alert message.

Return value convention:
  Both methods return a plain dict[str, float] mapping Railway measurement
  names (e.g. "MEMORY_USAGE_GB", "CPU_USAGE") to their resource amounts.
  Unknown or unsupported measurements are included but will be ignored by
  the domain's costo_uso() function.
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod


class ProveedorUsoRailway(ABC):
    """Fetch Railway resource usage amounts for cost computation.

    The implementation must call the Railway GraphQL API endpoint
    ``https://backboard.railway.com/graphql/v2`` with the project's
    ``RAILWAY_PROJECT_ID`` and the measurements
    ``[MEMORY_USAGE_GB, CPU_USAGE, NETWORK_TX_GB, DISK_USAGE_GB]``.
    """

    @abstractmethod
    def uso_mes_a_la_fecha(self, hasta: datetime.date) -> dict[str, float]:
        """Return actual resource usage from the 1st of *hasta*'s month to *hasta*.

        The time window is ``[first_day_of_month(hasta)T00:00:00Z, hasta+1T00:00:00Z)``.

        Args:
            hasta: Upper bound date (inclusive).  The calendar month is derived
                from this date; only days in that same month are included.

        Returns:
            Mapping of measurement name to resource amount.
            Example: ``{"MEMORY_USAGE_GB": 1234.5, "CPU_USAGE": 678.9}``.
        """
        ...

    @abstractmethod
    def estimado_mes(self, hoy: datetime.date) -> dict[str, float]:
        """Return projected resource usage for the current billing period.

        Queries the Railway ``estimatedUsage`` (or equivalent projection)
        for the full billing month that contains *hoy*.

        Args:
            hoy: Reference date (typically today).  Used to determine the
                current billing period.

        Returns:
            Mapping of measurement name to projected resource amount for
            the full billing period.
        """
        ...
