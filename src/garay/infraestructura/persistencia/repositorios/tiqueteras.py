from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import TiqueteraRepository
from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.infraestructura.persistencia.modelos import TiqueteraModel


def _dinero_to_str(d: Dinero | None) -> str | None:
    return str(d.monto) if d is not None else None


def _str_to_dinero(s: object) -> Dinero | None:
    return Dinero(str(s)) if isinstance(s, str) else None


def _datos_to_dict(d: DatosExtraidos) -> dict[str, object]:
    return {
        "valor_venta": _dinero_to_str(d.valor_venta),
        "neto": _dinero_to_str(d.neto),
        "abono": _dinero_to_str(d.abono),
        "nombre_cliente": d.nombre_cliente,
        "telefono": d.telefono,
        "cliente_hotel": d.cliente_hotel,
        "numero_habitacion": d.numero_habitacion,
        "servicio_nombre": d.servicio_nombre,
        "destinos": list(d.destinos),
        "fecha_salida": d.fecha_salida.isoformat() if d.fecha_salida is not None else None,
        "adultos": d.adultos,
        "ninos": d.ninos,
        "numero_ticket": d.numero_ticket,
        "confianza": str(d.confianza),
    }


def _dict_to_datos(raw: dict[str, object]) -> DatosExtraidos:
    fecha_salida_raw = raw.get("fecha_salida")
    fecha_salida: datetime.datetime | None = (
        datetime.datetime.fromisoformat(str(fecha_salida_raw))
        if fecha_salida_raw is not None
        else None
    )

    adultos_raw = raw.get("adultos")
    adultos: int | None = int(adultos_raw) if isinstance(adultos_raw, int) else None

    ninos_raw = raw.get("ninos")
    ninos: int | None = int(ninos_raw) if isinstance(ninos_raw, int) else None

    numero_ticket_raw = raw.get("numero_ticket")
    numero_ticket: int | None = (
        int(numero_ticket_raw) if isinstance(numero_ticket_raw, int) else None
    )

    destinos_raw = raw.get("destinos")
    destinos: tuple[str, ...] = (
        tuple(str(x) for x in destinos_raw) if isinstance(destinos_raw, list) else ()
    )

    nombre_cliente_raw = raw.get("nombre_cliente")
    nombre_cliente: str | None = nombre_cliente_raw if isinstance(nombre_cliente_raw, str) else None

    telefono_raw = raw.get("telefono")
    telefono: str | None = telefono_raw if isinstance(telefono_raw, str) else None

    cliente_hotel_raw = raw.get("cliente_hotel")
    cliente_hotel: str | None = cliente_hotel_raw if isinstance(cliente_hotel_raw, str) else None

    numero_habitacion_raw = raw.get("numero_habitacion")
    numero_habitacion: str | None = (
        numero_habitacion_raw if isinstance(numero_habitacion_raw, str) else None
    )

    servicio_nombre_raw = raw.get("servicio_nombre")
    servicio_nombre: str | None = (
        servicio_nombre_raw if isinstance(servicio_nombre_raw, str) else None
    )

    return DatosExtraidos(
        valor_venta=_str_to_dinero(raw.get("valor_venta")),
        neto=_str_to_dinero(raw.get("neto")),
        abono=_str_to_dinero(raw.get("abono")),
        nombre_cliente=nombre_cliente,
        telefono=telefono,
        cliente_hotel=cliente_hotel,
        numero_habitacion=numero_habitacion,
        servicio_nombre=servicio_nombre,
        destinos=destinos,
        fecha_salida=fecha_salida,
        adultos=adultos,
        ninos=ninos,
        numero_ticket=numero_ticket,
        confianza=Decimal(str(raw.get("confianza", "0"))),
    )


def to_orm(t: Tiquetera) -> TiqueteraModel:
    return TiqueteraModel(
        id=t.id,
        venta_id=t.venta_id,
        foto_referencia=t.foto_referencia,
        numero_fisico=t.numero_fisico,
        numero_ticket=t.numero_ticket,
        procesada=t.procesada,
        datos_extraidos=(
            _datos_to_dict(t.datos_extraidos) if t.datos_extraidos is not None else None
        ),
    )


def to_domain(m: TiqueteraModel) -> Tiquetera:
    return Tiquetera(
        id=m.id,
        venta_id=m.venta_id,
        foto_referencia=m.foto_referencia,
        numero_fisico=m.numero_fisico,
        numero_ticket=m.numero_ticket,
        procesada=m.procesada,
        datos_extraidos=(
            _dict_to_datos(m.datos_extraidos) if m.datos_extraidos is not None else None
        ),
    )


class SQLATiqueteraRepository(TiqueteraRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, tiquetera: Tiquetera) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(tiquetera))

    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> Tiquetera | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(TiqueteraModel).where(TiqueteraModel.venta_id == venta_id)
            ).scalar_one_or_none()
            return to_domain(row) if row else None
