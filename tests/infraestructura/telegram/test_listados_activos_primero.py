"""Tests for #3: active items listed before inactive (freelancers and tours)."""

from __future__ import annotations

import uuid
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.servicios.entidades import Servicio


def _srv(nombre: str, activo: bool, familia: str = "BARU") -> MagicMock:
    s = MagicMock()
    s.nombre = nombre
    s.activo = activo
    s.categoria = familia
    s.id = uuid.uuid4()
    return s


def _fl(nombre: str, activo: bool, tg: int | None) -> MagicMock:
    f = MagicMock()
    f.nombre = nombre
    f.activo = activo
    f.telegram_user_id = tg
    f.es_admin = False
    return f


def test_teclado_tours_activos_primero() -> None:
    from garay.infraestructura.telegram.handlers_tours import _teclado_tours

    servicios = [
        _srv("Zeta", activo=False),
        _srv("Ana", activo=True),
        _srv("Mora", activo=False),
        _srv("Beto", activo=True),
    ]
    markup = _teclado_tours(cast("list[Servicio]", servicios), "BARU", "edt_tour:")
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert len(labels) == 4
    assert "[inactivo]" not in labels[0]
    assert "[inactivo]" not in labels[1]
    assert "[inactivo]" in labels[2]
    assert "[inactivo]" in labels[3]


@pytest.mark.asyncio
async def test_listar_freelancers_activos_primero(monkeypatch: pytest.MonkeyPatch) -> None:
    import garay.infraestructura.telegram.handlers_freelancers as hf

    monkeypatch.setattr(hf, "dev_telegram_ids", lambda: set())
    admin = _fl("Admin", activo=True, tg=999)
    admin.es_admin = True
    fi = _fl("Ines", activo=False, tg=2)
    fa = _fl("Ana", activo=True, tg=1)

    repo = MagicMock()
    repo.listar_todos.return_value = [fi, fa]  # inactiva primero en la "DB"
    repo.buscar_por_telegram_id.return_value = admin  # el que llama es admin

    ctx = MagicMock()
    ctx.bot_data = {"freelancer_repo": repo}
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 999

    await hf.cmd_listar_freelancers(update, ctx)

    msg = update.effective_message.reply_text.call_args[0][0]
    assert msg.index("Ana") < msg.index("Ines")
