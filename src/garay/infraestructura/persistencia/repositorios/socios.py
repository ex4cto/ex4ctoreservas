"""SQLAlchemy implementations of SocioConfigRepository and PagoSocioRepository."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puertos.repositorios import PagoSocioRepository, SocioConfigRepository
from garay.dominio.socios.entidades import PagoSocio, SocioConfig
from garay.infraestructura.persistencia.modelos import PagoSocioModel, SocioConfigModel


def _config_to_orm(socio: SocioConfig) -> SocioConfigModel:
    return SocioConfigModel(
        nombre=socio.nombre,
        porcentaje=socio.porcentaje,
        telegram_id=socio.telegram_id,
    )


def _config_to_domain(m: SocioConfigModel) -> SocioConfig:
    return SocioConfig(
        nombre=m.nombre,
        porcentaje=Decimal(str(m.porcentaje)),
        telegram_id=m.telegram_id,
    )


def _pago_to_orm(pago: PagoSocio) -> PagoSocioModel:
    return PagoSocioModel(
        id=pago.id,
        nombre_socio=pago.nombre_socio,
        monto=pago.monto,
        fecha=pago.fecha,
        tipo=pago.tipo,
        nota=pago.nota,
        registrado_en=pago.registrado_en,
    )


def _pago_to_domain(m: PagoSocioModel) -> PagoSocio:
    return PagoSocio(
        id=m.id,
        nombre_socio=m.nombre_socio,
        monto=m.monto,  # TipoDinero returns Dinero directly
        fecha=m.fecha,
        tipo=m.tipo,
        nota=m.nota,
        registrado_en=m.registrado_en,
    )


class SQLASocioConfigRepository(SocioConfigRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def listar(self) -> list[SocioConfig]:
        with self._sf.begin() as session:
            stmt = select(SocioConfigModel).order_by(SocioConfigModel.nombre)
            return [_config_to_domain(m) for m in session.scalars(stmt).all()]

    def guardar(self, socio: SocioConfig) -> None:
        with self._sf.begin() as session:
            session.merge(_config_to_orm(socio))

    def buscar_por_nombre(self, nombre: str) -> SocioConfig | None:
        with self._sf.begin() as session:
            m = session.get(SocioConfigModel, nombre)
            return _config_to_domain(m) if m else None


class SQLAPagoSocioRepository(PagoSocioRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, pago: PagoSocio) -> None:
        with self._sf.begin() as session:
            session.merge(_pago_to_orm(pago))

    def listar(self) -> list[PagoSocio]:
        with self._sf.begin() as session:
            stmt = select(PagoSocioModel).order_by(PagoSocioModel.fecha.desc())
            return [_pago_to_domain(m) for m in session.scalars(stmt).all()]

    def listar_por_socio(self, nombre_socio: str) -> list[PagoSocio]:
        with self._sf.begin() as session:
            stmt = (
                select(PagoSocioModel)
                .where(PagoSocioModel.nombre_socio == nombre_socio)
                .order_by(PagoSocioModel.fecha.desc())
            )
            return [_pago_to_domain(m) for m in session.scalars(stmt).all()]
