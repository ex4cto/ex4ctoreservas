"""Pure domain service for partner (socio) revenue split calculations."""

from __future__ import annotations

from garay.dominio.comun.dinero import Dinero
from garay.dominio.socios.entidades import SocioConfig


def calcular_split_venta(
    agencia: Dinero,
    socios: list[SocioConfig],
) -> dict[str, Dinero]:
    """Distribute `agencia` among partners according to their percentages.

    Invariant: the sum of all returned values == agencia (no lost cents).
    Any centavo residual is assigned to the last partner in the list.
    Returns {nombre_socio: monto}.
    """
    if not socios:
        return {}

    # Calculate each socio's share using aplicar_porcentaje, except the last.
    resultado: dict[str, Dinero] = {}
    partes_previas: list[Dinero] = []

    for socio in socios[:-1]:
        parte = agencia.aplicar_porcentaje(socio.porcentaje)
        resultado[socio.nombre] = parte
        partes_previas.append(parte)

    # The last socio gets the residual to preserve the exact total.
    ultimo = socios[-1]
    suma_previas = sum(partes_previas, start=Dinero(0, agencia.moneda))
    resultado[ultimo.nombre] = agencia - suma_previas

    return resultado
