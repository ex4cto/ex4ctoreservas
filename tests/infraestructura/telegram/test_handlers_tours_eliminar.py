"""Unit tests for /eliminar_tour conversation handler."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.telegram.handlers_tours import (
    ELT_CONFIRMA,
    ELT_FAMILIA,
    ELT_TOUR,
    cmd_eliminar_tour,
    handle_elt_confirma,
    handle_elt_familia,
    handle_elt_tour,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _servicio(
    nombre: str = "City Tour",
    categoria: str = "Cartagena",
    activo: bool = True,
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre=nombre,
        categoria=categoria,
        activo=activo,
        precio_neto_adulto=Decimal("30000"),
        precio_neto_nino=None,
    )


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=123)
    update.effective_message = AsyncMock()
    if text is not None:
        update.effective_message.text = text
    if callback_data is not None:
        query = AsyncMock()
        query.data = callback_data
        query.answer = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None
    return update


def _make_context(
    servicios: list[Servicio] | None = None,
    user_data: dict[str, object] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    repo = MagicMock()
    if servicios is not None:
        repo.listar.return_value = servicios
        repo.listar_activos.return_value = [s for s in servicios if s.activo]
    else:
        repo.listar.return_value = []
        repo.listar_activos.return_value = []
    fsm = MagicMock()
    ctx.bot_data = {"servicio_repo": repo, "fsm": fsm}
    return ctx


# ---------------------------------------------------------------------------
# Phase 6.2 — /eliminar_tour tests
# ---------------------------------------------------------------------------


class TestCmdEliminarTour:
    @pytest.mark.asyncio
    async def test_cmd_eliminar_tour_muestra_familias(self) -> None:
        """Entry point shows families (all tours visible, uses listar())."""
        s_active = _servicio("City Tour", "Cartagena", activo=True)
        s_inactive = _servicio("Old Tour", "Cartagena", activo=False)
        update = _make_update()
        ctx = _make_context(servicios=[s_active, s_inactive])

        result = await cmd_eliminar_tour.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == ELT_FAMILIA
        # Must use listar() (ALL tours) for navigation
        ctx.bot_data["servicio_repo"].listar.assert_called_once()


class TestHandleEltFamilia:
    @pytest.mark.asyncio
    async def test_seleccionar_familia_muestra_tours(self) -> None:
        """Family selection returns tour list keyboard."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data="elt_familia:Cartagena")
        ctx = _make_context(
            servicios=[s1],
            user_data={"elt_servicios": [s1]},
        )

        result = await handle_elt_familia(update, ctx)

        assert result == ELT_TOUR


class TestHandleEltTour:
    @pytest.mark.asyncio
    async def test_seleccionar_tour_muestra_confirmacion(self) -> None:
        """Tour selection returns confirmation screen."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data=f"elt_tour:{s1.id}")
        ctx = _make_context(
            servicios=[s1],
            user_data={"elt_servicios": [s1]},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_elt_tour(update, ctx)

        assert result == ELT_CONFIRMA
        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "City Tour" in msg


class TestHandleEltConfirma:
    @pytest.mark.asyncio
    async def test_eliminar_confirmar_hace_soft_delete(self) -> None:
        """Confirm → guardar called with activo=False + fsm.refrescar_servicios()."""
        s1 = _servicio("City Tour", "Cartagena", activo=True)
        update = _make_update(callback_data="elt_confirmar")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "elt_target_id": str(s1.id),
                "elt_nombre": s1.nombre,
            },
        )
        repo = ctx.bot_data["servicio_repo"]
        repo.buscar_por_id.return_value = s1
        repo.listar_activos.return_value = []

        result = await handle_elt_confirma(update, ctx)

        assert result == ConversationHandler.END
        repo.guardar.assert_called_once()
        # The saved entity must have activo=False
        saved = repo.guardar.call_args[0][0]
        assert saved.activo is False
        # FSM must be refreshed with listar_activos() result
        ctx.bot_data["fsm"].refrescar_servicios.assert_called_once()

    @pytest.mark.asyncio
    async def test_eliminar_cancelar_no_modifica(self) -> None:
        """Cancel → guardar NOT called."""
        s1 = _servicio("City Tour", "Cartagena", activo=True)
        update = _make_update(callback_data="elt_cancelar")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "elt_target_id": str(s1.id),
                "elt_nombre": s1.nombre,
            },
        )

        result = await handle_elt_confirma(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()
        ctx.bot_data["fsm"].refrescar_servicios.assert_not_called()


class TestRefrescoConListarActivos:
    @pytest.mark.asyncio
    async def test_desactivar_tour_refresco_usa_listar_activos(self) -> None:
        """After soft-delete, FSM refresh is called with listar_activos() result (not listar())."""
        s1 = _servicio("Active Tour", activo=True)
        s2 = _servicio("To Delete", activo=True)
        update = _make_update(callback_data="elt_confirmar")
        ctx = _make_context(
            servicios=[s1, s2],
            user_data={
                "elt_target_id": str(s2.id),
                "elt_nombre": s2.nombre,
            },
        )
        repo = ctx.bot_data["servicio_repo"]
        repo.buscar_por_id.return_value = s2
        # After soft-delete, only s1 is active
        repo.listar_activos.return_value = [s1]

        await handle_elt_confirma(update, ctx)

        repo.listar_activos.assert_called()
        # listar() should NOT be used for the refresh
        # (listar_activos gives the fresh vendible catalog)
        call_args = ctx.bot_data["fsm"].refrescar_servicios.call_args
        assert call_args is not None
        passed_list = call_args[0][0]
        # Should be a list of 5-tuples mapping s1 only
        assert len(passed_list) == 1
