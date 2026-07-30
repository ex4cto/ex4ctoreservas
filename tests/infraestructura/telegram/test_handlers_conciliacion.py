"""Tests for handlers_conciliacion — cmd_conciliar, cmd_pendientes, callback_conciliar."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.dominio.conciliacion.entidades import Conciliacion, ResultadoConciliacion
from garay.dominio.conciliacion.tipos import EstadoConciliacion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update(user_id: int = 111) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    update.callback_query = None
    return update


def _make_context(**bot_data: object) -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = dict(bot_data)
    return ctx


def _make_settings(propietario_ids: str = "111") -> MagicMock:
    settings = MagicMock()
    settings.propietario_telegram_ids = propietario_ids
    return settings


def _make_conciliacion(
    *,
    estado: EstadoConciliacion = EstadoConciliacion.PENDIENTE,
    venta_id: uuid.UUID | None = None,
) -> Conciliacion:
    return Conciliacion(
        id=uuid.uuid4(),
        ingreso_id=uuid.uuid4(),
        venta_id=venta_id,
        estado=estado,
    )


# ---------------------------------------------------------------------------
# cmd_conciliar tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_conciliar_bloqueado_para_no_propietario() -> None:
    """User not in propietario list → reply sin_acceso, handler not called."""
    from garay.infraestructura.telegram.handlers_conciliacion import cmd_conciliar

    update = _make_update(user_id=999)
    ctx = _make_context()

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings("111"),
    ):
        result = await cmd_conciliar(update, ctx)

    assert result is None
    update.effective_message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_conciliar_propietario_ejecuta_servicio() -> None:
    """Propietario calls /conciliar → service.ejecutar() is called, result shown."""
    from garay.infraestructura.telegram.handlers_conciliacion import cmd_conciliar

    update = _make_update(user_id=111)
    servicio = MagicMock()
    servicio.ejecutar.return_value = ResultadoConciliacion(
        matcheados=3, sin_match=1, pendientes=2
    )
    ctx = _make_context(conciliar_service=servicio)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings("111"),
    ):
        await cmd_conciliar(update, ctx)

    servicio.ejecutar.assert_called_once()
    update.effective_message.reply_text.assert_called_once()
    texto = update.effective_message.reply_text.call_args[0][0]
    assert "3" in texto  # matcheados


# ---------------------------------------------------------------------------
# cmd_pendientes tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_pendientes_sin_pendientes_muestra_mensaje_vacio() -> None:
    """No pending conciliaciones → reply with sin_pendientes message."""
    from garay.infraestructura.telegram.handlers_conciliacion import cmd_pendientes

    update = _make_update(user_id=111)
    repo = MagicMock()
    repo.listar_pendientes.return_value = []
    ctx = _make_context(conciliacion_repo=repo)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings("111"),
    ):
        await cmd_pendientes(update, ctx)

    update.effective_message.reply_text.assert_called_once()
    texto = update.effective_message.reply_text.call_args[0][0]
    assert "pendientes" in texto.lower()


@pytest.mark.asyncio
async def test_cmd_pendientes_muestra_botones_cuando_hay_pendientes() -> None:
    """Pending conciliaciones → each one rendered with inline keyboard."""
    from garay.infraestructura.telegram.handlers_conciliacion import cmd_pendientes

    update = _make_update(user_id=111)
    concs = [_make_conciliacion(), _make_conciliacion()]
    repo = MagicMock()
    repo.listar_pendientes.return_value = concs
    ctx = _make_context(conciliacion_repo=repo)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings("111"),
    ):
        await cmd_pendientes(update, ctx)

    # reply_text called once per conciliacion
    assert update.effective_message.reply_text.call_count == 2


# ---------------------------------------------------------------------------
# callback_conciliar tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_match_actualiza_estado() -> None:
    """callback 'match' action → estado updated to MATCHEADO, guardar called."""
    from garay.infraestructura.telegram.handlers_conciliacion import callback_conciliar

    conc = _make_conciliacion(estado=EstadoConciliacion.PENDIENTE)

    repo = MagicMock()
    repo.buscar_por_id.return_value = conc

    query = AsyncMock()
    query.data = f"conc:{conc.id}:match"
    query.message = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    ctx = _make_context(conciliacion_repo=repo)

    await callback_conciliar(update, ctx)

    repo.buscar_por_id.assert_called_once_with(conc.id)
    repo.guardar.assert_called_once()
    saved_conc: Conciliacion = repo.guardar.call_args[0][0]
    assert saved_conc.estado == EstadoConciliacion.MATCHEADO


@pytest.mark.asyncio
async def test_callback_personal_actualiza_estado() -> None:
    """callback 'personal' action → estado updated to PERSONAL."""
    from garay.infraestructura.telegram.handlers_conciliacion import callback_conciliar

    conc = _make_conciliacion(estado=EstadoConciliacion.PENDIENTE)
    repo = MagicMock()
    repo.buscar_por_id.return_value = conc

    query = AsyncMock()
    query.data = f"conc:{conc.id}:personal"
    query.message = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    ctx = _make_context(conciliacion_repo=repo)

    await callback_conciliar(update, ctx)

    saved_conc: Conciliacion = repo.guardar.call_args[0][0]
    assert saved_conc.estado == EstadoConciliacion.PERSONAL


@pytest.mark.asyncio
async def test_callback_uuid_invalido_no_falla() -> None:
    """Malformed UUID in callback data → returns None without crashing."""
    from garay.infraestructura.telegram.handlers_conciliacion import callback_conciliar

    query = AsyncMock()
    query.data = "conc:NOT-A-UUID:match"
    query.message = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    repo = MagicMock()
    ctx = _make_context(conciliacion_repo=repo)

    await callback_conciliar(update, ctx)

    # The callback is acknowledged, but the malformed UUID short-circuits
    # before any repo lookup or message edit.
    query.answer.assert_awaited_once()
    repo.buscar_por_id.assert_not_called()
    query.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_callback_query_none_devuelve_none() -> None:
    """No callback_query → returns None immediately."""
    from garay.infraestructura.telegram.handlers_conciliacion import callback_conciliar

    update = MagicMock()
    update.callback_query = None
    repo = MagicMock()
    ctx = _make_context(conciliacion_repo=repo)

    await callback_conciliar(update, ctx)

    # With no callback_query the handler returns immediately, never touching
    # the repository.
    repo.buscar_por_id.assert_not_called()
    repo.guardar.assert_not_called()
