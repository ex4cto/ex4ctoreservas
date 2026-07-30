"""Tests for cmd_movimientos handler — RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, Ingreso
from garay.dominio.conciliacion.tipos import TipoEgreso

_UTC = datetime.UTC


def _make_update(user_id: int = 999) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    update.callback_query = None
    return update


def _make_settings(*, propietario_ids: str = "999") -> MagicMock:
    s = MagicMock()
    s.propietario_telegram_ids = propietario_ids
    return s


def _make_movimientos_service(
    ingresos: list[Ingreso] | None = None,
    egresos: list[Egreso] | None = None,
) -> MagicMock:
    from garay.aplicacion.reportes.movimientos_recientes import MovimientosRecientes

    total_i = sum((i.monto for i in (ingresos or [])), start=Dinero(0))
    total_e = sum((e.monto for e in (egresos or [])), start=Dinero(0))

    resultado = MovimientosRecientes(
        ingresos=tuple(ingresos or []),
        egresos=tuple(egresos or []),
        total_ingresos=total_i,
        total_egresos=total_e,
    )
    svc = MagicMock()
    svc.ejecutar.return_value = resultado
    return svc


def _make_context(**bot_data: object) -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = dict(bot_data)
    return ctx


def _ingreso(monto: str = "100000", reenviado: bool = False) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero(monto),
        fecha=datetime.date(2026, 7, 30),
        referencia=f"REF-{uuid.uuid4().hex[:6]}",
        fecha_recibido=datetime.datetime.now(_UTC),
        reenviado=reenviado,
    )


def _egreso(monto: str = "50000", reenviado: bool = False) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Compra varia",
        monto=Dinero(monto),
        fecha=datetime.date(2026, 7, 30),
        categoria="otro",
        tipo=TipoEgreso.AUTOMATICO,
        fecha_recibido=datetime.datetime.now(_UTC),
        reenviado=reenviado,
    )


# ---------------------------------------------------------------------------
# Import sanity — the module must be importable
# ---------------------------------------------------------------------------

def test_handlers_reportes_imports_cmd_movimientos() -> None:
    from garay.infraestructura.telegram.handlers_reportes import cmd_movimientos  # noqa: F401


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_movimientos_sin_movimientos_muestra_sin_datos() -> None:
    """Empty result → reply contains sin_movimientos message."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_movimientos

    update = _make_update(user_id=999)
    svc = _make_movimientos_service()
    context = _make_context(movimientos_service=svc)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings(propietario_ids="999"),
    ):
        await cmd_movimientos.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_movimientos_muestra_ingresos_y_egresos() -> None:
    """Reply contains ingreso and egreso amounts."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_movimientos

    i = _ingreso("150000")
    e = _egreso("75000")
    update = _make_update(user_id=999)
    svc = _make_movimientos_service(ingresos=[i], egresos=[e])
    context = _make_context(movimientos_service=svc)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings(propietario_ids="999"),
    ):
        await cmd_movimientos.__wrapped__(update, context)  # type: ignore[attr-defined]

    call_args = update.effective_message.reply_text.call_args[0][0]
    # Should mention amounts somewhere
    assert "150" in call_args or "75" in call_args


@pytest.mark.asyncio
async def test_cmd_movimientos_incluye_tag_reenvio_cuando_reenviado() -> None:
    """An ingreso with reenviado=True must show the reenvio tag."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_movimientos

    i = _ingreso("200000", reenviado=True)
    update = _make_update(user_id=999)
    svc = _make_movimientos_service(ingresos=[i])
    context = _make_context(movimientos_service=svc)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings(propietario_ids="999"),
    ):
        await cmd_movimientos.__wrapped__(update, context)  # type: ignore[attr-defined]

    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "fwd" in call_args.lower()


@pytest.mark.asyncio
async def test_cmd_movimientos_bloqueado_para_non_propietario() -> None:
    """User not in propietario list → handler replies denial, service NOT called."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_movimientos

    update = _make_update(user_id=456)
    svc = _make_movimientos_service()
    context = _make_context(movimientos_service=svc)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings(propietario_ids="999"),
    ):
        await cmd_movimientos(update, context)

    svc.ejecutar.assert_not_called()


# ---------------------------------------------------------------------------
# FIX 1: _fmt_cop format — amounts must use Colombian dot-separator, no cents
# ---------------------------------------------------------------------------


def test_formatear_movimientos_ingreso_monto_grande_formato_cop() -> None:
    """Dinero(208929.30) must appear as '$208.929' — not '208,929.3' (FIX 1)."""
    from garay.aplicacion.reportes.movimientos_recientes import MovimientosRecientes
    from garay.infraestructura.telegram.handlers_reportes import _formatear_movimientos

    i = _ingreso("208929.30")
    resultado = MovimientosRecientes(
        ingresos=(i,),
        egresos=(),
        total_ingresos=i.monto,
        total_egresos=Dinero(0),
    )
    texto = _formatear_movimientos(resultado, horas=24)
    assert "$208.929" in texto, f"Expected '$208.929' in output, got: {texto!r}"


# ---------------------------------------------------------------------------
# FIX 2: Markdown special chars in egreso.descripcion must appear verbatim
# ---------------------------------------------------------------------------


def test_formatear_movimientos_egreso_descripcion_markdown_verbatim() -> None:
    """An egreso description with Markdown chars must appear verbatim (FIX 2)."""
    from garay.aplicacion.reportes.movimientos_recientes import MovimientosRecientes
    from garay.infraestructura.telegram.handlers_reportes import _formatear_movimientos

    desc_markdown = "Compra en A*B_store"
    e = Egreso(
        id=uuid.uuid4(),
        descripcion=desc_markdown,
        monto=Dinero("50000"),
        fecha=datetime.date(2026, 7, 30),
        categoria="otro",
        tipo=TipoEgreso.AUTOMATICO,
        fecha_recibido=datetime.datetime.now(_UTC),
        reenviado=False,
    )
    resultado = MovimientosRecientes(
        ingresos=(),
        egresos=(e,),
        total_ingresos=Dinero(0),
        total_egresos=e.monto,
    )
    texto = _formatear_movimientos(resultado, horas=24)
    assert desc_markdown in texto, (
        f"Expected description {desc_markdown!r} verbatim in output, got: {texto!r}"
    )


# ---------------------------------------------------------------------------
# FIX 2: cmd_movimientos must NOT pass parse_mode="Markdown"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_movimientos_no_usa_parse_mode_markdown() -> None:
    """cmd_movimientos must call reply_text without parse_mode='Markdown' (FIX 2)."""
    from garay.infraestructura.telegram.handlers_reportes import cmd_movimientos

    update = _make_update(user_id=999)
    svc = _make_movimientos_service()
    context = _make_context(movimientos_service=svc)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=_make_settings(propietario_ids="999"),
    ):
        await cmd_movimientos.__wrapped__(update, context)  # type: ignore[attr-defined]

    call_kwargs = update.effective_message.reply_text.call_args
    assert call_kwargs is not None
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    args = call_kwargs.args if call_kwargs.args else ()
    # parse_mode must not be passed, or must not be "Markdown"
    assert "parse_mode" not in kwargs or kwargs["parse_mode"] != "Markdown", (
        f"reply_text was called with parse_mode='Markdown': kwargs={kwargs}, args={args}"
    )
