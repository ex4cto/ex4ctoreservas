"""Application service: generate recurring expenses for a given month/year."""

from __future__ import annotations

import calendar
import datetime
import uuid

from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.dominio.puertos.repositorios import EgresoRepository, GastoRecurrenteRepository


class GenerarGastosRecurrentesService:
    def __init__(
        self,
        recurrentes_repo: GastoRecurrenteRepository,
        egreso_repo: EgresoRepository,
    ) -> None:
        self._recurrentes = recurrentes_repo
        self._egresos = egreso_repo

    def generar(self, mes: int, año: int) -> list[Egreso]:
        gastos_activos = self._recurrentes.listar_activos()
        generados: list[Egreso] = []

        for gasto in gastos_activos:
            referencia = f"recurrente-{gasto.id}-{año}-{mes:02d}"
            if self._egresos.existe_referencia(referencia):
                continue

            ultimo_dia = calendar.monthrange(año, mes)[1]
            dia = min(gasto.dia_mes, ultimo_dia)
            fecha = datetime.date(año, mes, dia)

            egreso = Egreso(
                id=uuid.uuid4(),
                descripcion=f"Gasto recurrente: {gasto.nombre}",
                monto=gasto.monto,
                fecha=fecha,
                categoria=gasto.categoria,
                tipo=TipoEgreso.MANUAL,
                referencia=referencia,
            )
            self._egresos.guardar(egreso)
            generados.append(egreso)

        return generados
