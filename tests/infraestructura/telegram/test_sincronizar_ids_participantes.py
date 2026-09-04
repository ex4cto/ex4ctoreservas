"""Regression: participant ids must reach ctx so the factura BCC works for all roles."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from garay.dominio.ventas.contexto import ContextoVenta
from garay.infraestructura.telegram.handlers import _sincronizar_ids_participantes


def _cmd(vendedor_id: uuid.UUID | None, cerrador_id: uuid.UUID | None) -> MagicMock:
    cmd = MagicMock()
    cmd.participantes.vendedor_id = vendedor_id
    cmd.participantes.cerrador_id = cerrador_id
    return cmd


def test_ambos_sincroniza_cerrador_id() -> None:
    # 'ambos': the FSM left ctx.cerrador_id None; the command resolved it.
    yo = uuid.uuid4()
    ctx = ContextoVenta()
    assert ctx.cerrador_id is None
    _sincronizar_ids_participantes(ctx, _cmd(yo, yo))
    assert ctx.vendedor_id == yo
    assert ctx.cerrador_id == yo


def test_solo_cerrador_sincroniza_cerrador_id() -> None:
    vendedor = uuid.uuid4()
    cerrador = uuid.uuid4()
    ctx = ContextoVenta()
    _sincronizar_ids_participantes(ctx, _cmd(vendedor, cerrador))
    assert ctx.cerrador_id == cerrador


def test_solo_vendedor_preserva_cerrador_del_picker() -> None:
    vendedor = uuid.uuid4()
    cerrador = uuid.uuid4()
    ctx = ContextoVenta()
    ctx.cerrador_id = cerrador  # picker ya lo había puesto
    _sincronizar_ids_participantes(ctx, _cmd(vendedor, cerrador))
    assert ctx.cerrador_id == cerrador
