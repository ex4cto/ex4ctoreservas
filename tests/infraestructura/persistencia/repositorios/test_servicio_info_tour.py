"""Round-trip persistence tests for Servicio info_tour and observaciones fields.

Spec ref: "Round-trip persistence", "Null round-trip", "Partial content".
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository


def _make_servicio(**kwargs: object) -> Servicio:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "numero": 1,
        "nombre": "Tour Prueba",
        "precio_neto_adulto": Decimal("100000"),
    }
    defaults.update(kwargs)
    return Servicio(**defaults)  # type: ignore[arg-type]


def test_round_trip_both_fields_set(sf: sessionmaker[Session]) -> None:
    """Round-trip preserves both info_tour and observaciones when set."""
    repo = SQLAServicioRepository(sf)
    original = _make_servicio(
        info_tour="Salida 8am, almuerzo incluido",
        observaciones="No apto para embarazadas",
    )
    repo.guardar(original)
    result = repo.buscar_por_id(original.id)
    assert result is not None
    assert result.info_tour == "Salida 8am, almuerzo incluido"
    assert result.observaciones == "No apto para embarazadas"


def test_round_trip_both_fields_none(sf: sessionmaker[Session]) -> None:
    """Round-trip returns None for both fields when not set."""
    repo = SQLAServicioRepository(sf)
    original = _make_servicio()
    repo.guardar(original)
    result = repo.buscar_por_id(original.id)
    assert result is not None
    assert result.info_tour is None
    assert result.observaciones is None


def test_round_trip_partial_only_info_tour(sf: sessionmaker[Session]) -> None:
    """Round-trip preserves info_tour when only that field is set."""
    repo = SQLAServicioRepository(sf)
    original = _make_servicio(
        info_tour="Salida 8am",
        observaciones=None,
    )
    repo.guardar(original)
    result = repo.buscar_por_id(original.id)
    assert result is not None
    assert result.info_tour == "Salida 8am"
    assert result.observaciones is None
