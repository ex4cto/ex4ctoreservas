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


class TestParticipantesFreelancerIds:
    """Slice B — vendedor_id / cerrador_id nullable UUID fields."""

    def test_participantes_sin_ids_defaults_a_none(self) -> None:
        """Construction without ids keeps both fields None."""
        p = Participantes(vendedor_nombre="Ana", cerrador_nombre="Luis")
        assert p.vendedor_id is None
        assert p.cerrador_id is None

    def test_participantes_con_vendedor_id(self) -> None:
        """vendedor_id can be set explicitly."""
        f_id = uuid.uuid4()
        p = Participantes(vendedor_nombre="Ana", vendedor_id=f_id)
        assert p.vendedor_id == f_id
        assert p.cerrador_id is None

    def test_participantes_con_cerrador_id(self) -> None:
        """cerrador_id can be set explicitly."""
        f_id = uuid.uuid4()
        p = Participantes(cerrador_nombre="Luis", cerrador_id=f_id)
        assert p.cerrador_id == f_id
        assert p.vendedor_id is None

    def test_participantes_con_ambos_ids(self) -> None:
        """Both ids can be set simultaneously and are preserved in equality."""
        v_id = uuid.uuid4()
        c_id = uuid.uuid4()
        p1 = Participantes(vendedor_id=v_id, cerrador_id=c_id)
        p2 = Participantes(vendedor_id=v_id, cerrador_id=c_id)
        assert p1.vendedor_id == v_id
        assert p1.cerrador_id == c_id
        assert p1 == p2

    def test_participantes_name_only_construction_still_works(self) -> None:
        """Existing name-only construction is unbroken by the new id fields."""
        p = Participantes(vendedor_nombre="Maria", cerrador_nombre="Pedro")
        assert p.vendedor_nombre == "Maria"
        assert p.cerrador_nombre == "Pedro"
        assert p.vendedor_id is None
        assert p.cerrador_id is None
