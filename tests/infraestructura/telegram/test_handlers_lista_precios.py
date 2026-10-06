"""T2.18 RED — Unit tests for cmd_lista_precios handler.

Verifies: filtering, fmt_cop formatting, grouping by categoria, bot_data access.
No Playwright, no DB, no image generation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.servicios.entidades import Servicio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _servicio(
    numero: int = 1,
    nombre: str = "City Tour",
    categoria: str = "Cartagena",
    activo: bool = True,
    precio_sugerido_adulto: Decimal | None = Decimal("150000"),
    precio_neto_adulto: Decimal | None = Decimal("100000"),
    precio_neto_nino: Decimal | None = None,
    permite_ninos: bool = True,
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=numero,
        nombre=nombre,
        categoria=categoria,
        activo=activo,
        precio_neto_adulto=precio_neto_adulto,
        precio_neto_nino=precio_neto_nino,
        permite_ninos=permite_ninos,
        precio_sugerido_adulto=precio_sugerido_adulto,
    )


def _make_context(servicios: list[Servicio]) -> MagicMock:
    ctx = MagicMock()
    repo = MagicMock()
    repo.listar_activos.return_value = servicios
    ctx.bot_data = {"servicio_repo": repo}
    return ctx


def _make_update() -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=42)
    update.effective_message = AsyncMock()
    return update


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCmdListaPrecios:
    """Inner-logic tests — use __wrapped__ to bypass @requiere_rol guard."""

    @pytest.mark.asyncio
    async def test_lista_solo_activos_con_sugerido(self) -> None:
        """Only active services with precio_sugerido_adulto set appear in reply."""
        from garay.infraestructura.telegram.handlers_lista_precios import (
            cmd_lista_precios,
        )

        s_ok1 = _servicio(numero=1, nombre="Tour A", precio_sugerido_adulto=Decimal("150000"))
        s_ok2 = _servicio(numero=2, nombre="Tour B", precio_sugerido_adulto=Decimal("200000"))
        s_sin_sugerido = _servicio(numero=3, nombre="Tour C", precio_sugerido_adulto=None)

        ctx = _make_context([s_ok1, s_ok2, s_sin_sugerido])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        update.effective_message.reply_text.assert_called_once()
        text = update.effective_message.reply_text.call_args[0][0]
        assert "Tour A" in text
        assert "Tour B" in text
        assert "Tour C" not in text

    @pytest.mark.asyncio
    async def test_fmt_cop_usado_para_precio_sugerido(self) -> None:
        """precio_sugerido_adulto is formatted with fmt_cop ($150.000 not 150000.00)."""
        from garay.infraestructura.telegram.handlers_lista_precios import (
            cmd_lista_precios,
        )

        s = _servicio(precio_sugerido_adulto=Decimal("150000"))
        ctx = _make_context([s])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        text = update.effective_message.reply_text.call_args[0][0]
        assert "$150.000" in text
        assert "150000.00" not in text

    @pytest.mark.asyncio
    async def test_agrupa_por_categoria(self) -> None:
        """Services are grouped by categoria — each category header appears once."""
        from garay.infraestructura.telegram.handlers_lista_precios import (
            cmd_lista_precios,
        )

        s1 = _servicio(numero=1, nombre="City Tour", categoria="Cartagena")
        s2 = _servicio(numero=2, nombre="Playa Tour", categoria="Playa")
        s3 = _servicio(numero=3, nombre="Ciudad Tour 2", categoria="Cartagena")

        ctx = _make_context([s1, s2, s3])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        text = update.effective_message.reply_text.call_args[0][0]
        # Both categories must appear in the text
        assert "Cartagena" in text
        assert "Playa" in text
        # Both tour names must appear
        assert "City Tour" in text
        assert "Ciudad Tour 2" in text

    @pytest.mark.asyncio
    async def test_vacio_cuando_no_hay_servicios_elegibles(self) -> None:
        """Reply is sent even when no services pass the filter (empty state message)."""
        from garay.infraestructura.telegram.handlers_lista_precios import (
            cmd_lista_precios,
        )

        ctx = _make_context([])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        # Handler must reply even on empty
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_lee_servicio_repo_de_bot_data(self) -> None:
        """Handler reads servicio_repo from context.bot_data."""
        from garay.infraestructura.telegram.handlers_lista_precios import (
            cmd_lista_precios,
        )

        s = _servicio()
        ctx = _make_context([s])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        ctx.bot_data["servicio_repo"].listar_activos.assert_called_once()

    @pytest.mark.asyncio
    async def test_precio_sugerido_none_excluido_del_output(self) -> None:
        """Services with precio_sugerido_adulto=None are excluded (no dash shown)."""
        from garay.infraestructura.telegram.handlers_lista_precios import (
            cmd_lista_precios,
        )

        s_none = _servicio(nombre="Tour Excluido", precio_sugerido_adulto=None)
        ctx = _make_context([s_none])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        text = update.effective_message.reply_text.call_args[0][0]
        assert "Tour Excluido" not in text

    @pytest.mark.asyncio
    async def test_excluye_tour_sin_neto_adulto(self) -> None:
        """Tour with sugerido set but neto_adulto=None is excluded from the listing."""
        from garay.infraestructura.telegram.handlers_lista_precios import cmd_lista_precios

        s = _servicio(nombre="Tour Sin Neto", precio_neto_adulto=None)
        ctx = _make_context([s])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        text = update.effective_message.reply_text.call_args[0][0]
        assert "Tour Sin Neto" not in text

    @pytest.mark.asyncio
    async def test_muestra_nota_nino_adulto(self) -> None:
        """Shows 'niño = adulto' for tours with permite_ninos=True and precio_neto_nino=None."""
        from garay.infraestructura.telegram.handlers_lista_precios import cmd_lista_precios

        s = _servicio(nombre="Tour Con Nino", permite_ninos=True, precio_neto_nino=None)
        ctx = _make_context([s])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        text = update.effective_message.reply_text.call_args[0][0]
        assert "niño = adulto" in text

    @pytest.mark.asyncio
    async def test_no_muestra_nota_nino_cuando_no_aplica(self) -> None:
        """No 'niño = adulto' note when permite_ninos=False or precio_neto_nino is set."""
        from garay.infraestructura.telegram.handlers_lista_precios import cmd_lista_precios

        s = _servicio(nombre="Tour Sin Nino", permite_ninos=False)
        ctx = _make_context([s])
        update = _make_update()

        await cmd_lista_precios.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        text = update.effective_message.reply_text.call_args[0][0]
        assert "niño = adulto" not in text


# ---------------------------------------------------------------------------
# Spec: lista-precios-runtime-guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lista_precios_bloquea_usuario_no_registrado() -> None:
    """Unregistered user receives the deny message (via @requiere_rol guard)."""
    from garay.infraestructura.telegram.handlers_lista_precios import cmd_lista_precios

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = None  # user not registered

    ctx = MagicMock()
    ctx.bot_data = {
        "freelancer_repo": freelancer_repo,
        "servicio_repo": MagicMock(),
    }

    update = _make_update()

    # Call the decorated handler (not __wrapped__) to exercise the guard
    await cmd_lista_precios(update, ctx)

    update.effective_message.reply_text.assert_called_once()
    msg: str = update.effective_message.reply_text.call_args[0][0]
    assert "freelancer" in msg.lower()


@pytest.mark.asyncio
async def test_lista_precios_permite_usuario_registrado() -> None:
    """Registered user (freelancer_repo returns a freelancer) receives the price list."""
    from garay.infraestructura.telegram.handlers_lista_precios import cmd_lista_precios

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = MagicMock()  # registered

    servicio_repo = MagicMock()
    servicio_repo.listar_activos.return_value = [_servicio()]

    ctx = MagicMock()
    ctx.bot_data = {
        "freelancer_repo": freelancer_repo,
        "servicio_repo": servicio_repo,
    }

    update = _make_update()

    await cmd_lista_precios(update, ctx)

    # The decorated handler should call the inner function and return the price list
    update.effective_message.reply_text.assert_called_once()
