"""Tests for the surgical price/permite_ninos updater (scripts/actualizar_precios_servicios).

The updater must touch ONLY precio_neto_adulto, precio_neto_nino and permite_ninos,
leaving activo, nombre, categoria, descripcion and horarios untouched so manual
prod edits survive a re-run.
"""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from scripts.actualizar_precios_servicios import actualizar_precios
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
        id=__import__("uuid").uuid4(),
        numero=1,
        nombre="Tour Real",
        descripcion="desc prod",
        activo=False,
        precio_neto_adulto=Decimal("100000"),
        precio_neto_nino=Decimal("50000"),
        permite_ninos=True,
        categoria="CAT",
        horarios=["07:00"],
    )
    base.update(kw)
    return ServicioModel(**base)


def test_actualiza_solo_precios_y_permite_ninos() -> None:
    sf = _sf()
    with sf.begin() as s:
        s.add(_servicio())

    with sf.begin() as s:
        resumen = actualizar_precios(
            s, [{"numero": 1, "neto_adulto": "85", "neto_nino": None, "permite_ninos": False}]
        )

    assert resumen.actualizados == [1]
    with sf.begin() as s:
        row = s.execute(sa.select(ServicioModel).where(ServicioModel.numero == 1)).scalar_one()
        # Actualizado
        assert row.precio_neto_adulto == Decimal("85000")
        assert row.precio_neto_nino is None
        assert row.permite_ninos is False
        # Intacto
        assert row.activo is False
        assert row.nombre == "Tour Real"
        assert row.categoria == "CAT"
        assert row.descripcion == "desc prod"
        assert row.horarios == ["07:00"]


def test_numero_inexistente_se_reporta() -> None:
    sf = _sf()
    with sf.begin() as s:
        resumen = actualizar_precios(s, [{"numero": 999, "neto_adulto": "50"}])
    assert resumen.no_encontrados == [999]
    assert resumen.actualizados == []


def test_sin_cambios_no_cuenta_como_actualizado() -> None:
    sf = _sf()
    with sf.begin() as s:
        s.add(
            _servicio(
                precio_neto_adulto=Decimal("85000"),
                precio_neto_nino=None,
                permite_ninos=False,
            )
        )
    with sf.begin() as s:
        resumen = actualizar_precios(
            s, [{"numero": 1, "neto_adulto": "85", "neto_nino": None, "permite_ninos": False}]
        )
    assert resumen.sin_cambios == [1]
    assert resumen.actualizados == []


# ---------------------------------------------------------------------------
# Tests for precio_sugerido_adulto / precio_sugerido_nino sync (T1.11)
# ---------------------------------------------------------------------------


def test_actualiza_precio_sugerido_adulto_desde_null() -> None:
    """Script syncs precio_sugerido_adulto from JSON when DB value is NULL."""
    sf = _sf()
    with sf.begin() as s:
        row = _servicio(numero=2)
        row.precio_sugerido_adulto = None
        s.add(row)

    with sf.begin() as s:
        resumen = actualizar_precios(
            s,
            [{"numero": 2, "neto_adulto": "85", "precio_sugerido_adulto": 150}],
        )

    assert resumen.actualizados == [2]
    with sf.begin() as s:
        row2 = s.execute(sa.select(ServicioModel).where(ServicioModel.numero == 2)).scalar_one()
        assert row2.precio_sugerido_adulto == Decimal("150000")


def test_actualiza_precio_sugerido_nino_desde_null() -> None:
    """Script syncs precio_sugerido_nino from JSON when DB value is NULL."""
    sf = _sf()
    with sf.begin() as s:
        row = _servicio(numero=3)
        row.precio_sugerido_nino = None
        s.add(row)

    with sf.begin() as s:
        resumen = actualizar_precios(
            s,
            [{"numero": 3, "neto_adulto": "85", "precio_sugerido_nino": 90}],
        )

    assert resumen.actualizados == [3]
    with sf.begin() as s:
        row3 = s.execute(sa.select(ServicioModel).where(ServicioModel.numero == 3)).scalar_one()
        assert row3.precio_sugerido_nino == Decimal("90000")


def test_sin_cambio_sugerido_no_actualiza() -> None:
    """Script is a no-op when sugerido values already match."""
    sf = _sf()
    with sf.begin() as s:
        row = _servicio(
            numero=4,
            precio_neto_adulto=Decimal("85000"),
            precio_neto_nino=None,
            permite_ninos=True,
        )
        row.precio_sugerido_adulto = Decimal("150000")
        row.precio_sugerido_nino = None
        s.add(row)

    with sf.begin() as s:
        resumen = actualizar_precios(
            s,
            [{
                "numero": 4,
                "neto_adulto": "85",
                "neto_nino": None,
                "permite_ninos": True,
                "precio_sugerido_adulto": 150,
                "precio_sugerido_nino": None,
            }],
        )

    assert resumen.sin_cambios == [4]
    assert resumen.actualizados == []
