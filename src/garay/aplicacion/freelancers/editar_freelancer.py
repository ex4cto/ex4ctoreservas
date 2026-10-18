"""Application service: edit a freelancer, recording a per-field audit trail."""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from typing import Any

from garay.aplicacion._util.diff_campos import calcular_diff
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puertos.repositorios import (
    AuditoriaEntidadesRepository,
    FreelancerRepository,
)

_SENTINEL = object()


class EditarFreelancerService:
    def __init__(
        self,
        freelancers: FreelancerRepository,
        auditoria: AuditoriaEntidadesRepository,
    ) -> None:
        self._freelancers = freelancers
        self._auditoria = auditoria

    def editar(
        self,
        freelancer_id: uuid.UUID,
        *,
        nombre: str = _SENTINEL,  # type: ignore[assignment]
        activo: bool = _SENTINEL,  # type: ignore[assignment]
        es_admin: bool = _SENTINEL,  # type: ignore[assignment]
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> Freelancer:
        """Edit editable fields on a Freelancer; emit one audit row per changed field."""
        if por_telegram_id is None:
            raise ValueError("por_telegram_id es obligatorio para registrar auditoría")

        freelancer = self._freelancers.buscar_por_id(freelancer_id)
        if freelancer is None:
            raise ValueError(f"El freelancer {freelancer_id} no existe.")

        kwargs_nuevos: dict[str, Any] = {}
        if nombre is not _SENTINEL:
            kwargs_nuevos["nombre"] = nombre
        if activo is not _SENTINEL:
            kwargs_nuevos["activo"] = activo
        if es_admin is not _SENTINEL:
            kwargs_nuevos["es_admin"] = es_admin

        viejo_snapshot: dict[str, Any] = {
            campo: getattr(freelancer, campo) for campo in kwargs_nuevos
        }

        actualizado = dataclasses.replace(freelancer, **kwargs_nuevos)
        self._freelancers.guardar(actualizado)

        diff = calcular_diff(viejo_snapshot, kwargs_nuevos)
        ahora = datetime.datetime.now(datetime.UTC)
        for campo, valor_anterior, valor_nuevo in diff:
            self._auditoria.guardar(
                RegistroAuditoria(
                    id=uuid.uuid4(),
                    entidad_tipo="freelancer",
                    entidad_id=freelancer_id,
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
