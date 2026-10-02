"""Tests for fire-and-forget lista_precios trigger points in handlers_tours.py.

Verifies that asyncio.create_task(publicar_seguro(...)) is called after:
  - /nuevo_tour create success (handle_nvt_crear)
  - /editar_tour EDF_CONFIRMA success path (handle_edt_confirma)
  - /eliminar_tour (deactivate) success path (handle_elt_confirma)

TDD RED: these tests are written before the trigger code is added.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio
from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.telegram.handlers_tours import (
    NVT_CONFIRMA,
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
    update.effective_user = MagicMock(id=42)
    update.effective_message = AsyncMock()
    if callback_data is not None:
        query = AsyncMock()
        query.data = callback_data
        query.answer = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None
    return update


def _mock_service() -> MagicMock:
    """Build a mock PublicarListaPreciosServicio."""
    svc = MagicMock(spec=PublicarListaPreciosServicio)
    return svc


def _make_context_nvt(
    user_data: dict[str, object] | None = None,
    service: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    repo = MagicMock()
    repo.siguiente_numero.return_value = 10
    repo.guardar.return_value = None
    fsm = MagicMock()
    svc = service or _mock_service()
    ctx.bot_data = {
        "servicio_repo": repo,
        "fsm": fsm,
        "publicar_lista_precios_service": svc,
    }
    return ctx


def _make_context_edt(
    servicios: list[Servicio] | None = None,
    user_data: dict[str, object] | None = None,
    service: MagicMock | None = None,
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
    svc = service or _mock_service()
    ctx.bot_data = {
        "servicio_repo": repo,
        "fsm": fsm,
        "publicar_lista_precios_service": svc,
    }
    return ctx


# ---------------------------------------------------------------------------
# T2.23: Trigger tests
# ---------------------------------------------------------------------------


class TestNvtCrearTrigger:
    """After /nuevo_tour create success, asyncio.create_task(publicar_seguro(...)) fires."""

    @pytest.mark.asyncio
    async def test_nvt_crear_llama_create_task(self) -> None:
        """handle_nvt_crear calls asyncio.create_task after saving the new tour."""
        update = _make_update(callback_data="nvt_crear")
        service = _mock_service()
        ctx = _make_context_nvt(
            user_data={
                "nvt_familia": "PLAYERO",
                "nvt_nombre": "Nuevo Tour",
                "nvt_neto_adulto": Decimal("30000"),
                "nvt_neto_nino": None,
                "nvt_horarios": [],
            },
            service=service,
        )

        with patch("asyncio.create_task") as mock_create_task:
            await handle_nvt_crear(update, ctx)

        mock_create_task.assert_called_once()


class TestEdtConfirmaTrigger:
    """After EDF_CONFIRMA success (any field), asyncio.create_task(publicar_seguro(...)) fires."""

    @pytest.mark.asyncio
    async def test_edt_confirma_nombre_llama_create_task(self) -> None:
        """handle_edt_confirma calls create_task after confirming a nombre edit."""
        s = _servicio("City Tour")
        update = _make_update(callback_data="edt_confirmar")
        service = _mock_service()
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "edt_target_id": str(s.id),
                "edt_campo": "nombre",
                "edt_valor": "Nuevo Nombre",
            },
            service=service,
        )

        with patch("asyncio.create_task") as mock_create_task:
            await handle_edt_confirma(update, ctx)

        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_edt_confirma_activo_llama_create_task(self) -> None:
        """handle_edt_confirma calls create_task after toggling activo."""
        s = _servicio("City Tour")
        update = _make_update(callback_data="edt_confirmar")
        service = _mock_service()
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "edt_target_id": str(s.id),
                "edt_campo": "activo",
                "edt_activo_nuevo": False,
            },
            service=service,
        )

        with patch("asyncio.create_task") as mock_create_task:
            await handle_edt_confirma(update, ctx)

        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_edt_confirma_cancelar_no_llama_create_task(self) -> None:
        """handle_edt_confirma does NOT call create_task when action is 'cancelar'."""
        s = _servicio("City Tour")
        update = _make_update(callback_data="edt_cancelar")
        service = _mock_service()
        ctx = _make_context_edt(
            servicios=[s],
            user_data={"edt_target_id": str(s.id), "edt_campo": "nombre"},
            service=service,
        )

        with patch("asyncio.create_task") as mock_create_task:
            await handle_edt_confirma(update, ctx)

        mock_create_task.assert_not_called()


class TestEltConfirmaTrigger:
    """After deactivate (eliminar tour) success, asyncio.create_task(publicar_seguro(...)) fires."""

    @pytest.mark.asyncio
    async def test_elt_confirma_llama_create_task(self) -> None:
        """handle_elt_confirma calls create_task after soft-deleting a tour."""
        s = _servicio("Tour a Eliminar")
        update = _make_update(callback_data="elt_confirmar")
        service = _mock_service()
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "elt_target_id": str(s.id),
                "elt_nombre": s.nombre,
            },
            service=service,
        )

        with patch("asyncio.create_task") as mock_create_task:
            await handle_elt_confirma(update, ctx)

        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_elt_cancelar_no_llama_create_task(self) -> None:
        """handle_elt_confirma does NOT call create_task when action is 'cancelar'."""
        s = _servicio("Tour a Cancelar")
        update = _make_update(callback_data="elt_cancelar")
        service = _mock_service()
        ctx = _make_context_edt(
            servicios=[s],
            user_data={
                "elt_target_id": str(s.id),
                "elt_nombre": s.nombre,
            },
            service=service,
        )

        with patch("asyncio.create_task") as mock_create_task:
            await handle_elt_confirma(update, ctx)

        mock_create_task.assert_not_called()
