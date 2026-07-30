from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.errores import DescripcionEgresoVacia, MontoInvalido
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


class TestEgreso:
    def test_creacion_valida(self) -> None:
        eid = uuid.uuid4()
        e = Egreso(
            id=eid,
            descripcion="Uniformes equipo",
            monto=Dinero(200_000),
            fecha=datetime.date(2026, 7, 1),
            categoria="uniformes",
        )
        assert e.id == eid
        assert e.descripcion == "Uniformes equipo"
        assert e.categoria == "uniformes"

    def test_tipo_manual_por_defecto(self) -> None:
        e = _egreso()
        assert e.tipo == TipoEgreso.MANUAL

    def test_descripcion_vacia_levanta_error(self) -> None:
        with pytest.raises(DescripcionEgresoVacia):
            _egreso(descripcion="   ")

    def test_monto_cero_levanta_error(self) -> None:
        with pytest.raises(MontoInvalido):
            _egreso(monto=Dinero(0))

    def test_identidad_por_id(self) -> None:
        eid = uuid.uuid4()
        a = _egreso(id=eid, descripcion="A")
        b = _egreso(id=eid, descripcion="B")
        assert a == b
        assert hash(a) == hash(b)

    def test_correo_origen_es_none_por_defecto(self) -> None:
        e = _egreso()
        assert e.correo_origen is None

    def test_reenviado_es_false_por_defecto(self) -> None:
        e = _egreso()
        assert e.reenviado is False

    def test_correo_origen_se_puede_asignar(self) -> None:
        e = _egreso(correo_origen="banco@bancolombia.com")
        assert e.correo_origen == "banco@bancolombia.com"

    def test_reenviado_se_puede_asignar(self) -> None:
        e = _egreso(reenviado=True)
        assert e.reenviado is True
