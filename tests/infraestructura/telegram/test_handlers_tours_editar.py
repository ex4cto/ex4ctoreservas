"""Unit tests for /editar_tour conversation handler."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.servicios.entidades import Servicio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _servicio(
    nombre: str = "City Tour",
    categoria: str = "Cartagena",
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
# Import guard — these will fail RED until handlers_tours.py exists
# ---------------------------------------------------------------------------

from garay.infraestructura.telegram.handlers_tours import (  # noqa: E402
    EDF_CAMPO,
    EDF_CONFIRMA,
    EDF_FAMILIA,
    EDF_FICHA,
    EDF_TOUR,
    cmd_editar_tour,
    handle_edt_confirma,
    handle_edt_familia,
    handle_edt_nueva_familia_texto,
    handle_edt_tour,
    handle_edt_valor,
)

# ---------------------------------------------------------------------------
# Phase 6.1 — /editar_tour tests
# ---------------------------------------------------------------------------


class TestCmdEditarTour:
    @pytest.mark.asyncio
    async def test_cmd_editar_tour_muestra_familias(self) -> None:
        """Entry point returns family inline keyboard (requires admin; mocks repo.listar())."""
        s1 = _servicio("City Tour", "Cartagena")
        s2 = _servicio("Islas", "Cartagena")
        s3 = _servicio("Desierto", "Guajira")
        update = _make_update()
        ctx = _make_context(servicios=[s1, s2, s3])

        result = await cmd_editar_tour.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EDF_FAMILIA
        update.effective_message.reply_text.assert_called_once()
        # Must have called listar() (ALL tours, including inactive)
        ctx.bot_data["servicio_repo"].listar.assert_called_once()
        ctx.bot_data["servicio_repo"].listar_activos.assert_not_called()


class TestHandleEdtFamilia:
    @pytest.mark.asyncio
    async def test_seleccionar_familia_muestra_tours(self) -> None:
        """Family selection returns tour list keyboard."""
        s1 = _servicio("City Tour", "Cartagena")
        s2 = _servicio("Islas", "Cartagena")
        update = _make_update(callback_data="edt_familia:Cartagena")
        ctx = _make_context(
            servicios=[s1, s2],
            user_data={"edt_servicios": [s1, s2]},
        )

        result = await handle_edt_familia(update, ctx)

        assert result == EDF_TOUR
        update.effective_message.reply_text.assert_called_once()


class TestHandleEdtTour:
    @pytest.mark.asyncio
    async def test_seleccionar_tour_muestra_ficha(self) -> None:
        """Tour selection returns detail screen with edit buttons."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data=f"edt_tour:{s1.id}")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_servicios": [s1]},
        )

        result = await handle_edt_tour(update, ctx)

        assert result == EDF_FICHA
        assert ctx.user_data.get("edt_target_id") == str(s1.id)
        update.effective_message.reply_text.assert_called()


class TestHandleEdtCampoNombre:
    @pytest.mark.asyncio
    async def test_editar_nombre_muestra_confirmacion_antes_despues(self) -> None:
        """Name edit shows before→after screen."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(text="Nuevo City Tour")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "nombre",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CONFIRMA
        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "City Tour" in msg or "Nuevo City Tour" in msg

    @pytest.mark.asyncio
    async def test_editar_nombre_noop_guard(self) -> None:
        """Same name → no save, notifica sin cambio, returns to ficha."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(text="City Tour")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "nombre",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_FICHA
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_editar_nombre_vacio_rechazado(self) -> None:
        """Empty name → error, stays in EDF_CAMPO state."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(text="   ")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "nombre",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CAMPO
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_editar_nombre_guarda_y_refresca_fsm(self) -> None:
        """Confirm → servicio_repo.guardar() called + fsm.refrescar_servicios() called."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data="edt_confirmar")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "nombre",
                "edt_valor": "Nuevo City Tour",
            },
        )
        repo = ctx.bot_data["servicio_repo"]
        repo.buscar_por_id.return_value = s1
        repo.listar_activos.return_value = [s1]

        result = await handle_edt_confirma(update, ctx)

        assert result == EDF_FICHA
        repo.guardar.assert_called_once()
        ctx.bot_data["fsm"].refrescar_servicios.assert_called_once()


class TestHandleEdtCampoNeto:
    @pytest.mark.asyncio
    async def test_editar_neto_adulto_positivo_acepta(self) -> None:
        """Valid positive value → confirmation shown."""
        s1 = _servicio()
        update = _make_update(text="35000")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "neto_adulto",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CONFIRMA

    @pytest.mark.asyncio
    async def test_editar_neto_adulto_cero_rechazado(self) -> None:
        """Zero input → error, no save."""
        s1 = _servicio()
        update = _make_update(text="0")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "neto_adulto",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CAMPO
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_editar_neto_adulto_negativo_rechazado(self) -> None:
        """Negative input → error, no save."""
        s1 = _servicio()
        update = _make_update(text="-5000")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "neto_adulto",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CAMPO
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_editar_neto_adulto_vacio_acepta(self) -> None:
        """Empty input → confirmation shown (clears field)."""
        s1 = _servicio()
        update = _make_update(text="")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "neto_adulto",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CONFIRMA


class TestHandleEdtFamiliaReasign:
    @pytest.mark.asyncio
    async def test_editar_familia_existente(self) -> None:
        """Selecting existing family button → before→after confirm."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data="edt_familia_nueva:Guajira")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "familia",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_familia(update, ctx)

        assert result == EDF_CONFIRMA

    @pytest.mark.asyncio
    async def test_editar_familia_nueva_libre(self) -> None:
        """'Nueva familia' button → text prompt for new family name."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data="edt_familia_nueva_libre")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "familia",
            },
        )

        result = await handle_edt_familia(update, ctx)

        # Must prompt for free text
        assert result == EDF_CAMPO
        update.effective_message.reply_text.assert_called_once()


class TestHandleEdtNuevaFamiliaTexto:
    @pytest.mark.asyncio
    async def test_nueva_familia_libre_texto_muestra_confirmacion(self) -> None:
        """Free-text new family name → before→after confirm."""
        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(text="San Andres")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "familia",
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_nueva_familia_texto(update, ctx)

        assert result == EDF_CONFIRMA


class TestHandleEdtToggleActivo:
    @pytest.mark.asyncio
    async def test_toggle_activo_desactiva(self) -> None:
        """activo=True, campo='activo', edt_activo_nuevo=False → save sets activo=False."""
        s1 = _servicio(activo=True)
        update = _make_update(callback_data="edt_confirmar")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "activo",
                "edt_activo_nuevo": False,
            },
        )
        repo = ctx.bot_data["servicio_repo"]
        repo.buscar_por_id.return_value = s1
        repo.listar_activos.return_value = []

        result = await handle_edt_confirma(update, ctx)

        assert result == EDF_FICHA
        repo.guardar.assert_called_once()
        saved = repo.guardar.call_args[0][0]
        assert saved.activo is False

    @pytest.mark.asyncio
    async def test_toggle_activo_activa(self) -> None:
        """activo=False, campo='activo', edt_activo_nuevo=True → save sets activo=True."""
        s1 = _servicio(activo=False)
        update = _make_update(callback_data="edt_confirmar")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "activo",
                "edt_activo_nuevo": True,
            },
        )
        repo = ctx.bot_data["servicio_repo"]
        repo.buscar_por_id.return_value = s1
        repo.listar_activos.return_value = [s1]

        result = await handle_edt_confirma(update, ctx)

        assert result == EDF_FICHA
        repo.guardar.assert_called_once()
        saved = repo.guardar.call_args[0][0]
        assert saved.activo is True


class TestHandleEdtCancelar:
    @pytest.mark.asyncio
    async def test_cancelar_edicion_sale_limpio(self) -> None:
        """Cancel mid-flow returns END without saving."""
        s1 = _servicio()
        update = _make_update(callback_data="edt_cancelar")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id), "edt_campo": "nombre"},
        )

        result = await handle_edt_confirma(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()
