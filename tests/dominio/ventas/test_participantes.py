"""Tests del value object Participantes."""

from __future__ import annotations

import uuid

import pytest

from garay.dominio.ventas.valor_objetos import Participantes


class TestParticipantes:
    def test_participantes_vacios_validos(self) -> None:
        p = Participantes()
        assert p.vendedor_nombre is None
        assert p.cerrador_nombre is None
        assert p.punto_de_venta_id is None
        assert p.referido_nombre is None

    def test_participantes_es_frozen(self) -> None:
        p = Participantes(vendedor_nombre="Ana")
        with pytest.raises((AttributeError, TypeError)):
            p.vendedor_nombre = "Otra"  # type: ignore[misc]

    def test_dos_participantes_iguales(self) -> None:
        uid = uuid.uuid4()
        p1 = Participantes(vendedor_nombre="Ana", punto_de_venta_id=uid)
        p2 = Participantes(vendedor_nombre="Ana", punto_de_venta_id=uid)
        assert p1 == p2
