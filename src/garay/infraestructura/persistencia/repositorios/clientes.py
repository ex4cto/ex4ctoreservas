from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puertos.repositorios import ClienteRepository
from garay.infraestructura.persistencia.modelos import ClienteModel


def to_orm(c: Cliente) -> ClienteModel:
    return ClienteModel(
        id=c.id,
        nombre=c.nombre,
        tipo=str(c.tipo),
        telefono=c.telefono,
        hotel=c.hotel,
        numero_habitacion=c.numero_habitacion,
        email=c.email,
        identificacion=c.identificacion,
        tipo_identificacion=c.tipo_identificacion,
    )


def to_domain(m: ClienteModel) -> Cliente:
    return Cliente(
        id=m.id,
        nombre=m.nombre,
        tipo=TipoCliente(m.tipo),
        telefono=m.telefono,
        hotel=m.hotel,
        numero_habitacion=m.numero_habitacion,
        email=m.email,
        identificacion=m.identificacion,
        tipo_identificacion=m.tipo_identificacion,
    )


class SQLAClienteRepository(ClienteRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, cliente: Cliente) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(cliente))

    def buscar_por_id(self, id: uuid.UUID) -> Cliente | None:
        with self._sf.begin() as session:
            m = session.get(ClienteModel, id)
            return to_domain(m) if m else None

    def buscar_por_nombre(self, nombre: str) -> Cliente | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(ClienteModel).where(ClienteModel.nombre == nombre)
            ).scalar_one_or_none()
            return to_domain(row) if row else None
