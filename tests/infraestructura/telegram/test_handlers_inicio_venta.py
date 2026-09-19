"""Tests for PR F — date selector at the start of /nueva_venta."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.infraestructura.telegram.estados import ESTADO_PTB

_SERVICIOS: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARU", []),
]
_PUNTOS: list[str] = ["Marie Real"]


def _make_fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=_SERVICIOS, puntos_venta=_PUNTOS)


def _make_update_command() -> MagicMock:
    """Update from /nueva_venta command (no callback_query)."""
    update = MagicMock()
    update.callback_query = None
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_message = AsyncMock()
    msg = AsyncMock()
    msg.text = "/nueva_venta"
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _make_update_cb(data: str) -> MagicMock:
    """Update with a callback_query."""
    update = MagicMock()
    update.message = None
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_message = AsyncMock()
    cq = AsyncMock()
    cq.data = data
    cq.answer = AsyncMock()
    cq.edit_message_text = AsyncMock()
    update.callback_query = cq
    return update


def _make_update_text(text: str) -> MagicMock:
    """Update with a plain text message."""
    update = MagicMock()
    update.callback_query = None
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_message = AsyncMock()
    msg = AsyncMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _make_context(
    *,
    fsm: FSMTiquetera | None = None,
    ctx: ContextoVenta | None = None,
    user_data_extra: dict | None = None,  # type: ignore[type-arg]
    es_admin: bool = False,
) -> MagicMock:
    context = MagicMock()

    fsm_inst = fsm or _make_fsm()
    fl_repo = MagicMock()
    fl_mock = MagicMock()
    fl_mock.nombre = "Maria Lopez"
    fl_mock.es_admin = es_admin
    fl_repo.buscar_por_telegram_id.return_value = fl_mock

    context.bot_data = {"fsm": fsm_inst, "freelancer_repo": fl_repo}
    context.bot = AsyncMock()

    user_data: dict[str, object] = {}
    if ctx:
        user_data["contexto"] = ctx
    if user_data_extra:
        user_data.update(user_data_extra)
    context.user_data = user_data

    return context


# ---------------------------------------------------------------------------
# A. handle_iniciar_venta shows date selector
# ---------------------------------------------------------------------------


class TestIniciarVentaMuestraBotonesDeInicio:
    @pytest.mark.asyncio
    async def test_muestra_botones_inicio_hoy_y_otra_fecha(self) -> None:
        """SC-02: Admin sees both buttons."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers import handle_iniciar_venta
        from garay.infraestructura.telegram.handlers_inicio_venta import INICIO_VENTA

        update = _make_update_command()
        context = _make_context(es_admin=True)

        with patch(
            "garay.infraestructura.telegram.auth.es_admin_o_propietario",
            new=AsyncMock(return_value=True),
        ):
            result = await handle_iniciar_venta(update, context)

        assert result == INICIO_VENTA
        update.message.reply_text.assert_called_once()
        kwargs = update.message.reply_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None, "Expected InlineKeyboardMarkup"
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "inicio_hoy" in flat_data
        assert "inicio_otra_fecha" in flat_data


# ---------------------------------------------------------------------------
# SC-01..SC-04, SC-07..SC-09: tier-aware keyboard in _mostrar_selector_inicio
# ---------------------------------------------------------------------------

_PATCH_ES_ADMIN = "garay.infraestructura.telegram.auth.es_admin_o_propietario"


class TestMostrarSelectorInicio:
    """Tests for tier-aware keyboard shape via handle_iniciar_venta and handle_inicio_volver."""

    @pytest.mark.asyncio
    async def test_sc01_freelancer_oculta_otra_fecha(self) -> None:
        """SC-01: FREELANCER entry — inicio_otra_fecha absent."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers import handle_iniciar_venta
        from garay.infraestructura.telegram.handlers_inicio_venta import INICIO_VENTA

        update = _make_update_command()
        context = _make_context(es_admin=False)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=False)):
            result = await handle_iniciar_venta(update, context)

        assert result == INICIO_VENTA
        kwargs = update.message.reply_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_hoy" in flat
        assert "inicio_otra_fecha" not in flat

    @pytest.mark.asyncio
    async def test_sc02_admin_muestra_ambos_botones(self) -> None:
        """SC-02: ADMIN entry — both buttons present."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers import handle_iniciar_venta

        update = _make_update_command()
        context = _make_context(es_admin=True)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=True)):
            await handle_iniciar_venta(update, context)

        kwargs = update.message.reply_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_hoy" in flat
        assert "inicio_otra_fecha" in flat

    @pytest.mark.asyncio
    async def test_sc03_propietario_muestra_ambos_botones(self) -> None:
        """SC-03: PROPIETARIO entry — both buttons present."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers import handle_iniciar_venta

        update = _make_update_command()
        context = _make_context(es_admin=False)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=True)):
            await handle_iniciar_venta(update, context)

        kwargs = update.message.reply_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_otra_fecha" in flat

    @pytest.mark.asyncio
    async def test_sc04_dev_muestra_ambos_botones(self) -> None:
        """SC-04: DEV entry — both buttons present."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers import handle_iniciar_venta

        update = _make_update_command()
        context = _make_context(es_admin=False)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=True)):
            await handle_iniciar_venta(update, context)

        kwargs = update.message.reply_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_otra_fecha" in flat

    @pytest.mark.asyncio
    async def test_sc07_freelancer_venta_hoy_sin_override(self) -> None:
        """SC-07: FREELANCER today sale — correct state, no fecha_venta_override."""
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_inicio_hoy

        update = _make_update_cb("inicio_hoy")
        context = _make_context(es_admin=False)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=False)):
            result = await handle_inicio_hoy(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        assert "fecha_venta_override" not in context.user_data

    @pytest.mark.asyncio
    async def test_sc08_freelancer_atras_oculta_otra_fecha(self) -> None:
        """SC-08: FREELANCER Atrás — returns INICIO_VENTA, override cleared, hides otra_fecha."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers_inicio_venta import (
            INICIO_VENTA,
            handle_inicio_volver,
        )

        update = _make_update_cb("inicio_volver")
        context = _make_context(
            es_admin=False,
            user_data_extra={"fecha_venta_override": datetime.datetime(2026, 9, 10)},
        )

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=False)):
            result = await handle_inicio_volver(update, context)

        assert result == INICIO_VENTA
        assert "fecha_venta_override" not in context.user_data
        kwargs = update.callback_query.edit_message_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_otra_fecha" not in flat

    @pytest.mark.asyncio
    async def test_sc09_admin_atras_muestra_ambos_botones(self) -> None:
        """SC-09: ADMIN Atrás — returns INICIO_VENTA, override cleared, keyboard shows both."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers_inicio_venta import (
            INICIO_VENTA,
            handle_inicio_volver,
        )

        update = _make_update_cb("inicio_volver")
        context = _make_context(
            es_admin=True,
            user_data_extra={"fecha_venta_override": datetime.datetime(2026, 9, 10)},
        )

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=True)):
            result = await handle_inicio_volver(update, context)

        assert result == INICIO_VENTA
        assert "fecha_venta_override" not in context.user_data
        kwargs = update.callback_query.edit_message_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_hoy" in flat
        assert "inicio_otra_fecha" in flat


# ---------------------------------------------------------------------------
# B. handle_inicio_hoy proceeds to METODO_INPUT
# ---------------------------------------------------------------------------


class TestIniciohoyProcedeAMetodoInput:
    @pytest.mark.asyncio
    async def test_retorna_metodo_input(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_inicio_hoy

        update = _make_update_cb("inicio_hoy")
        context = _make_context()

        result = await handle_inicio_hoy(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]


# ---------------------------------------------------------------------------
# B2. handle_inicio_hoy sets registrante_privilegiado based on tier
# ---------------------------------------------------------------------------


class TestIniciohoySetRegistrantePrivilegiado:
    @pytest.mark.asyncio
    async def test_admin_sets_privilegiado_true(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_inicio_hoy

        update = _make_update_cb("inicio_hoy")
        context = _make_context(es_admin=True)

        result = await handle_inicio_hoy(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        ctx = context.user_data.get("contexto")
        assert isinstance(ctx, ContextoVenta)
        assert ctx.registrante_privilegiado is True

    @pytest.mark.asyncio
    async def test_freelancer_sets_privilegiado_false(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_inicio_hoy

        update = _make_update_cb("inicio_hoy")
        context = _make_context(es_admin=False)

        await handle_inicio_hoy(update, context)

        ctx = context.user_data.get("contexto")
        assert isinstance(ctx, ContextoVenta)
        assert ctx.registrante_privilegiado is False

    @pytest.mark.asyncio
    async def test_sends_metodo_prompt_message(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_inicio_hoy

        update = _make_update_cb("inicio_hoy")
        context = _make_context()

        await handle_inicio_hoy(update, context)

        update.callback_query.edit_message_text.assert_called_once()


# ---------------------------------------------------------------------------
# D2. handle_fecha_ayer sets registrante_privilegiado
# ---------------------------------------------------------------------------


class TestFechaAyerSetRegistrantePrivilegiado:
    @pytest.mark.asyncio
    async def test_admin_sets_privilegiado_true(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_fecha_ayer

        update = _make_update_cb("fecha_ayer")
        context = _make_context(es_admin=True)

        result = await handle_fecha_ayer(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        ctx = context.user_data.get("contexto")
        assert isinstance(ctx, ContextoVenta)
        assert ctx.registrante_privilegiado is True

    @pytest.mark.asyncio
    async def test_preserves_fecha_override_after_setting_privilegiado(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_fecha_ayer

        update = _make_update_cb("fecha_ayer")
        context = _make_context(es_admin=True)

        await handle_fecha_ayer(update, context)

        assert context.user_data.get("fecha_venta_override") is not None


# ---------------------------------------------------------------------------
# E2. handle_fecha_antes_ayer sets registrante_privilegiado
# ---------------------------------------------------------------------------


class TestFechaAntesAyerSetRegistrantePrivilegiado:
    @pytest.mark.asyncio
    async def test_admin_sets_privilegiado_true(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_fecha_antes_ayer

        update = _make_update_cb("fecha_antes_ayer")
        context = _make_context(es_admin=True)

        result = await handle_fecha_antes_ayer(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        ctx = context.user_data.get("contexto")
        assert isinstance(ctx, ContextoVenta)
        assert ctx.registrante_privilegiado is True


# ---------------------------------------------------------------------------
# C. handle_inicio_otra_fecha shows date sub-picker
# ---------------------------------------------------------------------------


class TestIniciOtraFechaMuestraSubPicker:
    @pytest.mark.asyncio
    async def test_muestra_botones_fecha_retroactiva(self) -> None:
        """SC-06 variant: authorized user sees the retroactive date sub-picker."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers_inicio_venta import (
            FECHA_RETROACTIVA,
            handle_inicio_otra_fecha,
        )

        update = _make_update_cb("inicio_otra_fecha")
        context = _make_context(es_admin=True)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=True)):
            result = await handle_inicio_otra_fecha(update, context)

        assert result == FECHA_RETROACTIVA
        update.callback_query.edit_message_text.assert_called_once()
        kwargs = update.callback_query.edit_message_text.call_args
        all_args = list(kwargs[0]) + list(kwargs[1].values())
        markup = next((a for a in all_args if isinstance(a, InlineKeyboardMarkup)), None)
        assert markup is not None
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "fecha_ayer" in flat_data
        assert "fecha_antes_ayer" in flat_data
        assert "fecha_otra" in flat_data
        assert "inicio_volver" in flat_data


# ---------------------------------------------------------------------------
# D. handle_fecha_ayer saves override and proceeds
# ---------------------------------------------------------------------------


class TestFechaAyerGuardaOverride:
    @pytest.mark.asyncio
    async def test_guarda_override_ayer_y_procede(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_fecha_ayer

        update = _make_update_cb("fecha_ayer")
        context = _make_context()

        result = await handle_fecha_ayer(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        override = context.user_data.get("fecha_venta_override")
        assert override is not None
        ayer = datetime.date.today() - datetime.timedelta(days=1)
        assert isinstance(override, datetime.datetime)
        assert override.date() == ayer


# ---------------------------------------------------------------------------
# E. handle_fecha_antes_ayer saves override and proceeds
# ---------------------------------------------------------------------------


class TestFechaAntesAyerGuardaOverride:
    @pytest.mark.asyncio
    async def test_guarda_override_antes_ayer_y_procede(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import handle_fecha_antes_ayer

        update = _make_update_cb("fecha_antes_ayer")
        context = _make_context()

        result = await handle_fecha_antes_ayer(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        override = context.user_data.get("fecha_venta_override")
        assert override is not None
        antes_ayer = datetime.date.today() - datetime.timedelta(days=2)
        assert isinstance(override, datetime.datetime)
        assert override.date() == antes_ayer


# ---------------------------------------------------------------------------
# F. handle_fecha_retroactiva_texto valid
# ---------------------------------------------------------------------------


class TestFechaRetroactivaTextoValido:
    @pytest.mark.asyncio
    async def test_texto_valido_guarda_override_y_procede(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import (
            handle_fecha_retroactiva_texto,
        )

        update = _make_update_text("15/09/2026")
        context = _make_context()

        result = await handle_fecha_retroactiva_texto(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        override = context.user_data.get("fecha_venta_override")
        assert isinstance(override, datetime.datetime)
        assert override.day == 15
        assert override.month == 9
        assert override.year == 2026


# ---------------------------------------------------------------------------
# F2. handle_fecha_retroactiva_texto sets registrante_privilegiado
# ---------------------------------------------------------------------------


class TestFechaRetroactivaTextoSetRegistrantePrivilegiado:
    @pytest.mark.asyncio
    async def test_admin_sets_privilegiado_true(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import (
            handle_fecha_retroactiva_texto,
        )

        update = _make_update_text("15/09/2026")
        context = _make_context(es_admin=True)

        result = await handle_fecha_retroactiva_texto(update, context)

        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
        ctx = context.user_data.get("contexto")
        assert isinstance(ctx, ContextoVenta)
        assert ctx.registrante_privilegiado is True


# ---------------------------------------------------------------------------
# G. handle_fecha_retroactiva_texto invalid
# ---------------------------------------------------------------------------


class TestFechaRetroactivaTextoInvalido:
    @pytest.mark.asyncio
    async def test_texto_invalido_repregunta(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import (
            FECHA_RETROACTIVA_TEXTO,
            handle_fecha_retroactiva_texto,
        )

        update = _make_update_text("no-es-fecha")
        context = _make_context()

        result = await handle_fecha_retroactiva_texto(update, context)

        assert result == FECHA_RETROACTIVA_TEXTO
        assert context.user_data.get("fecha_venta_override") is None


# ---------------------------------------------------------------------------
# H. handle_inicio_volver cleans override and goes back
# ---------------------------------------------------------------------------


class TestIniciVolverLimpiaOverride:
    @pytest.mark.asyncio
    async def test_limpia_override_y_vuelve_a_inicio(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import (
            INICIO_VENTA,
            handle_inicio_volver,
        )

        update = _make_update_cb("inicio_volver")
        context = _make_context(
            user_data_extra={"fecha_venta_override": datetime.datetime(2026, 9, 10)}
        )

        result = await handle_inicio_volver(update, context)

        assert result == INICIO_VENTA
        assert "fecha_venta_override" not in context.user_data


# ---------------------------------------------------------------------------
# I. handle_fecha_salida auto-fills when override is present
# ---------------------------------------------------------------------------


class TestFechaSalidaAutoFillCuandoHayOverride:
    @pytest.mark.asyncio
    async def test_autofill_con_override_no_pregunta_fecha(self) -> None:
        """When fecha_venta_override is in user_data, handle_fecha_salida must
        consume it and NOT return FECHA_SALIDA (it must advance to the next state)."""
        from garay.infraestructura.telegram.handlers import handle_fecha_salida

        override_dt = datetime.datetime(2026, 9, 10, 0, 0)
        ctx = ContextoVenta(
            destinos_numeros=[1],
            tipo_cliente=TipoCliente.EXTERNO,
        )

        update = _make_update_cb("IGNORED")
        context = _make_context(
            ctx=ctx,
            user_data_extra={"fecha_venta_override": override_dt},
        )

        result = await handle_fecha_salida(update, context)

        # Must NOT stay on FECHA_SALIDA
        assert result != ESTADO_PTB[EstadoFSM.FECHA_SALIDA]
        # Override must be consumed
        assert "fecha_venta_override" not in context.user_data


# ---------------------------------------------------------------------------
# SC-05 / SC-06. Stale-callback guard in handle_inicio_otra_fecha
# ---------------------------------------------------------------------------


class TestHandleInicioOtraFecha:
    @pytest.mark.asyncio
    async def test_sc05_freelancer_stale_callback_retorna_inicio_venta(self) -> None:
        """SC-05: FREELANCER stale callback — INICIO_VENTA, alert shown, no override."""
        from garay.infraestructura.telegram.handlers_inicio_venta import (
            INICIO_VENTA,
            handle_inicio_otra_fecha,
        )

        update = _make_update_cb("inicio_otra_fecha")
        context = _make_context(es_admin=False)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=False)):
            result = await handle_inicio_otra_fecha(update, context)

        assert result == INICIO_VENTA
        update.callback_query.answer.assert_called_once()
        call_kwargs = update.callback_query.answer.call_args
        assert call_kwargs.kwargs.get("show_alert") is True or (
            len(call_kwargs.args) > 0
            and call_kwargs.kwargs.get("show_alert") is True
        )
        assert "fecha_venta_override" not in context.user_data

    @pytest.mark.asyncio
    async def test_sc06_admin_muestra_sub_picker(self) -> None:
        """SC-06: ADMIN callback — returns FECHA_RETROACTIVA, edit_message_text called."""
        from garay.infraestructura.telegram.handlers_inicio_venta import (
            FECHA_RETROACTIVA,
            handle_inicio_otra_fecha,
        )

        update = _make_update_cb("inicio_otra_fecha")
        context = _make_context(es_admin=True)

        with patch(_PATCH_ES_ADMIN, new=AsyncMock(return_value=True)):
            result = await handle_inicio_otra_fecha(update, context)

        assert result == FECHA_RETROACTIVA
        update.callback_query.edit_message_text.assert_called_once()


# ---------------------------------------------------------------------------
# SC-13. venta.retroactiva_sin_acceso message key exists in catalog
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# SC-11 / SC-12. _teclado_inicio unit tests
# ---------------------------------------------------------------------------


class TestTecladoInicio:
    def test_sin_otra_fecha_una_sola_fila(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import _teclado_inicio

        markup = _teclado_inicio(mostrar_otra_fecha=False)
        assert len(markup.inline_keyboard) == 1
        assert markup.inline_keyboard[0][0].callback_data == "inicio_hoy"

    def test_con_otra_fecha_dos_filas(self) -> None:
        from garay.infraestructura.telegram.handlers_inicio_venta import _teclado_inicio

        markup = _teclado_inicio(mostrar_otra_fecha=True)
        flat = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "inicio_hoy" in flat
        assert "inicio_otra_fecha" in flat


class TestMensajeRetroactivaSinAcceso:
    def test_clave_retroactiva_sin_acceso_existe(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje

        msg = obtener_mensaje("venta.retroactiva_sin_acceso")
        assert msg and isinstance(msg, str)
