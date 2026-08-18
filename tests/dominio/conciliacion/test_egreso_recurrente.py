"""Domain tests — Egreso.gasto_recurrente_id field (Slice 1)."""

from __future__ import annotations

import datetime
import uuid

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso


def _egreso(**kwargs: object) -> Egreso:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "descripcion": "Pago de arriendo",
        "monto": Dinero(500_000),
        "fecha": datetime.date(2026, 7, 1),
        "categoria": "arriendo",
    }
    defaults.update(kwargs)
    return Egreso(**defaults)  # type: ignore[arg-type]


class TestEgresoGastoRecurrenteId:
    def test_gasto_recurrente_id_es_none_por_defecto(self) -> None:
        e = _egreso()
        assert e.gasto_recurrente_id is None

    def test_gasto_recurrente_id_se_puede_asignar(self) -> None:
        rid = uuid.uuid4()
        e = _egreso(gasto_recurrente_id=rid)
        assert e.gasto_recurrente_id == rid

    def test_construccion_sin_gasto_recurrente_id_sigue_funcionando(self) -> None:
        """Existing callers that don't pass gasto_recurrente_id must not break."""
        e = Egreso(
            id=uuid.uuid4(),
            descripcion="Gasto sin recurrente",
            monto=Dinero(100_000),
            fecha=datetime.date(2026, 8, 1),
            categoria="otro",
            tipo=TipoEgreso.MANUAL,
        )
        assert e.gasto_recurrente_id is None

    def test_construccion_completa_con_todos_los_campos(self) -> None:
        rid = uuid.uuid4()
        e = Egreso(
            id=uuid.uuid4(),
            descripcion="Arriendo mensual",
            monto=Dinero(1_500_000),
            fecha=datetime.date(2026, 8, 5),
            categoria="arriendo",
            tipo=TipoEgreso.MANUAL,
            gasto_recurrente_id=rid,
        )
        assert e.gasto_recurrente_id == rid
