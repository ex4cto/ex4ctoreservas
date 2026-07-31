"""Tests for the Factura entity — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid

from garay.dominio.comun.dinero import Dinero
from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura


def _make_factura(*, id: uuid.UUID | None = None) -> Factura:
    return Factura(
        id=id or uuid.uuid4(),
        numero="GT-20260731-A3F7B2",
        venta_id=uuid.uuid4(),
        cliente_email="juan@example.com",
        monto_total=Dinero("500000"),
        fecha_emision=datetime.date(2026, 7, 31),
        html_contenido="<html></html>",
    )


def test_construccion_valores_por_defecto() -> None:
    factura = _make_factura()

    assert factura.cliente_nombre is None
    assert factura.abono is None
    assert factura.estado_envio is EstadoEnvioFactura.PENDIENTE


def test_igualdad_por_id() -> None:
    id_comun = uuid.uuid4()
    a = _make_factura(id=id_comun)
    b = _make_factura(id=id_comun)

    assert a == b
    assert hash(a) == hash(b)


def test_distinto_id_no_es_igual() -> None:
    a = _make_factura()
    b = _make_factura()

    assert a != b


def test_factura_no_es_igual_a_otro_tipo() -> None:
    factura = _make_factura()

    assert factura != "no-soy-una-factura"
