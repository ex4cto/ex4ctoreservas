from __future__ import annotations

from dataclasses import dataclass

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class DesgloseComision:
    vendedor: Dinero
    cerrador: Dinero
    punto_de_venta: Dinero
    referido: Dinero
    agencia: Dinero
