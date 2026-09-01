"""Unit tests for _formatear_comision — commission line in the 'sale registered' message.

Shows the per-role split (vendedor/cerrador) whenever both roles earned a
commission — including when the same freelancer played both roles — and a single
total otherwise.
"""

from __future__ import annotations

from decimal import Decimal

from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.infraestructura.telegram.handlers import _formatear_comision

_SNAP = SnapshotReglas(
    tipo_cliente=TipoCliente.INTERNO,
    porcentaje_vendedor=Decimal("0"),
    porcentaje_cerrador=Decimal("0"),
    porcentaje_referido_maximo=Decimal("0"),
    porcentaje_capa_punto=Decimal("0"),
)


def _desglose(vendedor: int, cerrador: int) -> DesgloseComision:
    return DesgloseComision(
        vendedor=Dinero(vendedor),
        cerrador=Dinero(cerrador),
        punto_de_venta=Dinero(0),
        referido=Dinero(0),
        agencia=Dinero(0),
        snapshot=_SNAP,
    )


def test_ambos_roles_mismo_freelancer_muestra_split() -> None:
    """Same freelancer as vendedor and cerrador — must still show the split."""
    assert _formatear_comision(_desglose(56000, 56000)) == (
        "Vendedor: $56.000 / Cerrador: $56.000"
    )


def test_dos_personas_distintas_muestra_split() -> None:
    assert _formatear_comision(_desglose(56000, 40000)) == (
        "Vendedor: $56.000 / Cerrador: $40.000"
    )


def test_solo_vendedor_muestra_total_unico() -> None:
    """Only the vendedor earned — single total, no 'Cerrador: $0'."""
    assert _formatear_comision(_desglose(56000, 0)) == "$56.000"


def test_solo_cerrador_muestra_total_unico() -> None:
    assert _formatear_comision(_desglose(0, 56000)) == "$56.000"


def test_ambos_cero_muestra_cero() -> None:
    assert _formatear_comision(_desglose(0, 0)) == "$0"
