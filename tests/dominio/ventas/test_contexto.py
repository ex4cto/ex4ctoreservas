"""Tests for ContextoVenta — Slice B additions."""

from __future__ import annotations

import uuid

from garay.dominio.ventas.contexto import ContextoVenta


class TestContextoVentaFreelancerIds:
    """Slice B — vendedor_id / cerrador_id nullable UUID fields on ContextoVenta."""

    def test_contexto_defaults_vendedor_id_a_none(self) -> None:
        """ContextoVenta() initializes vendedor_id to None."""
        ctx = ContextoVenta()
        assert ctx.vendedor_id is None

    def test_contexto_defaults_cerrador_id_a_none(self) -> None:
        """ContextoVenta() initializes cerrador_id to None."""
        ctx = ContextoVenta()
        assert ctx.cerrador_id is None

    def test_contexto_vendedor_id_es_mutable(self) -> None:
        """vendedor_id can be assigned (ContextoVenta is a mutable dataclass)."""
        ctx = ContextoVenta()
        f_id = uuid.uuid4()
        ctx.vendedor_id = f_id
        assert ctx.vendedor_id == f_id

    def test_contexto_cerrador_id_es_mutable(self) -> None:
        """cerrador_id can be assigned."""
        ctx = ContextoVenta()
        f_id = uuid.uuid4()
        ctx.cerrador_id = f_id
        assert ctx.cerrador_id == f_id

    def test_contexto_ids_independientes_de_nombres(self) -> None:
        """Id fields are independent from name fields — both can be set simultaneously."""
        ctx = ContextoVenta()
        v_id = uuid.uuid4()
        c_id = uuid.uuid4()
        ctx.vendedor_nombre = "Ana"
        ctx.cerrador_nombre = "Luis"
        ctx.vendedor_id = v_id
        ctx.cerrador_id = c_id
        assert ctx.vendedor_nombre == "Ana"
        assert ctx.cerrador_nombre == "Luis"
        assert ctx.vendedor_id == v_id
        assert ctx.cerrador_id == c_id
