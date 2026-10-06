"""Tests for the surgical catalog sync script (scripts/sincronizar_catalogo).

The syncer must:
  - INSERT new services (numero not in DB) with correct fields
  - UPDATE only nombre, activo, categoria for existing services
  - Track sin_cambios when nothing has changed
  - NEVER touch horarios, descripcion, precio_neto_adulto, precio_neto_nino, permite_ninos
  - Support --dry-run (rollback, no persistence)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import sqlalchemy as sa
from scripts.seed import seed_id
from scripts.sincronizar_catalogo import sincronizar_catalogo
from sqlalchemy.orm import Session, sessionmaker

from garay.infraestructura.persistencia import modelos  # noqa: F401
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.modelos import ServicioModel


def _sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _servicio(**kw: object) -> ServicioModel:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        numero=1,
        nombre="Tour Original",
        descripcion="descripcion produccion",
        activo=True,
        precio_neto_adulto=Decimal("100000"),
        precio_neto_nino=Decimal("50000"),
        permite_ninos=True,
        categoria="CAT_ORIGINAL",
        horarios=["08:00", "14:00"],
    )
    base.update(kw)
    return ServicioModel(**base)


# ---------------------------------------------------------------------------
# Test 1: insert a brand-new service
# ---------------------------------------------------------------------------


def test_inserta_servicio_nuevo() -> None:
    sf = _sf()
    entry = {"numero": 42, "nombre": "Tour Nuevo", "activo": True, "categoria": "CIUDAD"}

    with sf.begin() as s:
        resumen = sincronizar_catalogo(s, [entry])
        s.flush()

    assert resumen.insertados == [42]
    assert resumen.actualizados == []
    assert resumen.sin_cambios == []

    with sf.begin() as s:
        row = s.execute(
            sa.select(ServicioModel).where(ServicioModel.numero == 42)
        ).scalar_one()
        assert row.nombre == "Tour Nuevo"
        assert row.activo is True
        assert row.categoria == "CIUDAD"
        assert row.id == seed_id("servicio:42")
        # horarios must not be None — model has NOT NULL default
        assert row.horarios is not None


# ---------------------------------------------------------------------------
# Test 2: update nombre/activo/categoria for an existing service
# ---------------------------------------------------------------------------


def test_actualiza_nombre_activo_categoria() -> None:
    sf = _sf()
    with sf.begin() as s:
        s.add(_servicio(numero=5, nombre="Viejo Nombre", activo=True, categoria="PLAYA"))

    entry = {"numero": 5, "nombre": "Nombre Nuevo", "activo": False, "categoria": "MONTANA"}

    with sf.begin() as s:
        resumen = sincronizar_catalogo(s, [entry])

    assert resumen.actualizados == [5]
    assert resumen.insertados == []
    assert resumen.sin_cambios == []

    with sf.begin() as s:
        row = s.execute(
            sa.select(ServicioModel).where(ServicioModel.numero == 5)
        ).scalar_one()
        assert row.nombre == "Nombre Nuevo"
        assert row.activo is False
        assert row.categoria == "MONTANA"
        # Untouched fields
        assert row.descripcion == "descripcion produccion"
        assert row.precio_neto_adulto == Decimal("100000")
        assert row.precio_neto_nino == Decimal("50000")
        assert row.permite_ninos is True
        assert row.horarios == ["08:00", "14:00"]


# ---------------------------------------------------------------------------
# Test 3: sin_cambios when entry matches DB exactly
# ---------------------------------------------------------------------------


def test_sin_cambios_cuando_igual() -> None:
    sf = _sf()
    with sf.begin() as s:
        s.add(_servicio(numero=7, nombre="Tour Estable", activo=True, categoria="SIERRA"))

    entry = {"numero": 7, "nombre": "Tour Estable", "activo": True, "categoria": "SIERRA"}

    with sf.begin() as s:
        resumen = sincronizar_catalogo(s, [entry])

    assert resumen.sin_cambios == [7]
    assert resumen.actualizados == []
    assert resumen.insertados == []


# ---------------------------------------------------------------------------
# Test 4: horarios and precio are never touched on update
# ---------------------------------------------------------------------------


def test_no_toca_horarios_ni_precio() -> None:
    sf = _sf()
    with sf.begin() as s:
        s.add(
            _servicio(
                numero=10,
                nombre="Tour Con Precios",
                activo=True,
                categoria="AVENTURA",
                horarios=["09:00", "15:00"],
                precio_neto_adulto=Decimal("200000"),
                precio_neto_nino=Decimal("100000"),
                permite_ninos=False,
            )
        )

    # Entry changes nombre and categoria only
    entry = {
        "numero": 10,
        "nombre": "Tour Con Precios Renombrado",
        "activo": True,
        "categoria": "AVENTURA_V2",
    }

    with sf.begin() as s:
        resumen = sincronizar_catalogo(s, [entry])

    assert resumen.actualizados == [10]

    with sf.begin() as s:
        row = s.execute(
            sa.select(ServicioModel).where(ServicioModel.numero == 10)
        ).scalar_one()
        # Updated
        assert row.nombre == "Tour Con Precios Renombrado"
        assert row.categoria == "AVENTURA_V2"
        # NEVER touched
        assert row.horarios == ["09:00", "15:00"]
        assert row.precio_neto_adulto == Decimal("200000")
        assert row.precio_neto_nino == Decimal("100000")
        assert row.permite_ninos is False


# ---------------------------------------------------------------------------
# Test 5: dry_run does not persist changes
# ---------------------------------------------------------------------------


def test_dry_run_no_persiste() -> None:
    sf = _sf()
    with sf.begin() as s:
        s.add(_servicio(numero=3, nombre="Nombre Prod", activo=True, categoria="MAR"))

    # In dry_run, we roll back after the call
    with sf() as s:
        # New service
        resumen_nuevo = sincronizar_catalogo(
            s, [{"numero": 99, "nombre": "Tour Fantasma", "activo": True, "categoria": "X"}]
        )
        assert resumen_nuevo.insertados == [99]
        s.rollback()

    # Service 99 must NOT be in DB
    with sf.begin() as s:
        row = s.execute(
            sa.select(ServicioModel).where(ServicioModel.numero == 99)
        ).scalar_one_or_none()
        assert row is None

    # Existing service update rolled back
    with sf() as s:
        resumen_upd = sincronizar_catalogo(
            s, [{"numero": 3, "nombre": "Nombre Cambiado", "activo": False, "categoria": "MAR"}]
        )
        assert resumen_upd.actualizados == [3]
        s.rollback()

    with sf.begin() as s:
        row2 = s.execute(
            sa.select(ServicioModel).where(ServicioModel.numero == 3)
        ).scalar_one()
        assert row2.nombre == "Nombre Prod"
        assert row2.activo is True
