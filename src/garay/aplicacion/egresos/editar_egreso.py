"""Application service: edit a manual egreso, recording a per-field audit trail."""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.auditoria_egreso import AuditoriaEgreso
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.errores import EgresoNoEditable
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.dominio.puertos.repositorios import (
    AuditoriaEgresoRepository,
    EgresoRepository,
)


class EditarEgresoService:
    def __init__(
        self,
        egresos: EgresoRepository,
        auditoria: AuditoriaEgresoRepository,
    ) -> None:
        self._egresos = egresos
        self._auditoria = auditoria

    def listar_editables(self, limite: int = 10) -> list[Egreso]:
        return self._egresos.listar_manuales(limite)

    def editar_categoria(
        self, egreso_id: uuid.UUID, categoria: str, *, por_telegram_id: int, por_nombre: str | None
    ) -> Egreso:
        egreso = self._obtener_editable(egreso_id)
        actualizado = dataclasses.replace(egreso, categoria=categoria)
        return self._aplicar(
            actualizado, "categoria", egreso.categoria, categoria, por_telegram_id, por_nombre
        )

    def editar_destinatario(
        self,
        egreso_id: uuid.UUID,
        destinatario: str | None,
        *,
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> Egreso:
        egreso = self._obtener_editable(egreso_id)
        actualizado = dataclasses.replace(egreso, destinatario=destinatario)
        return self._aplicar(
            actualizado,
            "destinatario",
            egreso.destinatario or "—",
            destinatario or "—",
            por_telegram_id,
            por_nombre,
        )

    def editar_concepto(
        self,
        egreso_id: uuid.UUID,
        descripcion: str,
        *,
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> Egreso:
        egreso = self._obtener_editable(egreso_id)
        actualizado = dataclasses.replace(egreso, descripcion=descripcion)
        return self._aplicar(
            actualizado, "concepto", egreso.descripcion, descripcion, por_telegram_id, por_nombre
        )

    def editar_monto(
        self, egreso_id: uuid.UUID, monto: Decimal, *, por_telegram_id: int, por_nombre: str | None
    ) -> Egreso:
        egreso = self._obtener_editable(egreso_id)
        nuevo = Dinero(monto, egreso.monto.moneda)
        actualizado = dataclasses.replace(egreso, monto=nuevo)
        return self._aplicar(
            actualizado,
            "monto",
            str(egreso.monto.monto),
            str(nuevo.monto),
            por_telegram_id,
            por_nombre,
        )

    def editar_fecha(
        self,
        egreso_id: uuid.UUID,
        fecha: datetime.date,
        *,
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> Egreso:
        egreso = self._obtener_editable(egreso_id)
        actualizado = dataclasses.replace(egreso, fecha=fecha)
        return self._aplicar(
            actualizado,
            "fecha",
            egreso.fecha.isoformat(),
            fecha.isoformat(),
            por_telegram_id,
            por_nombre,
        )

    # ------------------------------------------------------------------
    def _obtener_editable(self, egreso_id: uuid.UUID) -> Egreso:
        egreso = self._egresos.buscar_por_id(egreso_id)
        if egreso is None:
            raise ValueError(f"El egreso {egreso_id} no existe.")
        if egreso.tipo != TipoEgreso.MANUAL:
            raise EgresoNoEditable("Solo se pueden editar egresos manuales.")
        return egreso

    def _aplicar(
        self,
        actualizado: Egreso,
        campo: str,
        valor_anterior: str,
        valor_nuevo: str,
        por_telegram_id: int,
        por_nombre: str | None,
    ) -> Egreso:
        self._egresos.guardar(actualizado)
        self._auditoria.guardar(
            AuditoriaEgreso(
                id=uuid.uuid4(),
                egreso_id=actualizado.id,
                campo=campo,
                valor_anterior=valor_anterior,
                valor_nuevo=valor_nuevo,
                realizada_por_telegram_id=por_telegram_id,
                realizada_por_nombre=por_nombre,
                realizada_at=datetime.datetime.now(datetime.UTC),
            )
        )
        return actualizado
