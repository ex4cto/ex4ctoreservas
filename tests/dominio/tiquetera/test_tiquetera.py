from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.tiquetera.errores import FotoReferenciaVacia, TiqueteraYaProcesada
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos


def _tiquetera(**kwargs: object) -> Tiquetera:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "venta_id": uuid.uuid4(),
        "foto_referencia": "foto/ruta.jpg",
    }
    defaults.update(kwargs)
    return Tiquetera(**defaults)  # type: ignore[arg-type]


def _datos() -> DatosExtraidos:
    return DatosExtraidos(confianza=Decimal("0.95"))


class TestTiquetera:
    def test_creacion_valida(self) -> None:
        tid = uuid.uuid4()
        vid = uuid.uuid4()
        t = Tiquetera(id=tid, venta_id=vid, foto_referencia="ruta/foto.jpg")
        assert t.id == tid
        assert t.venta_id == vid
        assert t.foto_referencia == "ruta/foto.jpg"

    def test_no_procesada_por_defecto(self) -> None:
        t = _tiquetera()
        assert t.procesada is False

    def test_sin_datos_extraidos_por_defecto(self) -> None:
        t = _tiquetera()
        assert t.datos_extraidos is None

    def test_foto_referencia_vacia_levanta_error(self) -> None:
        with pytest.raises(FotoReferenciaVacia):
            _tiquetera(foto_referencia="   ")

    def test_marcar_procesada_establece_datos(self) -> None:
        t = _tiquetera()
        datos = _datos()
        t.marcar_procesada(datos)
        assert t.procesada is True
        assert t.datos_extraidos == datos

    def test_marcar_procesada_segunda_vez_levanta_error(self) -> None:
        t = _tiquetera()
        t.marcar_procesada(_datos())
        with pytest.raises(TiqueteraYaProcesada):
            t.marcar_procesada(_datos())

    def test_identidad_por_id(self) -> None:
        tid = uuid.uuid4()
        a = Tiquetera(id=tid, venta_id=uuid.uuid4(), foto_referencia="foto.jpg")
        b = Tiquetera(id=tid, venta_id=uuid.uuid4(), foto_referencia="otra.jpg")
        assert a == b
        assert hash(a) == hash(b)

    def test_tiquetera_con_numero_fisico(self) -> None:
        t = _tiquetera(numero_fisico=42)
        assert t.numero_fisico == 42

    def test_tiquetera_sin_numero_fisico_es_none(self) -> None:
        t = _tiquetera()
        assert t.numero_fisico is None

    def test_numero_ticket_es_none_antes_de_persistir(self) -> None:
        t = _tiquetera()
        assert t.numero_ticket is None
