from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puertos.repositorios import ReglasComisionRepository
from garay.infraestructura.persistencia.modelos import ReglasComisionModel


def to_orm(r: ReglasComision) -> ReglasComisionModel:
    return ReglasComisionModel(
        id=r.id,
        tipo_cliente=str(r.tipo_cliente),
        porcentaje_vendedor=r.porcentaje_vendedor,
        porcentaje_cerrador=r.porcentaje_cerrador,
        porcentaje_referido_maximo=r.porcentaje_referido_maximo,
        punto_de_venta_nombre=r.punto_de_venta_nombre,
        numero_personas=r.numero_personas,
    )


def to_domain(m: ReglasComisionModel) -> ReglasComision:
    return ReglasComision(
        id=m.id,
        tipo_cliente=TipoCliente(m.tipo_cliente),
        porcentaje_vendedor=m.porcentaje_vendedor,
        porcentaje_cerrador=m.porcentaje_cerrador,
        porcentaje_referido_maximo=m.porcentaje_referido_maximo,
        punto_de_venta_nombre=m.punto_de_venta_nombre,
        numero_personas=m.numero_personas,
    )


class SQLAReglasComisionRepository(ReglasComisionRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, reglas: ReglasComision) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(reglas))

    def buscar_por_tipo_cliente(self, tipo: TipoCliente) -> ReglasComision | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(ReglasComisionModel).where(ReglasComisionModel.tipo_cliente == str(tipo))
            ).scalar_one_or_none()
            return to_domain(row) if row else None
