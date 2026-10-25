"""Tests for fire-and-forget catalog notification trigger points in handlers_tours.py.

Verifies that context.application.create_task(registrar_cambio(...)) is called after:
  - /nuevo_tour create success (handle_nvt_crear)
  - /editar_tour EDF_CONFIRMA success path (handle_edt_confirma)
  - /eliminar_tour (deactivate) success path (handle_elt_confirma)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.telegram.handlers_tours import (
    configurar_notificaciones_catalogo,
    handle_edt_confirma,
    handle_elt_confirma,
    handle_nvt_crear,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _servicio(
    nombre: str = "City Tour",
    categoria: str = "PLAYERO",
    activo: bool = True,
    neto_adulto: Decimal | None = Decimal("30000"),
    neto_nino: Decimal | None = None,
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre=nombre,
        categoria=categoria,
        activo=activo,
        precio_neto_adulto=neto_adulto,
        precio_neto_nino=neto_nino,
        precio_sugerido_adulto=Decimal("50000"),
    )

def _make_update(callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=42, full_name="Test Admin")
    update.effective_message = AsyncMock()
    if callback_data is not None:
        query = AsyncMock()
        query.data = callback_data
        query.answer = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None
    return update

def _mock_notif_svc() -> MagicMock:
    """Build a mock NotificarCambioCatalogoServicio."""
    from garay.aplicacion.servicios.notificaciones_catalogo import NotificarCambioCatalogoServicio
    svc = MagicMock(spec=NotificarCambioCatalogoServicio)
    svc.registrar_cambio = AsyncMock()
    svc._repo = MagicMock()
    return svc

def _make_context_nvt(
    user_data: dict[str, object] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    repo = MagicMock()
    repo.siguiente_numero.return_value = 10
    repo.guardar.return_value = None
    fsm = MagicMock()
    ctx.bot_data = {
        "servicio_repo": repo,
        "fsm": fsm,
    }
    return ctx

def _make_context_edt(
    servicios: list[Servicio] | None = None,
    user_data: dict[str, object] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    repo = MagicMock()
    if servicios:
        repo.listar.return_value = servicios
        repo.listar_activos.return_value = [s for s in servicios if s.activo]
        repo.buscar_por_id.return_value = servicios[0]
    else:
        repo.listar.return_value = []
        repo.listar_activos.return_value = []
        repo.buscar_por_id.return_value = None
    repo.guardar.return_value = None
    fsm = MagicMock()
    ctx.bot_data = {
        "servicio_repo": repo,
        "fsm": fsm,
    }
    return ctx

# ---------------------------------------------------------------------------
# T2.23: Trigger tests
# ---------------------------------------------------------------------------

class TestNvtCrearTrigger:
    """After /nuevo_tour create success, application.create_task(registrar_cambio(...)) fires."""

    @pytest.mark.asyncio
    async def test_nvt_crear_llama_create_task(self) -> None:
        """handle_nvt_crear calls application.create_task after saving the new tour."""
        notif_svc = _mock_notif_svc()
        configurar_notificaciones_catalogo(notif_svc)

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context_nvt(
            user_data={
                "nvt_familia": "PLAYERO",
                "nvt_nombre": "Nuevo Tour",
                "nvt_neto_adulto": Decimal("30000"),
                "nvt_neto_nino": None,
                "nvt_horarios": [],
            },
        )

        await handle_nvt_crear(update, ctx)

        ctx.application.create_task.assert_called_once()

class TestEdtConfirmaTrigger:
    """After EDF_CONFIRMA success, application.create_task(registrar_cambio(...)) fires."""

    @pytest.mark.asyncio
    async def test_edt_confirma_nombre_llama_create_task(self) -> None:
        """handle_edt_confirma calls application.create_task after confirming a nombre edit."""
        notif_svc = _mock_notif_svc()
        configurar_notificaciones_catalogo(notif_svc)

        s = _servicio("City Tour")
        update = _make_update(callback_data="edt_confirmar")
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "edt_target_id": str(s.id),
                "edt_campo": "nombre",
                "edt_valor": "Nuevo Nombre",
            },
        )

        await handle_edt_confirma(update, ctx)

        ctx.application.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_edt_confirma_activo_llama_create_task(self) -> None:
        """handle_edt_confirma calls application.create_task after toggling activo."""
        notif_svc = _mock_notif_svc()
        configurar_notificaciones_catalogo(notif_svc)

        s = _servicio("City Tour")
        update = _make_update(callback_data="edt_confirmar")
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "edt_target_id": str(s.id),
                "edt_campo": "activo",
                "edt_activo_nuevo": False,
            },
        )

        await handle_edt_confirma(update, ctx)

        ctx.application.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_edt_confirma_cancelar_no_llama_create_task(self) -> None:
        """handle_edt_confirma does NOT call application.create_task when action is 'cancelar'."""
        notif_svc = _mock_notif_svc()
        configurar_notificaciones_catalogo(notif_svc)

        s = _servicio("City Tour")
        update = _make_update(callback_data="edt_cancelar")
        ctx = _make_context_edt(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edt_campo": "nombre"},
        )

        await handle_edt_confirma(update, ctx)

        ctx.application.create_task.assert_not_called()

class TestEltConfirmaTrigger:
    """After deactivate success, application.create_task(registrar_cambio(...)) fires."""

    @pytest.mark.asyncio
    async def test_elt_confirma_llama_create_task(self) -> None:
        """handle_elt_confirma calls application.create_task after soft-deleting a tour."""
        notif_svc = _mock_notif_svc()
        configurar_notificaciones_catalogo(notif_svc)

        s = _servicio("Tour a Eliminar")
        update = _make_update(callback_data="elt_confirmar")
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "elt_target_id": str(s.id),
                "elt_nombre": s.nombre,
            },
        )

        await handle_elt_confirma(update, ctx)

        ctx.application.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_elt_cancelar_no_llama_create_task(self) -> None:
        """handle_elt_confirma does NOT call application.create_task when action is 'cancelar'."""
        notif_svc = _mock_notif_svc()
        configurar_notificaciones_catalogo(notif_svc)

        s = _servicio("Tour a Cancelar")
        update = _make_update(callback_data="elt_cancelar")
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "elt_target_id": str(s.id),
                "elt_nombre": s.nombre,
            },
        )

        await handle_elt_confirma(update, ctx)

        ctx.application.create_task.assert_not_called()
