from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puntos_venta.entidades import PuntoDeVenta


def _reglas(**kwargs: object) -> ReglasComision:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "tipo_cliente": TipoCliente.EXTERNO,
        "porcentaje_vendedor": Decimal("20"),
        "porcentaje_cerrador": Decimal("20"),
        "porcentaje_referido_maximo": Decimal("10"),
    }
    defaults.update(kwargs)
    return ReglasComision(**defaults)  # type: ignore[arg-type]


def _punto(porcentaje_capa: Decimal = Decimal("20")) -> PuntoDeVenta:
    return PuntoDeVenta(
        id=uuid.uuid4(),
        nombre="Punto Test",
        porcentaje_capa=porcentaje_capa,
    )


class TestSnapshotReglas:
    def test_desde_reglas_sin_punto(self) -> None:
        reglas = _reglas()
        snap = SnapshotReglas.desde_reglas(reglas, None)
        assert snap.porcentaje_capa_punto == Decimal("0")
        assert snap.tipo_cliente == TipoCliente.EXTERNO
        assert snap.porcentaje_vendedor == Decimal("20")
        assert snap.porcentaje_cerrador == Decimal("20")
        assert snap.porcentaje_referido_maximo == Decimal("10")

    def test_desde_reglas_con_punto(self) -> None:
        reglas = _reglas()
        punto = _punto(Decimal("15"))
        snap = SnapshotReglas.desde_reglas(reglas, punto)
        assert snap.porcentaje_capa_punto == Decimal("15")

    def test_es_frozen(self) -> None:
        reglas = _reglas()
        snap = SnapshotReglas.desde_reglas(reglas, None)
        with pytest.raises(FrozenInstanceError):
            snap.porcentaje_vendedor = Decimal("99")  # type: ignore[misc]


class TestSnapshotReglasCamposNuevos:
    """WU-2: numero_personas and punto_de_venta_nombre fields + backward compat (REQ-08c / B4)."""

    def test_campos_nuevos_defaultean_none(self) -> None:
        reglas = _reglas()
        snap = SnapshotReglas.desde_reglas(reglas, None)
        assert snap.numero_personas is None
        assert snap.punto_de_venta_nombre is None

    def test_desde_reglas_mapea_campos_crespo(self) -> None:
        reglas = _reglas(punto_de_venta_nombre="Crespo", numero_personas=1)
        snap = SnapshotReglas.desde_reglas(reglas, None)
        assert snap.numero_personas == 1
        assert snap.punto_de_venta_nombre == "Crespo"

    def test_desde_reglas_mapea_campos_global_none(self) -> None:
        reglas = _reglas(punto_de_venta_nombre=None, numero_personas=None)
        snap = SnapshotReglas.desde_reglas(reglas, None)
        assert snap.numero_personas is None
        assert snap.punto_de_venta_nombre is None

    def test_snapshot_to_dict_round_trip_con_campos_nuevos(self) -> None:
        """_snapshot_to_dict and _dict_to_snapshot round-trip new fields."""
        from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
            _dict_to_snapshot,
            _snapshot_to_dict,
        )

        reglas = _reglas(punto_de_venta_nombre="Crespo", numero_personas=2)
        snap = SnapshotReglas.desde_reglas(reglas, None)
        d = _snapshot_to_dict(snap)
        assert d["numero_personas"] == "2"
        assert d["punto_de_venta_nombre"] == "Crespo"

        snap2 = _dict_to_snapshot(d)
        assert snap2.numero_personas == 2
        assert snap2.punto_de_venta_nombre == "Crespo"

    def test_snapshot_to_dict_round_trip_campos_none(self) -> None:
        """None fields serialize/deserialize correctly."""
        from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
            _dict_to_snapshot,
            _snapshot_to_dict,
        )

        reglas = _reglas()
        snap = SnapshotReglas.desde_reglas(reglas, None)
        d = _snapshot_to_dict(snap)
        assert d["numero_personas"] is None
        assert d["punto_de_venta_nombre"] is None

        snap2 = _dict_to_snapshot(d)
        assert snap2.numero_personas is None
        assert snap2.punto_de_venta_nombre is None

    def test_dict_to_snapshot_backward_compat_old_dict(self) -> None:
        """Old snapshot dict without new keys deserializes without error (REQ-08c / T13)."""
        from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
            _dict_to_snapshot,
        )

        old_dict: dict[str, object] = {
            "tipo_cliente": "EXTERNO",
            "porcentaje_vendedor": "20",
            "porcentaje_cerrador": "20",
            "porcentaje_referido_maximo": "10",
            "porcentaje_capa_punto": "0",
            # numero_personas and punto_de_venta_nombre intentionally absent
        }
        snap = _dict_to_snapshot(old_dict)
        assert snap.numero_personas is None
        assert snap.punto_de_venta_nombre is None
        assert snap.porcentaje_vendedor == Decimal("20")
