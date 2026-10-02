"""Round-trip tests for ServicioModel / SQLAServicioRepository — precio_sugerido fields."""

from __future__ import annotations

import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia import modelos  # noqa: F401 — registers ORM models
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository


def _make_sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _servicio(**kwargs: object) -> Servicio:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        numero=1,
        nombre="Tour Sugerido",
    )
    defaults.update(kwargs)
    return Servicio(**defaults)  # type: ignore[arg-type]


class TestPrecioSugeridoRoundTrip:
    def test_persiste_ambos_valores_no_nulos(self) -> None:
        """Round-trip preserves non-None precio_sugerido_adulto and nino."""
        sf = _make_sf()
        repo = SQLAServicioRepository(sf)
        servicio = _servicio(
            precio_sugerido_adulto=Decimal("150000"),
            precio_sugerido_nino=Decimal("90000"),
        )
        repo.guardar(servicio)

        cargado = repo.buscar_por_id(servicio.id)
        assert cargado is not None
        assert cargado.precio_sugerido_adulto == Decimal("150000")
        assert cargado.precio_sugerido_nino == Decimal("90000")

    def test_persiste_none_cuando_no_se_provee(self) -> None:
        """Round-trip preserves None for both sugerido fields."""
        sf = _make_sf()
        repo = SQLAServicioRepository(sf)
        servicio = _servicio()  # no sugerido fields
        repo.guardar(servicio)

        cargado = repo.buscar_por_id(servicio.id)
        assert cargado is not None
        assert cargado.precio_sugerido_adulto is None
        assert cargado.precio_sugerido_nino is None

    def test_persiste_adulto_con_nino_none(self) -> None:
        """Can store precio_sugerido_adulto with nino as None."""
        sf = _make_sf()
        repo = SQLAServicioRepository(sf)
        servicio = _servicio(precio_sugerido_adulto=Decimal("200000"))
        repo.guardar(servicio)

        cargado = repo.buscar_por_id(servicio.id)
        assert cargado is not None
        assert cargado.precio_sugerido_adulto == Decimal("200000")
        assert cargado.precio_sugerido_nino is None

    def test_actualizar_valor_sugerido(self) -> None:
        """Saving again with updated sugerido value overwrites the stored value."""
        sf = _make_sf()
        repo = SQLAServicioRepository(sf)
        servicio = _servicio(precio_sugerido_adulto=Decimal("100000"))
        repo.guardar(servicio)

        servicio.precio_sugerido_adulto = Decimal("120000")
        repo.guardar(servicio)

        cargado = repo.buscar_por_id(servicio.id)
        assert cargado is not None
        assert cargado.precio_sugerido_adulto == Decimal("120000")
