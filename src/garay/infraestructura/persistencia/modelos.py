"""ORM models — persistence layer mapping for all domain aggregates.

Serialization of complex domain types (UUIDs in JSON lists, SnapshotReglas dicts,
DatosExtraidos dicts) is the responsibility of the repository layer, NOT here.
This module declares table structure and column types only.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Sequence,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.tipos import TipoDinero

# Registered with Base.metadata so Alembic emits explicit CreateSequence / DropSequence.
# SQLite ignores sequence DDL entirely — tests using SQLite are unaffected.
_ticket_seq = Sequence("ticket_seq", metadata=Base.metadata)


class ServicioModel(Base):
    __tablename__ = "servicios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    descripcion: Mapped[str] = mapped_column(String, nullable=False, default="")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    precio_neto_adulto: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    precio_neto_nino: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)


class ClienteModel(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)  # TipoCliente value
    telefono: Mapped[str | None] = mapped_column(String, nullable=True)
    hotel: Mapped[str | None] = mapped_column(String, nullable=True)
    numero_habitacion: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    identificacion: Mapped[str | None] = mapped_column(String, nullable=True)
    tipo_identificacion: Mapped[str | None] = mapped_column(String, nullable=True)


class FreelancerModel(Base):
    __tablename__ = "freelancers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    es_admin: Mapped[bool] = mapped_column(Boolean, server_default=sa.text("false"), nullable=False)


class PuntoDeVentaModel(Base):
    __tablename__ = "puntos_de_venta"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    porcentaje_capa: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class ReglasComisionModel(Base):
    __tablename__ = "reglas_comision"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    tipo_cliente: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    porcentaje_vendedor: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    porcentaje_cerrador: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    porcentaje_referido_maximo: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class VentaModel(Base):
    __tablename__ = "ventas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    valor_venta: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    neto: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    abono: Mapped[Dinero | None] = mapped_column(TipoDinero(), nullable=True)
    # Stored as JSON list of UUID strings; repo layer handles UUID↔str conversion.
    servicio_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clientes.id"), nullable=False
    )
    tipo_cliente: Mapped[str] = mapped_column(String, nullable=False)
    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    adultos: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ninos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estado: Mapped[str] = mapped_column(String, nullable=False, default="PENDIENTE")
    vendedor_nombre: Mapped[str | None] = mapped_column(String, nullable=True)
    cerrador_nombre: Mapped[str | None] = mapped_column(String, nullable=True)
    punto_de_venta_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("puntos_de_venta.id"), nullable=True
    )
    referido_nombre: Mapped[str | None] = mapped_column(String, nullable=True)


class TiqueteraModel(Base):
    __tablename__ = "tiqueteras"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    venta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ventas.id"), nullable=False, unique=True
    )
    foto_referencia: Mapped[str] = mapped_column(String, nullable=False)
    # Physical paper number entered by the user; optional.
    numero_fisico: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # System-assigned via ticket_seq on INSERT; None before first persist.
    numero_ticket: Mapped[int | None] = mapped_column(
        BigInteger, _ticket_seq, nullable=True, unique=True
    )
    procesada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Serialized DatosExtraidos; repo handles conversion to/from domain VO.
    datos_extraidos: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ComisionRegistradaModel(Base):
    __tablename__ = "comisiones_registradas"

    venta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ventas.id"), primary_key=True
    )
    vendedor: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    cerrador: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    punto_de_venta: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    referido: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    agencia: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    # Serialized SnapshotReglas; immutable historical record. Repo handles conversion.
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False)


class IngresoModel(Base):
    __tablename__ = "ingresos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    banco: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    referencia: Mapped[str] = mapped_column(String, nullable=False)
    remitente: Mapped[str | None] = mapped_column(String, nullable=True)
    clasificado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ventas.id"), nullable=True
    )
    # UTC timestamp of receipt. Null for legacy records predating this column.
    fecha_recibido: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class EgresoModel(Base):
    __tablename__ = "egresos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False)  # CategoriaEgreso value
    tipo: Mapped[str] = mapped_column(String, nullable=False, default="manual")  # TipoEgreso
    # Unique message ID; None for manually-created records.
    referencia: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    # UTC timestamp of receipt. Null for legacy/manual records.
    fecha_recibido: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CategoriaEgresoModel(Base):
    __tablename__ = "categorias_egreso"

    nombre: Mapped[str] = mapped_column(String, primary_key=True)
    descripcion: Mapped[str] = mapped_column(String, nullable=False, default="")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class GastoRecurrenteModel(Base):
    __tablename__ = "gastos_recurrentes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[Dinero] = mapped_column(TipoDinero(), nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    dia_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ConciliacionModel(Base):
    __tablename__ = "conciliaciones"
    __table_args__ = (sa.UniqueConstraint("ingreso_id", name="uq_conciliaciones_ingreso_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    ingreso_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingresos.id"), nullable=False
    )
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ventas.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(String, nullable=False, default="pendiente")
    notas: Mapped[str] = mapped_column(String, nullable=False, default="")
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confianza: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
