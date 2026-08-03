"""Unit tests for cmd_mis_ventas handler and _contexto_a_comando id-capture."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.infraestructura.telegram.handlers import _contexto_a_comando, cmd_mis_ventas


def _make_update(user_id: int = 123) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    return update


def _make_context(**bot_data_overrides: object) -> MagicMock:
    ctx = MagicMock()
    base: dict[str, object] = {}
    base.update(bot_data_overrides)
    ctx.bot_data = base
    return ctx


@pytest.mark.asyncio
async def test_cmd_mis_ventas_sin_repos() -> None:
    """Missing repos → reply error message, return early."""
    update = _make_update()
    # freelancer_repo present but venta_repo and comision_registrada_repo missing
    freelancer_repo = MagicMock()
    freelancer_mock = MagicMock()
    freelancer_mock.nombre = "Carlos"
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer_mock
    context = _make_context(freelancer_repo=freelancer_repo)

    await cmd_mis_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "Error" in call_args or "error" in call_args


@pytest.mark.asyncio
async def test_cmd_mis_ventas_sin_ventas() -> None:
    """Empty ventas list → message mentions 0 ventas."""
    update = _make_update()

    freelancer_repo = MagicMock()
    freelancer_mock = MagicMock()
    freelancer_mock.nombre = "Carlos"
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer_mock

    venta_repo = MagicMock()
    venta_repo.listar_por_freelancer_y_periodo.return_value = []

    comision_repo = MagicMock()
    comision_repo.listar_por_venta_ids.return_value = []

    context = _make_context(
        freelancer_repo=freelancer_repo,
        venta_repo=venta_repo,
        comision_registrada_repo=comision_repo,
    )

    await cmd_mis_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "0" in msg


# ─── _contexto_a_comando id-capture (Phase 7) ────────────────────────────────

_REGISTRANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_COUNTERPART_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_SRV_UUID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _make_full_context(
    *,
    rol_registrante: str,
    vendedor_id: uuid.UUID | None = None,
    cerrador_id: uuid.UUID | None = None,
    vendedor_nombre: str | None = None,
    cerrador_nombre: str | None = None,
) -> ContextoVenta:
    """Build a ContextoVenta that passes all guards in _contexto_a_comando."""
    return ContextoVenta(
        rol_registrante=rol_registrante,
        valor=Decimal("500000"),
        neto=Decimal("200000"),
        tipo_cliente=TipoCliente.EXTERNO,
        destinos_numeros=[1],
        fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
        cliente_nombre="Test Cliente",
        vendedor_id=vendedor_id,
        cerrador_id=cerrador_id,
        vendedor_nombre=vendedor_nombre,
        cerrador_nombre=cerrador_nombre,
    )


def _make_cmd_context(registrant_id: uuid.UUID = _REGISTRANT_ID) -> MagicMock:
    """Build a context mock with all repos needed by _contexto_a_comando."""
    freelancer = MagicMock()
    freelancer.id = registrant_id
    freelancer.nombre = "Ana"

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer

    srv_mock = MagicMock()
    srv_mock.numero = 1
    srv_mock.id = _SRV_UUID

    servicio_repo = MagicMock()
    servicio_repo.listar.return_value = [srv_mock]

    cliente_repo = MagicMock()
    cliente_repo.guardar.return_value = None

    context = MagicMock()
    context.bot_data = {
        "freelancer_repo": freelancer_repo,
        "servicio_repo": servicio_repo,
        "cliente_repo": cliente_repo,
    }
    return context


def _make_cmd_update(user_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.callback_query = None
    update.message = None
    return update


class TestContextoAComandoIds:
    """Phase 7 — _contexto_a_comando captures vendedor_id / cerrador_id per rol."""

    def test_ambos_sets_both_ids_to_registrant(self) -> None:
        """rol='ambos': both vendedor_id and cerrador_id == registrant freelancer.id."""
        ctx = _make_full_context(rol_registrante="ambos")
        update = _make_cmd_update()
        context = _make_cmd_context()

        cmd = _contexto_a_comando(update, context, ctx)

        assert cmd is not None
        assert cmd.participantes.vendedor_id == _REGISTRANT_ID
        assert cmd.participantes.cerrador_id == _REGISTRANT_ID

    def test_vendedor_sets_vendedor_id_registrant_cerrador_id_from_ctx(self) -> None:
        """rol='vendedor': vendedor_id == registrant, cerrador_id from ctx.cerrador_id."""
        ctx = _make_full_context(
            rol_registrante="vendedor",
            cerrador_id=_COUNTERPART_ID,
            cerrador_nombre="Luis",
        )
        update = _make_cmd_update()
        context = _make_cmd_context()

        cmd = _contexto_a_comando(update, context, ctx)

        assert cmd is not None
        assert cmd.participantes.vendedor_id == _REGISTRANT_ID
        assert cmd.participantes.cerrador_id == _COUNTERPART_ID

    def test_cerrador_sets_cerrador_id_registrant_vendedor_id_from_ctx(self) -> None:
        """rol='cerrador': cerrador_id == registrant, vendedor_id from ctx.vendedor_id."""
        ctx = _make_full_context(
            rol_registrante="cerrador",
            vendedor_id=_COUNTERPART_ID,
            vendedor_nombre="Luis",
        )
        update = _make_cmd_update()
        context = _make_cmd_context()

        cmd = _contexto_a_comando(update, context, ctx)

        assert cmd is not None
        assert cmd.participantes.cerrador_id == _REGISTRANT_ID
        assert cmd.participantes.vendedor_id == _COUNTERPART_ID


