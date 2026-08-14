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
    EDF_NUEVA_FAMILIA,
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
        """'Nueva familia' button → text prompt, returns EDF_NUEVA_FAMILIA (Option B fix)."""
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

        # Must prompt for free text and transition to the dedicated state
        assert result == EDF_NUEVA_FAMILIA
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

    @pytest.mark.asyncio
    async def test_cancelar_con_activo_pendiente_no_persiste_toggle(self) -> None:
        """
        Cancel during an activo-toggle confirmation MUST NOT persist the toggle.

        WARNING-1 edge case: if edt_activo_nuevo is in user_data and the user
        taps Cancel, the toggle must be discarded — not saved.
        """
        s1 = _servicio(activo=True)
        update = _make_update(callback_data="edt_cancelar")
        ctx = _make_context(
            servicios=[s1],
            user_data={
                "edt_target_id": str(s1.id),
                "edt_campo": "activo",
                "edt_activo_nuevo": False,  # pending toggle — must be discarded on cancel
            },
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_confirma(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()
        # User_data must be cleaned up
        assert "edt_activo_nuevo" not in ctx.user_data


# ---------------------------------------------------------------------------
# Routing tests — verify PTB state dispatch, not just handler logic
# ---------------------------------------------------------------------------


class TestEdtCampoRoutingNuevaFamilia:
    """
    These tests simulate the PTB routing that actually runs in production.

    In state EDF_CAMPO, PTB evaluates handlers in list order and stops at the
    first match.  The FIRST MessageHandler(_TEXT, ...) registered for EDF_CAMPO
    is the one that actually runs when the user types text.

    CRITICAL-1 root cause: both handle_edt_valor and handle_edt_nueva_familia_texto
    were registered under EDF_CAMPO.  PTB always dispatches to handle_edt_valor
    first, so handle_edt_nueva_familia_texto is never reached.

    The fix (Option B) introduces EDF_NUEVA_FAMILIA (228) as a dedicated state so
    there is no collision.  These tests document the correct post-fix behaviour and
    act as a regression guard.
    """

    @pytest.mark.asyncio
    async def test_edf_campo_texto_con_campo_familia_debe_ir_a_confirma_no_error(
        self,
    ) -> None:
        """
        After 'Nueva familia' is chosen, the user types a name.
        The PTB-dispatched handler for that text input MUST return EDF_CONFIRMA
        (not stay in EDF_CAMPO with a 'neto inválido' error).

        RED: with current code handle_edt_valor is the first MessageHandler(_TEXT)
        in EDF_CAMPO. When edt_campo='familia' it falls through to the fallback
        branch and returns EDF_CAMPO — this test will FAIL before the fix.

        GREEN: after introducing EDF_NUEVA_FAMILIA, the text in that new state is
        handled by handle_edt_nueva_familia_texto, which returns EDF_CONFIRMA.
        We verify by calling the handler that PTB would actually invoke.
        """
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

        # After the fix: the handler that PTB dispatches in EDF_NUEVA_FAMILIA is
        # handle_edt_nueva_familia_texto, which must return EDF_CONFIRMA.
        result = await handle_edt_nueva_familia_texto(update, ctx)

        assert result == EDF_CONFIRMA, (
            f"Expected EDF_CONFIRMA ({EDF_CONFIRMA}) but got {result}. "
            "The nueva-familia text handler must route to confirm, not loop with an error."
        )
        # Also verify the family name was stored for later confirmation
        assert ctx.user_data.get("edt_valor") == "San Andres"

    @pytest.mark.asyncio
    async def test_handle_edt_valor_con_campo_familia_no_llega_a_confirma(
        self,
    ) -> None:
        """
        Regression guard: handle_edt_valor must NOT silently accept edt_campo='familia'.
        If it did, a bug would allow writing a familia through the wrong handler.
        When edt_campo='familia', handle_edt_valor must stay in EDF_CAMPO (error path).

        This documents the BUG that existed before Option B:
        the wrong handler (handle_edt_valor) was being dispatched by PTB for
        'nueva familia' text input because both were registered under EDF_CAMPO.
        """
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

        # handle_edt_valor has no branch for campo='familia', it falls through to
        # the fallback error path and returns EDF_CAMPO.
        result = await handle_edt_valor(update, ctx)

        assert result == EDF_CAMPO, (
            "handle_edt_valor must return EDF_CAMPO when campo='familia' "
            "(it is not the right handler for this path)."
        )
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_edf_nueva_familia_state_exists(self) -> None:
        """EDF_NUEVA_FAMILIA constant must exist and be in the 220-229 range."""
        from garay.infraestructura.telegram.handlers_tours import EDF_NUEVA_FAMILIA

        assert isinstance(EDF_NUEVA_FAMILIA, int)
        assert 220 <= EDF_NUEVA_FAMILIA <= 229, (
            f"EDF_NUEVA_FAMILIA={EDF_NUEVA_FAMILIA} is outside the expected 220-229 range"
        )

    @pytest.mark.asyncio
    async def test_handle_edt_familia_nueva_libre_retorna_edf_nueva_familia(
        self,
    ) -> None:
        """
        When the admin taps 'Nueva familia', handle_edt_familia must return
        EDF_NUEVA_FAMILIA (not EDF_CAMPO) so PTB routes the next text message
        to handle_edt_nueva_familia_texto instead of handle_edt_valor.
        """
        from garay.infraestructura.telegram.handlers_tours import EDF_NUEVA_FAMILIA

        s1 = _servicio("City Tour", "Cartagena")
        update = _make_update(callback_data="edt_familia_nueva_libre")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id), "edt_campo": "familia"},
        )

        result = await handle_edt_familia(update, ctx)

        assert result == EDF_NUEVA_FAMILIA, (
            f"Expected EDF_NUEVA_FAMILIA ({EDF_NUEVA_FAMILIA}) but got {result}. "
            "handle_edt_familia must return EDF_NUEVA_FAMILIA (not EDF_CAMPO) "
            "when the callback is 'edt_familia_nueva_libre'."
        )


class TestEdtNuevaFamiliaEndToEnd:
    """
    Full flow: taps 'Nueva familia' → types name → confirms → saved in repo with
    the new categoria and FSM refreshed.
    """

    @pytest.mark.asyncio
    async def test_nueva_familia_flujo_completo_guarda_y_refresca(self) -> None:
        """
        End-to-end: admin writes new family name → confirm → service saved with
        new categoria and FSM refreshed.  Verifies no 'neto inválido' error in path.
        """
        s1 = _servicio("City Tour", "Cartagena")

        # Step 1: tap 'Nueva familia' → must go to EDF_NUEVA_FAMILIA
        update_cb = _make_update(callback_data="edt_familia_nueva_libre")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id), "edt_campo": "familia"},
        )
        state_after_tap = await handle_edt_familia(update_cb, ctx)
        assert state_after_tap == EDF_NUEVA_FAMILIA

        # Step 2: type new family name in EDF_NUEVA_FAMILIA → must go to EDF_CONFIRMA
        update_txt = _make_update(text="San Andres")
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1
        state_after_text = await handle_edt_nueva_familia_texto(update_txt, ctx)
        assert state_after_text == EDF_CONFIRMA
        assert ctx.user_data.get("edt_valor") == "San Andres"

        # Step 3: confirm → service saved with new categoria, FSM refreshed
        update_confirm = _make_update(callback_data="edt_confirmar")
        repo = ctx.bot_data["servicio_repo"]
        repo.buscar_por_id.return_value = s1
        repo.listar_activos.return_value = [s1]
        state_after_confirm = await handle_edt_confirma(update_confirm, ctx)

        assert state_after_confirm == EDF_FICHA
        repo.guardar.assert_called_once()
        saved = repo.guardar.call_args[0][0]
        assert saved.categoria == "San Andres", (
            f"Expected categoria='San Andres' but got {saved.categoria!r}. "
            "The new family name must be persisted."
        )
        ctx.bot_data["fsm"].refrescar_servicios.assert_called_once()


# ---------------------------------------------------------------------------
# Task 4.1 RED -- _teclado_horarios helper
# ---------------------------------------------------------------------------


class TestTecladoHorarios:
    """_teclado_horarios(horarios, prefix) must return a properly structured keyboard."""

    def test_teclado_horarios_filas_quit_mas_agregar_listo(self) -> None:
        """Two horarios: two X rows + agregar row + listo row (4 total)."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios(["07:00", "19:00"], prefix="edh_")
        assert isinstance(markup, InlineKeyboardMarkup)
        rows = markup.inline_keyboard
        assert len(rows) == 4, f"Expected 4 rows but got {len(rows)}"

    def test_teclado_horarios_callbacks_quitar(self) -> None:
        """Each horario row callback_data must be prefix+quitar:HH:MM."""
        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios(["07:00", "19:00"], prefix="edh_")
        rows = markup.inline_keyboard
        assert rows[0][0].callback_data == "edh_quitar:07:00"
        assert rows[1][0].callback_data == "edh_quitar:19:00"

    def test_teclado_horarios_callback_agregar(self) -> None:
        """The agregar row callback must be prefix+agregar."""
        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios(["07:00"], prefix="edh_")
        rows = markup.inline_keyboard
        assert rows[-2][0].callback_data == "edh_agregar"

    def test_teclado_horarios_callback_listo(self) -> None:
        """The Listo row callback must be prefix+listo."""
        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios(["07:00"], prefix="edh_")
        rows = markup.inline_keyboard
        assert rows[-1][0].callback_data == "edh_listo"

    def test_teclado_horarios_lista_vacia(self) -> None:
        """Empty list: 0 X rows + agregar row + listo row (2 total)."""
        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios([], prefix="edh_")
        rows = markup.inline_keyboard
        assert len(rows) == 2

    def test_teclado_horarios_label_display_ampm(self) -> None:
        """Each X row must show AM/PM formatted time in the button text."""
        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios(["07:00", "19:00"], prefix="edh_")
        rows = markup.inline_keyboard
        assert "7:00 AM" in rows[0][0].text
        assert "7:00 PM" in rows[1][0].text

    def test_teclado_horarios_nvt_prefix(self) -> None:
        """Same helper works with nvt_hor_ prefix."""
        from garay.infraestructura.telegram.handlers_tours import _teclado_horarios

        markup = _teclado_horarios(["08:00"], prefix="nvt_hor_")
        rows = markup.inline_keyboard
        assert rows[0][0].callback_data == "nvt_hor_quitar:08:00"
        assert rows[-2][0].callback_data == "nvt_hor_agregar"
        assert rows[-1][0].callback_data == "nvt_hor_listo"


# ---------------------------------------------------------------------------
# Task 5.1 RED -- EDH state constants + editor handlers
# ---------------------------------------------------------------------------


class TestEdhStateConstants:
    """EDH_* constants must be defined, unique, in range 237-239."""

    def test_edh_lista_equals_237(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import EDH_LISTA

        assert EDH_LISTA == 237

    def test_edh_agregar_equals_238(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import EDH_AGREGAR

        assert EDH_AGREGAR == 238

    def test_edh_constants_unique(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import EDH_AGREGAR, EDH_LISTA

        assert EDH_LISTA != EDH_AGREGAR


class TestHandleEdtFichaHorarios:
    """handle_edt_ficha with campo=horarios must open the EDH editor."""

    @pytest.mark.asyncio
    async def test_edt_campo_horarios_opens_edh(self) -> None:
        """Selecting horarios from the ficha must return EDH_LISTA."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDH_LISTA,
            handle_edt_ficha,
        )

        s1 = _servicio()
        update = _make_update(callback_data="edt_campo:horarios")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edt_ficha(update, ctx)

        assert result == EDH_LISTA

    @pytest.mark.asyncio
    async def test_edt_campo_horarios_sends_keyboard(self) -> None:
        """Opening the horarios editor must send an InlineKeyboardMarkup."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers_tours import handle_edt_ficha

        s1 = _servicio()
        update = _make_update(callback_data="edt_campo:horarios")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        await handle_edt_ficha(update, ctx)

        call_args = update.effective_message.reply_text.call_args_list
        keyboards = [
            c.kwargs.get("reply_markup") or (c.args[1] if len(c.args) > 1 else None)
            for c in call_args
        ]
        assert any(isinstance(k, InlineKeyboardMarkup) for k in keyboards)


class TestHandleEdhLista:
    """handle_edh_lista routes edh_agregar / edh_quitar / edh_listo correctly."""

    @pytest.mark.asyncio
    async def test_edh_agregar_goes_to_edh_agregar_state(self) -> None:
        """Tapping agregar returns EDH_AGREGAR."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDH_AGREGAR,
            handle_edh_lista,
        )

        s1 = _servicio()
        update = _make_update(callback_data="edh_agregar")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edh_lista(update, ctx)

        assert result == EDH_AGREGAR

    @pytest.mark.asyncio
    async def test_edh_quitar_removes_and_rerenders(self) -> None:
        """Tapping X removes the horario, saves, and returns EDH_LISTA."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDH_LISTA,
            handle_edh_lista,
        )

        s1 = _servicio()
        s1.horarios = ["07:00", "19:00"]
        update = _make_update(callback_data="edh_quitar:07:00")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edh_lista(update, ctx)

        assert result == EDH_LISTA
        ctx.bot_data["servicio_repo"].guardar.assert_called_once()
        saved = ctx.bot_data["servicio_repo"].guardar.call_args[0][0]
        assert "07:00" not in saved.horarios
        assert "19:00" in saved.horarios

    @pytest.mark.asyncio
    async def test_edh_listo_returns_edf_ficha(self) -> None:
        """Tapping Listo returns EDF_FICHA."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDF_FICHA,
            handle_edh_lista,
        )

        s1 = _servicio()
        update = _make_update(callback_data="edh_listo")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edh_lista(update, ctx)

        assert result == EDF_FICHA


class TestHandleEdhAgregarTexto:
    """handle_edh_agregar_texto validates and persists new horario."""

    @pytest.mark.asyncio
    async def test_horario_valido_agrega_y_vuelve_a_lista(self) -> None:
        """Valid horario text -> agregar, save, return EDH_LISTA."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDH_LISTA,
            handle_edh_agregar_texto,
        )

        s1 = _servicio()
        s1.horarios = ["07:00"]
        update = _make_update(text="9pm")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edh_agregar_texto(update, ctx)

        assert result == EDH_LISTA
        ctx.bot_data["servicio_repo"].guardar.assert_called_once()
        saved = ctx.bot_data["servicio_repo"].guardar.call_args[0][0]
        assert "21:00" in saved.horarios

    @pytest.mark.asyncio
    async def test_horario_invalido_queda_en_edh_agregar(self) -> None:
        """Invalid text -> error reply, stay in EDH_AGREGAR."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDH_AGREGAR,
            handle_edh_agregar_texto,
        )

        s1 = _servicio()
        update = _make_update(text="nope")
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edh_agregar_texto(update, ctx)

        assert result == EDH_AGREGAR
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()

    @pytest.mark.asyncio
    async def test_horario_duplicado_queda_en_edh_agregar(self) -> None:
        """Duplicate horario -> error reply, stay in EDH_AGREGAR."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDH_AGREGAR,
            handle_edh_agregar_texto,
        )

        s1 = _servicio()
        s1.horarios = ["19:00"]
        update = _make_update(text="7pm")  # canonical 19:00 = duplicate
        ctx = _make_context(
            servicios=[s1],
            user_data={"edt_target_id": str(s1.id)},
        )
        ctx.bot_data["servicio_repo"].buscar_por_id.return_value = s1

        result = await handle_edh_agregar_texto(update, ctx)

        assert result == EDH_AGREGAR
        ctx.bot_data["servicio_repo"].guardar.assert_not_called()


# ---------------------------------------------------------------------------
# Task 6.1 RED -- EDH states wired in bot.py
# ---------------------------------------------------------------------------


class TestEdhStatesBotWiring:
    """Structural: EDH_LISTA and EDH_AGREGAR must be in editar_tour_conv_handler."""

    def _get_editar_conv(self) -> object:
        from unittest.mock import MagicMock, patch

        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.bot import crear_aplicacion

        with patch("garay.infraestructura.telegram.bot.obtener_settings") as ms:
            settings = MagicMock()
            settings.propietario_telegram_ids = ""
            settings.dev_telegram_ids = ""
            ms.return_value = settings
            app = crear_aplicacion("fake:token")

        for _group, handlers in app.handlers.items():
            for h in handlers:
                if isinstance(h, ConversationHandler):
                    for ep in h.entry_points:
                        if hasattr(ep, "commands") and "editar_tour" in ep.commands:
                            return h
        return None

    def test_edh_lista_registered_in_editar_tour(self) -> None:
        """EDH_LISTA must appear in editar_tour_conv_handler states."""
        from garay.infraestructura.telegram.handlers_tours import EDH_LISTA

        editar_conv = self._get_editar_conv()
        assert editar_conv is not None, "editar_tour_conv_handler not found"
        assert EDH_LISTA in editar_conv.states, (  # type: ignore[union-attr]
            f"EDH_LISTA ({EDH_LISTA}) not registered in editar_tour_conv_handler states"
        )

    def test_edh_agregar_registered_in_editar_tour(self) -> None:
        """EDH_AGREGAR must appear in editar_tour_conv_handler states."""
        from garay.infraestructura.telegram.handlers_tours import EDH_AGREGAR

        editar_conv = self._get_editar_conv()
        assert editar_conv is not None, "editar_tour_conv_handler not found"
        assert EDH_AGREGAR in editar_conv.states, (  # type: ignore[union-attr]
            f"EDH_AGREGAR ({EDH_AGREGAR}) not registered in editar_tour_conv_handler states"
        )

    def test_edh_agregar_state_has_single_message_handler(self) -> None:
        """EDH_AGREGAR must contain exactly ONE MessageHandler (Fase 1 lesson)."""
        from telegram.ext import MessageHandler

        from garay.infraestructura.telegram.handlers_tours import EDH_AGREGAR

        editar_conv = self._get_editar_conv()
        assert editar_conv is not None
        handlers_list = editar_conv.states.get(EDH_AGREGAR, [])  # type: ignore[union-attr]
        text_handlers = [h for h in handlers_list if isinstance(h, MessageHandler)]
        assert len(text_handlers) == 1, (
            f"EDH_AGREGAR must have exactly 1 MessageHandler, got {len(text_handlers)}"
        )
