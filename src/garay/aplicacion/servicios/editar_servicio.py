"""Application service: edit a servicio, recording a per-field audit trail."""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from decimal import Decimal
from typing import Any

from garay.aplicacion._util.diff_campos import calcular_diff
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.puertos.repositorios import (
    AuditoriaEntidadesRepository,
    ServicioRepository,
)
from garay.dominio.servicios.entidades import Servicio

_SENTINEL = object()

_CAMPOS_EDITABLES = (
    "precio_neto_adulto",
    "precio_neto_nino",
    "precio_sugerido_adulto",
    "precio_sugerido_nino",
    "netos_por_horario",
    "activo",
    "nombre",
)


class EditarServicioService:
    def __init__(
        self,
        servicios: ServicioRepository,
        auditoria: AuditoriaEntidadesRepository,
    ) -> None:
        self._servicios = servicios
        self._auditoria = auditoria

    def editar(
        self,
        servicio_id: uuid.UUID,
        *,
        precio_neto_adulto: Decimal | None = _SENTINEL,  # type: ignore[assignment]
        precio_neto_nino: Decimal | None = _SENTINEL,  # type: ignore[assignment]
        precio_sugerido_adulto: Decimal | None = _SENTINEL,  # type: ignore[assignment]
        precio_sugerido_nino: Decimal | None = _SENTINEL,  # type: ignore[assignment]
        netos_por_horario: dict[str, Decimal] | None = _SENTINEL,  # type: ignore[assignment]
        activo: bool = _SENTINEL,  # type: ignore[assignment]
        nombre: str = _SENTINEL,  # type: ignore[assignment]
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> Servicio:
        """Edit editable fields on a Servicio; emit one audit row per changed field."""
        if por_telegram_id is None:
            raise ValueError("por_telegram_id es obligatorio para registrar auditoría")

        servicio = self._servicios.buscar_por_id(servicio_id)
        if servicio is None:
            raise ValueError(f"El servicio {servicio_id} no existe.")

        # Build snapshot dicts only for fields that were explicitly passed
        kwargs_nuevos: dict[str, Any] = {}
        if precio_neto_adulto is not _SENTINEL:
            kwargs_nuevos["precio_neto_adulto"] = precio_neto_adulto
        if precio_neto_nino is not _SENTINEL:
            kwargs_nuevos["precio_neto_nino"] = precio_neto_nino
        if precio_sugerido_adulto is not _SENTINEL:
            kwargs_nuevos["precio_sugerido_adulto"] = precio_sugerido_adulto
        if precio_sugerido_nino is not _SENTINEL:
            kwargs_nuevos["precio_sugerido_nino"] = precio_sugerido_nino
        if netos_por_horario is not _SENTINEL:
            kwargs_nuevos["netos_por_horario"] = netos_por_horario
        if activo is not _SENTINEL:
            kwargs_nuevos["activo"] = activo
        if nombre is not _SENTINEL:
            kwargs_nuevos["nombre"] = nombre

        viejo_snapshot: dict[str, Any] = {
            campo: getattr(servicio, campo) for campo in kwargs_nuevos
        }

        # Build updated entity
        actualizado = dataclasses.replace(servicio, **kwargs_nuevos)

        # Persist
        self._servicios.guardar(actualizado)

        # Emit one audit row per changed field
        diff = calcular_diff(viejo_snapshot, kwargs_nuevos)
        ahora = datetime.datetime.now(datetime.UTC)
        for campo, valor_anterior, valor_nuevo in diff:
            self._auditoria.guardar(
                RegistroAuditoria(
                    id=uuid.uuid4(),
                    entidad_tipo="servicio",
                    entidad_id=servicio_id,
                    entidad_clave=None,
                    campo=campo,
                    valor_anterior=valor_anterior,
                    valor_nuevo=valor_nuevo,
                    realizada_por_telegram_id=por_telegram_id,
                    realizada_por_nombre=por_nombre,
                    realizada_at=ahora,
                )
            )

        return actualizado
