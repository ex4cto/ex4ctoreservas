"""Application service: register a manual expense."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.dominio.puertos.repositorios import CategoriaEgresoRepository, EgresoRepository


class RegistrarEgresoManualService:
    def __init__(
        self,
        egreso_repo: EgresoRepository,
        categoria_repo: CategoriaEgresoRepository,
    ) -> None:
        self._egresos = egreso_repo
        self._categorias = categoria_repo

    def registrar(
        self,
        monto: Decimal,
        descripcion: str,
        categoria: str,
        fecha: datetime.date,
        *,
        moneda: str,
    ) -> Egreso:
        activas = self._categorias.listar_activas()
        if categoria not in activas:
            raise ValueError(f"Categoria no valida: {categoria!r}")
        egreso = Egreso(
            id=uuid.uuid4(),
            descripcion=descripcion,
            monto=Dinero(monto, moneda),
            fecha=fecha,
            categoria=categoria,
            tipo=TipoEgreso.MANUAL,
        )
        self._egresos.guardar(egreso)
        return egreso

    def listar_categorias(self) -> list[str]:
        return self._categorias.listar_activas()
