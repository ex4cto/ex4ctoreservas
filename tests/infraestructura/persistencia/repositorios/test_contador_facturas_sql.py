"""Tests for ContadorFacturasSQLAlchemy adapter.

TDD RED phase: all tests fail with ModuleNotFoundError until the adapter is created.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.persistencia.contador_facturas_sql import (
    ContadorFacturasSQLAlchemy,
)
from garay.infraestructura.persistencia.modelos import FacturaModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MONTO = Dinero("100000")


def _insert_factura(
    sf: sessionmaker[Session],
    *,
    fecha: datetime.date,
    estado: str,
) -> None:
    """Insert a raw FacturaModel row; bypasses domain logic for speed."""
    with sf.begin() as session:
        session.add(
            FacturaModel(
                id=uuid.uuid4(),
                numero="GT-TEST",
                venta_id=uuid.uuid4(),
                cliente_nombre="Test",
                cliente_email="test@example.com",
                monto_total=_MONTO,
                abono=None,
                fecha_emision=fecha,
                html_contenido="<html/>",
                estado_envio=estado,
            )
        )


# ---------------------------------------------------------------------------
# contar_mes_a_la_fecha
# ---------------------------------------------------------------------------


def test_contar_mes_a_la_fecha_solo_enviados(sf: sessionmaker[Session]) -> None:
    """Only ENVIADO rows in the month of *hasta* are counted."""
    _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="ENVIADO")
    _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="PENDIENTE")
    _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="ERROR")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 7, 31)) == 1


def test_contar_mes_a_la_fecha_limite_superior_inclusivo(sf: sessionmaker[Session]) -> None:
    """Row on *hasta* itself is included in the count."""
    _insert_factura(sf, fecha=datetime.date(2026, 7, 31), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 7, 31)) == 1


def test_contar_mes_a_la_fecha_hasta_excluye_despues(sf: sessionmaker[Session]) -> None:
    """Rows after *hasta* but still in the same calendar month are NOT counted."""
    # Insert on Jul 15; query hasta = Jul 10 → not counted
    _insert_factura(sf, fecha=datetime.date(2026, 7, 15), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 7, 10)) == 0


def test_contar_mes_a_la_fecha_excluye_mes_anterior(sf: sessionmaker[Session]) -> None:
    """Rows in the previous calendar month are never counted."""
    _insert_factura(sf, fecha=datetime.date(2026, 6, 30), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 7, 31)) == 0


def test_contar_mes_a_la_fecha_acumula_todo_el_mes(sf: sessionmaker[Session]) -> None:
    """Multiple ENVIADO rows in the same month all contribute to the count."""
    for day in [1, 10, 20, 31]:
        _insert_factura(sf, fecha=datetime.date(2026, 7, day), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 7, 31)) == 4


def test_contar_mes_a_la_fecha_vacio_retorna_cero(sf: sessionmaker[Session]) -> None:
    """Empty table returns 0."""
    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 7, 31)) == 0


def test_contar_mes_a_la_fecha_primer_dia_del_mes(sf: sessionmaker[Session]) -> None:
    """Window [day1, day1] (hasta is the 1st) counts only that single day."""
    _insert_factura(sf, fecha=datetime.date(2026, 8, 1), estado="ENVIADO")
    _insert_factura(sf, fecha=datetime.date(2026, 7, 31), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_mes_a_la_fecha(datetime.date(2026, 8, 1)) == 1


# ---------------------------------------------------------------------------
# contar_dia
# ---------------------------------------------------------------------------


def test_contar_dia_solo_dia_exacto(sf: sessionmaker[Session]) -> None:
    """Only rows with fecha_emision == *dia* are counted."""
    _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="ENVIADO")
    _insert_factura(sf, fecha=datetime.date(2026, 7, 11), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_dia(datetime.date(2026, 7, 10)) == 1


def test_contar_dia_solo_enviados(sf: sessionmaker[Session]) -> None:
    """Non-ENVIADO rows on the exact date are ignored."""
    _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="ENVIADO")
    _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="PENDIENTE")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_dia(datetime.date(2026, 7, 10)) == 1


def test_contar_dia_multiples_enviados(sf: sessionmaker[Session]) -> None:
    """Multiple ENVIADO rows on the same day are all counted."""
    for _ in range(3):
        _insert_factura(sf, fecha=datetime.date(2026, 7, 10), estado="ENVIADO")

    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_dia(datetime.date(2026, 7, 10)) == 3


def test_contar_dia_sin_filas_retorna_cero(sf: sessionmaker[Session]) -> None:
    """Returns 0 when no rows match."""
    contador = ContadorFacturasSQLAlchemy(sf)
    assert contador.contar_dia(datetime.date(2026, 7, 10)) == 0
