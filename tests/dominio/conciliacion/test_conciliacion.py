from __future__ import annotations

import uuid

from garay.dominio.conciliacion.entidades import Conciliacion
from garay.dominio.conciliacion.tipos import EstadoConciliacion


def _conciliacion(**kwargs: object) -> Conciliacion:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "ingreso_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return Conciliacion(**defaults)  # type: ignore[arg-type]


class TestConciliacion:
    def test_creacion_valida(self) -> None:
        cid = uuid.uuid4()
        iid = uuid.uuid4()
        c = Conciliacion(id=cid, ingreso_id=iid)
        assert c.id == cid
        assert c.ingreso_id == iid

    def test_estado_pendiente_por_defecto(self) -> None:
        c = _conciliacion()
        assert c.estado == EstadoConciliacion.PENDIENTE

    def test_sin_venta_id_es_valido(self) -> None:
        c = _conciliacion()
        assert c.venta_id is None

    def test_identidad_por_id(self) -> None:
        cid = uuid.uuid4()
        a = _conciliacion(id=cid, ingreso_id=uuid.uuid4())
        b = _conciliacion(id=cid, ingreso_id=uuid.uuid4())
        assert a == b
        assert hash(a) == hash(b)
