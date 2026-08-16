"""Port interface: counting ENVIADO invoices for Resend quota monitoring.

This ABC defines the read contract that the application service uses to
query send counts from the DB.  The concrete SQLAlchemy adapter is
implemented in the infrastructure layer (Batch 2).

Scope of each query (enforced by the adapter, documented here for clarity):
- contar_mes_a_la_fecha: invoices in the calendar month of `hasta` with
  fecha_emision <= hasta (and >= first day of that month).
- contar_dia: invoices with fecha_emision == dia.

Only invoices with estado_envio == EstadoEnvioFactura.ENVIADO are counted.
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod


class ContadorFacturasEnviadas(ABC):
    """Count ENVIADO invoices for Resend quota approximation.

    The implementation must scope every query to
    ``estado_envio = 'ENVIADO'`` (``EstadoEnvioFactura.ENVIADO``).
    """

    @abstractmethod
    def contar_mes_a_la_fecha(self, hasta: datetime.date) -> int:
        """Count ENVIADO invoices in the calendar month of *hasta*.

        The window is ``[first_day_of_month(hasta), hasta]`` inclusive.
        Invoices outside this range are excluded even if their month matches.

        Args:
            hasta: Upper bound (inclusive).  The calendar month is derived
                from this date; days before the 1st are excluded.

        Returns:
            Non-negative integer count.
        """
        ...

    @abstractmethod
    def contar_dia(self, dia: datetime.date) -> int:
        """Count ENVIADO invoices with fecha_emision == *dia*.

        Args:
            dia: The exact date to match.

        Returns:
            Non-negative integer count.
        """
        ...
