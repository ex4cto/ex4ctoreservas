"""Tests for SQLAAuditoriaEgresoRepository and SQLAEgresoRepository.listar_manuales."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.auditoria_egreso import AuditoriaEgreso
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.infraestructura.persistencia.repositorios.auditoria_egresos import (
    SQLAAuditoriaEgresoRepository,
)
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository


def _egreso(tipo: TipoEgreso, fecha: datetime.date) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Concepto",
        monto=Dinero("10000", "COP"),
        fecha=fecha,
        categoria="otro",
        tipo=tipo,
    )


class TestListarManuales:
    def test_solo_retorna_manuales(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAEgresoRepository(sf)
        repo.guardar(_egreso(TipoEgreso.MANUAL, datetime.date(2026, 7, 1)))
        repo.guardar(_egreso(TipoEgreso.AUTOMATICO, datetime.date(2026, 7, 2)))
        manuales = repo.listar_manuales(10)
        assert len(manuales) == 1
        assert manuales[0].tipo == TipoEgreso.MANUAL

    def test_orden_descendente_y_limite(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAEgresoRepository(sf)
        repo.guardar(_egreso(TipoEgreso.MANUAL, datetime.date(2026, 7, 1)))
        repo.guardar(_egreso(TipoEgreso.MANUAL, datetime.date(2026, 7, 3)))
        repo.guardar(_egreso(TipoEgreso.MANUAL, datetime.date(2026, 7, 2)))
        manuales = repo.listar_manuales(2)
        assert len(manuales) == 2
        assert manuales[0].fecha == datetime.date(2026, 7, 3)
        assert manuales[1].fecha == datetime.date(2026, 7, 2)

    def test_vacio(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAEgresoRepository(sf)
        assert repo.listar_manuales(10) == []


class TestAuditoriaEgresoRepo:
    def test_guardar_y_listar_por_egreso_id(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEgresoRepository(sf)
        egreso_id = uuid.uuid4()
        registro = AuditoriaEgreso(
            id=uuid.uuid4(),
            egreso_id=egreso_id,
            campo="monto",
            valor_anterior="100.00",
            valor_nuevo="200.00",
            realizada_por_telegram_id=9,
            realizada_por_nombre="Garay",
            realizada_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
        )
        repo.guardar(registro)
        rows = repo.listar_por_egreso_id(egreso_id)
        assert len(rows) == 1
        assert rows[0].campo == "monto"
        assert rows[0].valor_anterior == "100.00"
        assert rows[0].valor_nuevo == "200.00"
        assert rows[0].realizada_por_nombre == "Garay"

    def test_listar_vacio(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEgresoRepository(sf)
        assert repo.listar_por_egreso_id(uuid.uuid4()) == []
