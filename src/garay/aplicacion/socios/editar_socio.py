"""Application service: edit a SocioConfig, recording a per-field audit trail."""

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
    SocioConfigRepository,
)
from garay.dominio.socios.entidades import SocioConfig

_SENTINEL = object()


class EditarSocioConfigService:
    def __init__(
        self,
        socios: SocioConfigRepository,
        auditoria: AuditoriaEntidadesRepository,
    ) -> None:
        self._socios = socios
        self._auditoria = auditoria

    def editar(
        self,
        nombre: str,
        *,
        porcentaje: Decimal = _SENTINEL,  # type: ignore[assignment]
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> SocioConfig:
        """Edit editable fields on a SocioConfig; emit one audit row per changed field.

        socios_config identity is text-based (nombre), so audit rows use
        entidad_clave=nombre and entidad_id=None.
        """
        if por_telegram_id is None:
            raise ValueError("por_telegram_id es obligatorio para registrar auditoría")

        socio = self._socios.buscar_por_nombre(nombre)
        if socio is None:
            raise ValueError(f"El socio config '{nombre}' no existe.")

        kwargs_nuevos: dict[str, Any] = {}
        if porcentaje is not _SENTINEL:
            kwargs_nuevos["porcentaje"] = porcentaje

        viejo_snapshot: dict[str, Any] = {
            campo: getattr(socio, campo) for campo in kwargs_nuevos
        }

        actualizado = dataclasses.replace(socio, **kwargs_nuevos)
        self._socios.guardar(actualizado)

        diff = calcular_diff(viejo_snapshot, kwargs_nuevos)
        ahora = datetime.datetime.now(datetime.UTC)
        for campo, valor_anterior, valor_nuevo in diff:
            self._auditoria.guardar(
                RegistroAuditoria(
                    id=uuid.uuid4(),
                    entidad_tipo="socio_config",
                    entidad_id=None,
                    entidad_clave=nombre,
                    campo=campo,
                    valor_anterior=valor_anterior,
                    valor_nuevo=valor_nuevo,
                    realizada_por_telegram_id=por_telegram_id,
                    realizada_por_nombre=por_nombre,
                    realizada_at=ahora,
                )
            )

        return actualizado
