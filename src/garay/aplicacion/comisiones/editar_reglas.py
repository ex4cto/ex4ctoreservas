"""Application service: edit a ReglasComision, recording a per-field audit trail."""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from decimal import Decimal
from typing import Any

from garay.aplicacion._util.diff_campos import calcular_diff
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.puertos.repositorios import (
    AuditoriaEntidadesRepository,
    ReglasComisionRepository,
)

_SENTINEL = object()


class EditarReglasComisionService:
    def __init__(
        self,
        reglas: ReglasComisionRepository,
        auditoria: AuditoriaEntidadesRepository,
    ) -> None:
        self._reglas = reglas
        self._auditoria = auditoria

    def editar(
        self,
        regla_id: uuid.UUID,
        *,
        porcentaje_vendedor: Decimal = _SENTINEL,  # type: ignore[assignment]
        porcentaje_cerrador: Decimal = _SENTINEL,  # type: ignore[assignment]
        punto_de_venta_nombre: str | None = _SENTINEL,  # type: ignore[assignment]
        numero_personas: int | None = _SENTINEL,  # type: ignore[assignment]
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> ReglasComision:
        """Edit editable fields on a ReglasComision; emit one audit row per changed field."""
        if por_telegram_id is None:
            raise ValueError("por_telegram_id es obligatorio para registrar auditoría")

        regla = self._reglas.buscar_por_id(regla_id)
        if regla is None:
            raise ValueError(f"La regla de comision {regla_id} no existe.")

        kwargs_nuevos: dict[str, Any] = {}
        if porcentaje_vendedor is not _SENTINEL:
            kwargs_nuevos["porcentaje_vendedor"] = porcentaje_vendedor
        if porcentaje_cerrador is not _SENTINEL:
            kwargs_nuevos["porcentaje_cerrador"] = porcentaje_cerrador
        if punto_de_venta_nombre is not _SENTINEL:
            kwargs_nuevos["punto_de_venta_nombre"] = punto_de_venta_nombre
        if numero_personas is not _SENTINEL:
            kwargs_nuevos["numero_personas"] = numero_personas

        viejo_snapshot: dict[str, Any] = {
            campo: getattr(regla, campo) for campo in kwargs_nuevos
        }

        actualizado = dataclasses.replace(regla, **kwargs_nuevos)
        self._reglas.guardar(actualizado)

        diff = calcular_diff(viejo_snapshot, kwargs_nuevos)
        ahora = datetime.datetime.now(datetime.UTC)
        for campo, valor_anterior, valor_nuevo in diff:
            self._auditoria.guardar(
                RegistroAuditoria(
                    id=uuid.uuid4(),
                    entidad_tipo="regla_comision",
                    entidad_id=regla_id,
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
