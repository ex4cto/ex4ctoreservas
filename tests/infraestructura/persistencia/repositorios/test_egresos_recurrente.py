"""Persistence tests — gasto_recurrente_id round-trip and sumar_por_recurrente_en_mes (Slice 1)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_FECHA = datetime.date(2026, 7, 15)
_DEFAULT_MONTO = Dinero("100000")


def _make_egreso(
    *,
    fecha: datetime.date = _DEFAULT_FECHA,
    monto: Dinero = _DEFAULT_MONTO,
    gasto_recurrente_id: uuid.UUID | None = None,
    tipo: TipoEgreso = TipoEgreso.MANUAL,
    referencia: str | None = None,
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Pago recurrente de prueba",
        monto=monto,
        fecha=fecha,
        categoria="arriendo",
        tipo=tipo,
        referencia=referencia,
        gasto_recurrente_id=gasto_recurrente_id,
    )


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

class TestGastoRecurrenteIdRoundTrip:
    def test_guardar_con_gasto_recurrente_id_se_preserva(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        egreso = _make_egreso(gasto_recurrente_id=rid)

        repo.guardar(egreso)
        resultado = repo.buscar_por_id(egreso.id)

        assert resultado is not None
        assert resultado.gasto_recurrente_id == rid

    def test_guardar_sin_gasto_recurrente_id_es_none(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAEgresoRepository(sf)
        egreso = _make_egreso(gasto_recurrente_id=None)

        repo.guardar(egreso)
        resultado = repo.buscar_por_id(egreso.id)

        assert resultado is not None
        assert resultado.gasto_recurrente_id is None


# ---------------------------------------------------------------------------
# sumar_por_recurrente_en_mes tests
# ---------------------------------------------------------------------------

class TestSumarPorRecurrenteEnMes:
    def test_devuelve_cero_cuando_no_hay_egresos(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero(0)

    def test_suma_un_solo_egreso(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        egreso = _make_egreso(
            fecha=datetime.date(2026, 7, 10),
            monto=Dinero("300000"),
            gasto_recurrente_id=rid,
        )
        repo.guardar(egreso)

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero("300000")

    def test_suma_dos_pagos_parciales_mismo_recurrente_mismo_mes(
        self, sf: sessionmaker[Session]
    ) -> None:
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        pago1 = _make_egreso(
            fecha=datetime.date(2026, 7, 5),
            monto=Dinero("150000"),
            gasto_recurrente_id=rid,
        )
        pago2 = _make_egreso(
            fecha=datetime.date(2026, 7, 20),
            monto=Dinero("150000"),
            gasto_recurrente_id=rid,
        )
        repo.guardar(pago1)
        repo.guardar(pago2)

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero("300000")
        # Decimal precision — never float
        assert resultado.monto == Decimal("300000.00")

    def test_aislamiento_entre_recurrentes_distintos(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Payments to one recurrent ID must NOT leak into another."""
        repo = SQLAEgresoRepository(sf)
        rid_a = uuid.uuid4()
        rid_b = uuid.uuid4()
        rid_c = uuid.uuid4()

        for rid, monto_str in [(rid_a, "500000"), (rid_b, "200000"), (rid_c, "75000")]:
            repo.guardar(
                _make_egreso(
                    fecha=datetime.date(2026, 7, 10),
                    monto=Dinero(monto_str),
                    gasto_recurrente_id=rid,
                )
            )

        assert repo.sumar_por_recurrente_en_mes(rid_a, año=2026, mes=7) == Dinero("500000")
        assert repo.sumar_por_recurrente_en_mes(rid_b, año=2026, mes=7) == Dinero("200000")
        assert repo.sumar_por_recurrente_en_mes(rid_c, año=2026, mes=7) == Dinero("75000")

    def test_egresos_de_otro_mes_excluidos(self, sf: sessionmaker[Session]) -> None:
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        # July payment — inside
        repo.guardar(
            _make_egreso(
                fecha=datetime.date(2026, 7, 15),
                monto=Dinero("100000"),
                gasto_recurrente_id=rid,
            )
        )
        # June payment — outside
        repo.guardar(
            _make_egreso(
                fecha=datetime.date(2026, 6, 30),
                monto=Dinero("999999"),
                gasto_recurrente_id=rid,
            )
        )
        # August payment — outside
        repo.guardar(
            _make_egreso(
                fecha=datetime.date(2026, 8, 1),
                monto=Dinero("888888"),
                gasto_recurrente_id=rid,
            )
        )

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero("100000")

    def test_ultimo_dia_del_mes_incluido(self, sf: sessionmaker[Session]) -> None:
        """Last day of the target month must be IN the result."""
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        repo.guardar(
            _make_egreso(
                fecha=datetime.date(2026, 7, 31),  # last day of July
                monto=Dinero("50000"),
                gasto_recurrente_id=rid,
            )
        )

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero("50000")

    def test_primer_dia_siguiente_mes_excluido(self, sf: sessionmaker[Session]) -> None:
        """First day of the NEXT month must NOT be included."""
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        repo.guardar(
            _make_egreso(
                fecha=datetime.date(2026, 8, 1),  # first day of August — out of July
                monto=Dinero("50000"),
                gasto_recurrente_id=rid,
            )
        )

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero(0)

    def test_egresos_sin_gasto_recurrente_id_no_aparecen(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Egresos with gasto_recurrente_id=None must never match any recurrent query."""
        repo = SQLAEgresoRepository(sf)
        rid = uuid.uuid4()
        # This egreso has no recurrent link
        repo.guardar(
            _make_egreso(
                fecha=datetime.date(2026, 7, 10),
                monto=Dinero("200000"),
                gasto_recurrente_id=None,
            )
        )

        resultado = repo.sumar_por_recurrente_en_mes(rid, año=2026, mes=7)

        assert resultado == Dinero(0)

    def test_tres_recurrentes_multiples_pagos_aislamiento_completo(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Full isolation check with 3 IDs and multiple payments each."""
        repo = SQLAEgresoRepository(sf)
        rid1 = uuid.uuid4()
        rid2 = uuid.uuid4()
        rid3 = uuid.uuid4()

        # rid1: two payments in July → 400 000
        repo.guardar(_make_egreso(
            fecha=datetime.date(2026, 7, 1),
            monto=Dinero("250000"),
            gasto_recurrente_id=rid1,
        ))
        repo.guardar(_make_egreso(
            fecha=datetime.date(2026, 7, 15),
            monto=Dinero("150000"),
            gasto_recurrente_id=rid1,
        ))

        # rid2: one payment in July → 600 000
        repo.guardar(_make_egreso(
            fecha=datetime.date(2026, 7, 10),
            monto=Dinero("600000"),
            gasto_recurrente_id=rid2,
        ))

        # rid3: payment in June (out of range) + payment in August (out) → 0 for July
        repo.guardar(_make_egreso(
            fecha=datetime.date(2026, 6, 15),
            monto=Dinero("300000"),
            gasto_recurrente_id=rid3,
        ))
        repo.guardar(_make_egreso(
            fecha=datetime.date(2026, 8, 5),
            monto=Dinero("300000"),
            gasto_recurrente_id=rid3,
        ))

        assert repo.sumar_por_recurrente_en_mes(rid1, año=2026, mes=7) == Dinero("400000")
        assert repo.sumar_por_recurrente_en_mes(rid2, año=2026, mes=7) == Dinero("600000")
        assert repo.sumar_por_recurrente_en_mes(rid3, año=2026, mes=7) == Dinero(0)
