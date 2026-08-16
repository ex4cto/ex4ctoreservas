"""Pure domain logic for Railway cost monitoring.

No I/O. All functions take plain types and return plain values.
The crossing rule (cruza_umbral) is stateless: it fires exactly once
per threshold crossing because the caller passes previo/actual from
consecutive measurements.

Pricing model (Railway Hobby plan):
- Bill = max(plan_fee, usage_cost)
- usage_cost = sum of resource * unit_price for each known measurement
"""

from __future__ import annotations

from dataclasses import dataclass

# Measurement keys returned by the Railway GraphQL API.
_MEASUREMENT_MEMORIA = "MEMORY_USAGE_GB"
_MEASUREMENT_CPU = "CPU_USAGE"
_MEASUREMENT_EGRESS = "NETWORK_TX_GB"
_MEASUREMENT_VOLUMEN = "DISK_USAGE_GB"


@dataclass(frozen=True)
class PreciosRailway:
    """Unit prices for Railway resource measurements (USD).

    Attributes:
        precio_memoria_gb_min: USD per GB·min of memory usage.
        precio_cpu_vcpu_min:   USD per vCPU·min of CPU usage.
        precio_egress_gb:      USD per GB of network egress.
        precio_volumen_gb_min: USD per GB·min of volume (disk) usage.
    """

    precio_memoria_gb_min: float
    precio_cpu_vcpu_min: float
    precio_egress_gb: float
    precio_volumen_gb_min: float


def costo_uso(recursos: dict[str, float], precios: PreciosRailway) -> float:
    """Compute the raw usage cost from resource measurements.

    Multiplies each known measurement by its unit price and sums the results.
    Unknown measurement keys are silently ignored.

    Args:
        recursos: Mapping of measurement name to resource amount
            (e.g. ``{"MEMORY_USAGE_GB": 1000.0, "CPU_USAGE": 500.0}``).
        precios: Unit prices for each resource type.

    Returns:
        Total usage cost in USD.  Returns 0.0 for an empty dict.
    """
    total = 0.0
    total += recursos.get(_MEASUREMENT_MEMORIA, 0.0) * precios.precio_memoria_gb_min
    total += recursos.get(_MEASUREMENT_CPU, 0.0) * precios.precio_cpu_vcpu_min
    total += recursos.get(_MEASUREMENT_EGRESS, 0.0) * precios.precio_egress_gb
    total += recursos.get(_MEASUREMENT_VOLUMEN, 0.0) * precios.precio_volumen_gb_min
    return total


def costo_factura(costo_uso_val: float, plan_fee: float) -> float:
    """Compute the actual Railway bill for a billing period.

    Railway's Hobby plan charges the greater of the plan fee or the raw usage
    cost: ``bill = max(plan_fee, usage_cost)``.

    Args:
        costo_uso_val: Raw usage cost in USD (output of :func:`costo_uso`).
        plan_fee: Monthly plan fee in USD (e.g. 5.0 for the Hobby plan).

    Returns:
        Actual bill in USD (never below ``plan_fee``).
    """
    return max(plan_fee, costo_uso_val)


def cruza_umbral(actual: float, previo: float, umbral: float) -> bool:
    """Return True when the cost just crossed the alert threshold.

    A crossing is detected when ``previo < umbral <= actual``.  This stateless
    rule fires exactly once per crossing without persisted state: the caller
    provides two consecutive cost readings and the function detects whether the
    threshold was entered between them.

    Pass ``previo=0.0`` at a month boundary so a fresh month can re-alert even
    if last month's costs were already above the threshold.

    Args:
        actual: Current month-to-date cost in USD.
        previo: Previous evaluation's month-to-date cost in USD.
            Pass 0.0 when the month just started (boundary reset).
        umbral: Alert threshold in USD.

    Returns:
        True if the threshold was crossed since the previous evaluation.
    """
    return previo < umbral <= actual
