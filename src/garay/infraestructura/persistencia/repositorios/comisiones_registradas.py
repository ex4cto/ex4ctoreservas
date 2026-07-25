from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puertos.repositorios import ComisionRegistradaRepository
from garay.infraestructura.persistencia.modelos import ComisionRegistradaModel


def _snapshot_to_dict(s: SnapshotReglas) -> dict[str, object]:
    return {
        "tipo_cliente": str(s.tipo_cliente),
        "porcentaje_vendedor": str(s.porcentaje_vendedor),
        "porcentaje_cerrador": str(s.porcentaje_cerrador),
        "porcentaje_referido_maximo": str(s.porcentaje_referido_maximo),
        "porcentaje_capa_punto": str(s.porcentaje_capa_punto),
    }


def _dict_to_snapshot(raw: dict[str, object]) -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente(str(raw["tipo_cliente"])),
        porcentaje_vendedor=Decimal(str(raw["porcentaje_vendedor"])),
        porcentaje_cerrador=Decimal(str(raw["porcentaje_cerrador"])),
        porcentaje_referido_maximo=Decimal(str(raw["porcentaje_referido_maximo"])),
        porcentaje_capa_punto=Decimal(str(raw["porcentaje_capa_punto"])),
    )


def to_orm(c: ComisionRegistrada) -> ComisionRegistradaModel:
    return ComisionRegistradaModel(
        venta_id=c.venta_id,
        vendedor=c.desglose.vendedor,
        cerrador=c.desglose.cerrador,
        punto_de_venta=c.desglose.punto_de_venta,
        referido=c.desglose.referido,
        agencia=c.desglose.agencia,
        snapshot_json=_snapshot_to_dict(c.desglose.snapshot),
        fecha=c.fecha,
    )


def to_domain(m: ComisionRegistradaModel) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=m.venta_id,
        desglose=DesgloseComision(
            vendedor=m.vendedor,
            cerrador=m.cerrador,
            punto_de_venta=m.punto_de_venta,
            referido=m.referido,
            agencia=m.agencia,
            snapshot=_dict_to_snapshot(m.snapshot_json),
        ),
        fecha=m.fecha,
    )


class SQLAComisionRegistradaRepository(ComisionRegistradaRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, comision: ComisionRegistrada) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(comision))

    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> ComisionRegistrada | None:
        with self._sf.begin() as session:
            m = session.get(ComisionRegistradaModel, venta_id)
            return to_domain(m) if m else None

    def listar_por_venta_ids(self, ids: list[uuid.UUID]) -> list[ComisionRegistrada]:
        if not ids:
            return []
        with self._sf.begin() as session:
            stmt = select(ComisionRegistradaModel).where(ComisionRegistradaModel.venta_id.in_(ids))
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]
