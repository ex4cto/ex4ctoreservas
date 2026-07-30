from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.dominio.conciliacion.errores import MontoInvalido, ReferenciaIngresoVacia


def _ingreso(**kwargs: object) -> Ingreso:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "banco": "Bancolombia",
        "monto": Dinero(100_000),
        "fecha": datetime.date(2026, 7, 1),
        "referencia": "TXN-001",
    }
    defaults.update(kwargs)
    return Ingreso(**defaults)  # type: ignore[arg-type]


class TestIngreso:
    def test_creacion_valida(self) -> None:
        iid = uuid.uuid4()
        i = Ingreso(
            id=iid,
            banco="Bancolombia",
            monto=Dinero(50_000),
            fecha=datetime.date(2026, 7, 1),
            referencia="REF-01",
        )
        assert i.id == iid
        assert i.banco == "Bancolombia"
        assert i.monto == Dinero(50_000)

    def test_no_clasificado_por_defecto(self) -> None:
        i = _ingreso()
        assert i.clasificado is False

    def test_sin_venta_id_por_defecto(self) -> None:
        i = _ingreso()
        assert i.venta_id is None

    def test_referencia_vacia_levanta_error(self) -> None:
        with pytest.raises(ReferenciaIngresoVacia):
            _ingreso(referencia="   ")

    def test_monto_cero_levanta_error(self) -> None:
        with pytest.raises(MontoInvalido):
            _ingreso(monto=Dinero(0))

    def test_identidad_por_id(self) -> None:
        iid = uuid.uuid4()
        a = _ingreso(id=iid, referencia="R1")
        b = _ingreso(id=iid, referencia="R2")
        assert a == b
        assert hash(a) == hash(b)

    def test_correo_origen_es_none_por_defecto(self) -> None:
        i = _ingreso()
        assert i.correo_origen is None

    def test_reenviado_es_false_por_defecto(self) -> None:
        i = _ingreso()
        assert i.reenviado is False

    def test_correo_origen_se_puede_asignar(self) -> None:
        i = _ingreso(correo_origen="banco@bancolombia.com")
        assert i.correo_origen == "banco@bancolombia.com"

    def test_reenviado_se_puede_asignar(self) -> None:
        i = _ingreso(reenviado=True)
        assert i.reenviado is True
