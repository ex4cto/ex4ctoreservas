"""Integration tests for SQLAAuditoriaEntidadesRepository.

RED phase: tests written before the implementation in
src/garay/infraestructura/persistencia/repositorios/auditoria_entidades.py.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.infraestructura.persistencia.repositorios.auditoria_entidades import (
    SQLAAuditoriaEntidadesRepository,
)

_ACTOR_ID = 5870211102
_ACTOR_NOMBRE = "Ryan"

# Use timezone-naive datetimes for SQLite-backed integration tests.
# SQLite's DateTime(timezone=True) stores/returns naive datetimes; timezone
# info is stripped on round-trip. PostgreSQL preserves it. The repo itself
# accepts tz-aware values (production use) — the test fixtures use naive to
# avoid false assertion failures in SQLite-backed CI.
_T0 = datetime.datetime(2026, 10, 15, 10, 0, 0)
_T1 = datetime.datetime(2026, 10, 16, 10, 0, 0)
_T2 = datetime.datetime(2026, 10, 17, 10, 0, 0)


def _registro(
    entidad_tipo: str = "servicio",
    entidad_id: uuid.UUID | None = None,
    entidad_clave: str | None = None,
    campo: str = "precio_neto_adulto",
    valor_anterior: str | None = "50000",
    valor_nuevo: str | None = "60000",
    actor_id: int = _ACTOR_ID,
    actor_nombre: str | None = _ACTOR_NOMBRE,
    realizada_at: datetime.datetime = _T1,
) -> RegistroAuditoria:
    return RegistroAuditoria(
        id=uuid.uuid4(),
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        entidad_clave=entidad_clave,
        campo=campo,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
        realizada_por_telegram_id=actor_id,
        realizada_por_nombre=actor_nombre,
        realizada_at=realizada_at,
    )


class TestGuardarYListar:
    def test_guardar_persiste_fila_recuperable_por_listar(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        entidad_id = uuid.uuid4()
        r = _registro(entidad_id=entidad_id)
        repo.guardar(r)
        rows = repo.listar()
        assert len(rows) == 1
        assert rows[0].id == r.id
        assert rows[0].campo == "precio_neto_adulto"
        assert rows[0].valor_anterior == "50000"
        assert rows[0].valor_nuevo == "60000"

    def test_guardar_preserva_entidad_clave(self, sf: sessionmaker[Session]) -> None:
        """Text-keyed entities (socios_config) use entidad_clave, not entidad_id."""
        repo = SQLAAuditoriaEntidadesRepository(sf)
        r = _registro(entidad_tipo="socio_config", entidad_id=None, entidad_clave="Ryan")
        repo.guardar(r)
        rows = repo.listar()
        assert len(rows) == 1
        assert rows[0].entidad_clave == "Ryan"
        assert rows[0].entidad_id is None

    def test_guardar_preserva_valores_none(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        r = _registro(valor_anterior=None, valor_nuevo=None)
        repo.guardar(r)
        rows = repo.listar()
        assert rows[0].valor_anterior is None
        assert rows[0].valor_nuevo is None


class TestListarFiltros:
    def test_filtro_por_entidad_tipo(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(entidad_tipo="servicio"))
        repo.guardar(_registro(entidad_tipo="freelancer"))
        rows = repo.listar(entidad_tipo="servicio")
        assert len(rows) == 1
        assert rows[0].entidad_tipo == "servicio"

    def test_filtro_por_telegram_id(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(actor_id=111))
        repo.guardar(_registro(actor_id=222))
        rows = repo.listar(por_telegram_id=111)
        assert len(rows) == 1
        assert rows[0].realizada_por_telegram_id == 111

    def test_filtro_por_desde(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(realizada_at=_T0))
        repo.guardar(_registro(realizada_at=_T2))
        rows = repo.listar(desde=datetime.date(2026, 10, 16))
        assert len(rows) == 1
        assert rows[0].realizada_at == _T2

    def test_filtro_por_hasta(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(realizada_at=_T0))
        repo.guardar(_registro(realizada_at=_T2))
        rows = repo.listar(hasta=datetime.date(2026, 10, 15))
        assert len(rows) == 1
        assert rows[0].realizada_at == _T0

    def test_filtro_por_rango_fechas(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(realizada_at=_T0))
        repo.guardar(_registro(realizada_at=_T1))
        repo.guardar(_registro(realizada_at=_T2))
        rows = repo.listar(
            desde=datetime.date(2026, 10, 16),
            hasta=datetime.date(2026, 10, 16),
        )
        assert len(rows) == 1
        assert rows[0].realizada_at == _T1

    def test_sin_filtros_retorna_todos_ordenados_desc(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(realizada_at=_T0))
        repo.guardar(_registro(realizada_at=_T2))
        repo.guardar(_registro(realizada_at=_T1))
        rows = repo.listar()
        assert len(rows) == 3
        assert rows[0].realizada_at == _T2
        assert rows[1].realizada_at == _T1
        assert rows[2].realizada_at == _T0

    def test_combinacion_tipo_y_telegram_id(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(entidad_tipo="servicio", actor_id=111))
        repo.guardar(_registro(entidad_tipo="freelancer", actor_id=111))
        repo.guardar(_registro(entidad_tipo="servicio", actor_id=222))
        rows = repo.listar(entidad_tipo="servicio", por_telegram_id=111)
        assert len(rows) == 1
        assert rows[0].entidad_tipo == "servicio"
        assert rows[0].realizada_por_telegram_id == 111

    def test_filtro_por_actor_nombre_exacto(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(actor_nombre="Ryan"))
        repo.guardar(_registro(actor_nombre="Sharimel"))
        rows = repo.listar(actor_nombre="Ryan")
        assert len(rows) == 1
        assert rows[0].realizada_por_nombre == "Ryan"

    def test_filtro_por_actor_nombre_parcial(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(actor_nombre="Ryan Dev"))
        repo.guardar(_registro(actor_nombre="Sharimel"))
        rows = repo.listar(actor_nombre="Ryan")
        assert len(rows) == 1
        assert rows[0].realizada_por_nombre == "Ryan Dev"

    def test_filtro_por_actor_nombre_none_retorna_todos(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        repo.guardar(_registro(actor_nombre="Ryan"))
        repo.guardar(_registro(actor_nombre="Sharimel"))
        rows = repo.listar(actor_nombre=None)
        assert len(rows) == 2

    def test_listar_vacio(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAAuditoriaEntidadesRepository(sf)
        assert repo.listar() == []
