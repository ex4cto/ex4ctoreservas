"""Tests for SQLASocioConfigRepository and SQLAPagoSocioRepository — RED phase."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.socios.entidades import PagoSocio, SocioConfig
from garay.infraestructura.persistencia.repositorios.socios import (
    SQLAPagoSocioRepository,
    SQLASocioConfigRepository,
)


def _config(nombre: str, porcentaje: str = "50", telegram_id: int | None = None) -> SocioConfig:
    return SocioConfig(
        nombre=nombre,
        porcentaje=Decimal(porcentaje),
        telegram_id=telegram_id,
    )


def _pago(nombre_socio: str = "garay", tipo: str = "total") -> PagoSocio:
    return PagoSocio(
        id=uuid.uuid4(),
        nombre_socio=nombre_socio,
        monto=Dinero("500000"),
        fecha=datetime.date(2026, 9, 15),
        tipo=tipo,
        nota=None,
        registrado_en=datetime.datetime(2026, 9, 15, 10, 0, 0),
    )


class TestSocioConfigRepository:
    def test_guardar_y_listar(self, sf: sessionmaker[Session]) -> None:
        repo = SQLASocioConfigRepository(sf)
        repo.guardar(_config("garay", "50"))
        repo.guardar(_config("ryan", "25"))
        repo.guardar(_config("empresa", "25"))

        configs = repo.listar()
        nombres = [c.nombre for c in configs]
        assert "garay" in nombres
        assert "ryan" in nombres
        assert "empresa" in nombres
        assert len(configs) == 3

    def test_guardar_actualiza_existente(self, sf: sessionmaker[Session]) -> None:
        repo = SQLASocioConfigRepository(sf)
        repo.guardar(_config("garay", "50"))

        # Update porcentaje
        updated = SocioConfig(nombre="garay", porcentaje=Decimal("60"), telegram_id=999)
        repo.guardar(updated)

        resultado = repo.buscar_por_nombre("garay")
        assert resultado is not None
        assert resultado.porcentaje == Decimal("60")
        assert resultado.telegram_id == 999

    def test_buscar_por_nombre_existente(self, sf: sessionmaker[Session]) -> None:
        repo = SQLASocioConfigRepository(sf)
        repo.guardar(_config("ryan", "25", telegram_id=111222333))

        resultado = repo.buscar_por_nombre("ryan")
        assert resultado is not None
        assert resultado.nombre == "ryan"
        assert resultado.porcentaje == Decimal("25")
        assert resultado.telegram_id == 111222333

    def test_buscar_por_nombre_inexistente(self, sf: sessionmaker[Session]) -> None:
        repo = SQLASocioConfigRepository(sf)
        assert repo.buscar_por_nombre("fantasma") is None

    def test_listar_vacio(self, sf: sessionmaker[Session]) -> None:
        repo = SQLASocioConfigRepository(sf)
        assert repo.listar() == []

    def test_preserva_telegram_id_none(self, sf: sessionmaker[Session]) -> None:
        repo = SQLASocioConfigRepository(sf)
        repo.guardar(_config("empresa", "25", telegram_id=None))

        resultado = repo.buscar_por_nombre("empresa")
        assert resultado is not None
        assert resultado.telegram_id is None


class TestPagoSocioRepository:
    def test_guardar_y_listar(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        repo.guardar(_pago("garay", "total"))
        repo.guardar(_pago("ryan", "parcial"))

        pagos = repo.listar()
        assert len(pagos) == 2
        nombres = [p.nombre_socio for p in pagos]
        assert "garay" in nombres
        assert "ryan" in nombres

    def test_listar_por_socio(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        repo.guardar(_pago("garay", "total"))
        repo.guardar(_pago("garay", "parcial"))
        repo.guardar(_pago("ryan", "total"))

        pagos_garay = repo.listar_por_socio("garay")
        assert len(pagos_garay) == 2
        assert all(p.nombre_socio == "garay" for p in pagos_garay)

    def test_listar_por_socio_sin_resultados(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        assert repo.listar_por_socio("empresa") == []

    def test_listar_vacio(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        assert repo.listar() == []

    def test_preserva_monto_como_dinero(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        pago = _pago("garay", "total")
        repo.guardar(pago)

        resultado = repo.listar()[0]
        assert resultado.monto == Dinero("500000")

    def test_preserva_nota_none(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        repo.guardar(_pago())

        resultado = repo.listar()[0]
        assert resultado.nota is None

    def test_preserva_nota_texto(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAPagoSocioRepository(sf)
        pago = PagoSocio(
            id=uuid.uuid4(),
            nombre_socio="ryan",
            monto=Dinero("100000"),
            fecha=datetime.date(2026, 9, 15),
            tipo="parcial",
            nota="Adelanto agosto",
            registrado_en=datetime.datetime(2026, 9, 15, 10, 0, 0),
        )
        repo.guardar(pago)

        resultado = repo.listar_por_socio("ryan")[0]
        assert resultado.nota == "Adelanto agosto"
