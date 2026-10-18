"""Application service: edit a PuntoDeVenta, recording a per-field audit trail."""

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
    PuntoDeVentaRepository,
)
from garay.dominio.puntos_venta.entidades import PuntoDeVenta

_SENTINEL = object()


class EditarPuntoDeVentaService:
    def __init__(
        self,
        puntos: PuntoDeVentaRepository,
        auditoria: AuditoriaEntidadesRepository,
    ) -> None:
        self._puntos = puntos
        self._auditoria = auditoria

    def editar(
        self,
        punto_id: uuid.UUID,
        *,
        porcentaje_capa: Decimal = _SENTINEL,  # type: ignore[assignment]
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> PuntoDeVenta:
        """Edit editable fields on a PuntoDeVenta; emit one audit row per changed field."""
        if por_telegram_id is None:
            raise ValueError("por_telegram_id es obligatorio para registrar auditoría")

        punto = self._puntos.buscar_por_id(punto_id)
        if punto is None:
            raise ValueError(f"El punto de venta {punto_id} no existe.")

        kwargs_nuevos: dict[str, Any] = {}
        if porcentaje_capa is not _SENTINEL:
            kwargs_nuevos["porcentaje_capa"] = porcentaje_capa

        viejo_snapshot: dict[str, Any] = {
            campo: getattr(punto, campo) for campo in kwargs_nuevos
        }

        actualizado = dataclasses.replace(punto, **kwargs_nuevos)
        self._puntos.guardar(actualizado)

        diff = calcular_diff(viejo_snapshot, kwargs_nuevos)
        ahora = datetime.datetime.now(datetime.UTC)
        for campo, valor_anterior, valor_nuevo in diff:
            self._auditoria.guardar(
                RegistroAuditoria(
                    id=uuid.uuid4(),
                    entidad_tipo="punto_de_venta",
                    entidad_id=punto_id,
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
