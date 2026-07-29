"""Tests for CandidatoMatch and ResultadoConciliacion value objects."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.conciliacion.entidades import CandidatoMatch, Conciliacion, ResultadoConciliacion
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def _make_venta(valor: int = 100_000) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(valor),
        servicio_ids=[],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(vendedor_nombre="Ana", cerrador_nombre="Ana"),
    )


class TestCandidatoMatch:
    def test_creacion_basica(self) -> None:
        venta = _make_venta()
        candidato = CandidatoMatch(
            venta=venta,
            score=Decimal("0.95"),
            diferencia_monto=Dinero(1000),
        )
        assert candidato.score == Decimal("0.95")
        assert candidato.diferencia_monto == Dinero(1000)

    def test_igualdad_por_venta(self) -> None:
        venta = _make_venta()
        a = CandidatoMatch(venta=venta, score=Decimal("0.9"), diferencia_monto=Dinero(0))
        b = CandidatoMatch(venta=venta, score=Decimal("0.5"), diferencia_monto=Dinero(5000))
        assert a == b

    def test_hash_consistente_con_igualdad(self) -> None:
        venta = _make_venta()
        a = CandidatoMatch(venta=venta, score=Decimal("0.9"), diferencia_monto=Dinero(0))
        b = CandidatoMatch(venta=venta, score=Decimal("0.5"), diferencia_monto=Dinero(5000))
        assert hash(a) == hash(b)

    def test_distintas_ventas_son_distintos(self) -> None:
        a = CandidatoMatch(venta=_make_venta(), score=Decimal("0.9"), diferencia_monto=Dinero(0))
        b = CandidatoMatch(venta=_make_venta(), score=Decimal("0.9"), diferencia_monto=Dinero(0))
        assert a != b


class TestResultadoConciliacion:
    def test_creacion_basica(self) -> None:
        r = ResultadoConciliacion(matcheados=5, sin_match=2, pendientes=3)
        assert r.matcheados == 5
        assert r.sin_match == 2
        assert r.pendientes == 3

    def test_frozen_no_mutable(self) -> None:
        r = ResultadoConciliacion(matcheados=1, sin_match=0, pendientes=0)
        with pytest.raises((AttributeError, TypeError)):
            r.matcheados = 99  # type: ignore[misc]


class TestConciliacionConScore:
    def test_score_y_confianza_opcionales(self) -> None:
        c = Conciliacion(id=uuid.uuid4(), ingreso_id=uuid.uuid4())
        assert c.score is None
        assert c.confianza is None

    def test_score_y_confianza_se_pueden_setear(self) -> None:
        c = Conciliacion(
            id=uuid.uuid4(),
            ingreso_id=uuid.uuid4(),
            score=Decimal("0.95"),
            confianza=Decimal("0.95"),
        )
        assert c.score == Decimal("0.95")
        assert c.confianza == Decimal("0.95")
