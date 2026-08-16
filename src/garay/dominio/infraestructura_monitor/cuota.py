"""Pure domain logic for Resend email-quota monitoring.

No I/O. All functions take plain ints/tuples and return plain values.
The crossing rule (banda_mensual_cruzada) is stateless: it fires exactly once
per band because the caller passes previo/actual from consecutive DB reads.
"""

from __future__ import annotations

import math


def bandas_absolutas(cap: int, bandas_fraccion: tuple[float, ...]) -> tuple[int, ...]:
    """Convert fractional bands to absolute integer thresholds.

    Args:
        cap: The monthly cap (e.g. 3000).
        bandas_fraccion: Fractions of the cap (e.g. (0.80, 0.95, 1.0)).

    Returns:
        Sorted, deduplicated tuple of absolute thresholds
        (e.g. (2400, 2850, 3000)).  Uses floor for each product.
    """
    seen: set[int] = set()
    result: list[int] = []
    for f in bandas_fraccion:
        t = math.floor(cap * f)
        if t not in seen:
            seen.add(t)
            result.append(t)
    result.sort()
    return tuple(result)


def banda_mensual_cruzada(
    conteo_actual: int,
    conteo_previo: int,
    umbrales: tuple[int, ...],
) -> int | None:
    """Return the HIGHEST threshold crossed since the previous evaluation, or None.

    A threshold T is "crossed" when ``conteo_previo < T <= conteo_actual``.
    This stateless rule fires exactly once per band crossing without persisted
    state: the caller provides two consecutive count readings (e.g. yesterday
    and the day before) and the function detects what band — if any — was
    entered between them.

    If multiple thresholds are crossed in one step (e.g. a large spike), the
    highest crossed threshold is returned so the owner is notified of the
    most urgent breach.

    Args:
        conteo_actual: Cumulative send count as of the current evaluation.
        conteo_previo: Cumulative send count as of the previous evaluation.
            Pass 0 when a fresh month resets the window.
        umbrales: Sorted absolute thresholds (output of ``bandas_absolutas``).
            May be unsorted; the check is threshold-by-threshold, and the
            returned value is the maximum crossing so sorting is not required
            for correctness, only for readability.

    Returns:
        The highest threshold T where ``conteo_previo < T <= conteo_actual``,
        or ``None`` if no threshold was crossed.
    """
    highest: int | None = None
    for t in umbrales:
        if conteo_previo < t <= conteo_actual and (highest is None or t > highest):
            highest = t
    return highest


def supera_umbral_diario(conteo_dia: int, umbral: int) -> bool:
    """Return True when the daily send count meets or exceeds the alert threshold.

    Args:
        conteo_dia: Number of ENVIADO invoices for a completed day.
        umbral: The daily alert threshold (e.g. 80).

    Returns:
        True if ``conteo_dia >= umbral``, False otherwise.
    """
    return conteo_dia >= umbral
