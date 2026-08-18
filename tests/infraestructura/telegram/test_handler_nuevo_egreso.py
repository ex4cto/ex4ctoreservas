"""Tests for /nuevo_egreso ConversationHandler — RED phase."""

from __future__ import annotations

import datetime
import uuid as _uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers_egresos import (
    CB_CANCELAR_SEL,
    CB_HOY,
    CB_OTRO_EGRESO,
    CB_USAR_SUGERIDO,
    EGRESO_CATEGORIA,
    EGRESO_CONFIRMACION,
    EGRESO_DESCRIPCION,
    EGRESO_FECHA,
    EGRESO_MONTO,
    EGRESO_REC_CONFIRM,
    EGRESO_REC_FECHA,
    EGRESO_REC_MONTO,
    EGRESO_SELECCION,
    PREFIJO_REC,
    cmd_nuevo_egreso,
    handle_egreso_categoria,
    handle_egreso_confirmacion,
    handle_egreso_descripcion,
    handle_egreso_fecha,
    handle_egreso_monto,
    handle_egreso_rec_confirmacion,
    handle_egreso_rec_fecha,
    handle_egreso_rec_monto,
    handle_egreso_seleccion,
)


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    if text is not None:
        update.message = MagicMock()
        update.message.text = text
        update.callback_query = None
    elif callback_data is not None:
        update.message = None
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
    else:
        update.message = None
        update.callback_query = None
    return update


def _make_admin_repo() -> MagicMock:
    """Freelancer repo whose lookup returns an admin — satisfies requiere_admin_conv."""
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = True
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_context(
    categorias: list[str] | None = None,
    gastos_recurrentes: list[object] | None = None,
    egreso_repo: object | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    service = MagicMock()
    service.listar_categorias.return_value = categorias or ["arriendo", "nomina", "otro"]
    recurrente_service = MagicMock()
    recurrente_service.listar_activos.return_value = gastos_recurrentes or []
    ctx.bot_data = {
        "egreso_service": service,
        "recurrente_service": recurrente_service,
        "freelancer_repo": _make_admin_repo(),
        "egreso_repo": egreso_repo,
    }
    return ctx


class TestCmdNuevoEgreso:
    @pytest.mark.asyncio
    async def test_inicia_y_pide_seleccion(self) -> None:
        update = _make_update()
        ctx = _make_context()
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == EGRESO_SELECCION
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_admin_es_denegado(self) -> None:
        """Non-admin user → requiere_admin_conv ends the conversation, no monto prompt."""
        update = _make_update()
        ctx = _make_context()
        repo = ctx.bot_data["freelancer_repo"]
        repo.buscar_por_telegram_id.return_value.es_admin = False
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == ConversationHandler.END


class TestHandleEgresoMonto:
    @pytest.mark.asyncio
    async def test_monto_valido_avanza(self) -> None:
        update = _make_update(text="50")  # 50 → 50000
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_DESCRIPCION
        assert ctx.user_data["egreso_monto"] == Decimal("50000")

    @pytest.mark.asyncio
    async def test_monto_invalido_repite_estado(self) -> None:
        update = _make_update(text="abc")
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_MONTO

    @pytest.mark.asyncio
    async def test_monto_escrito_completo(self) -> None:
        update = _make_update(text="500000")
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_DESCRIPCION
        assert ctx.user_data["egreso_monto"] == Decimal("500000")

    @pytest.mark.asyncio
    async def test_monto_con_puntos(self) -> None:
        update = _make_update(text="500.000")
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_DESCRIPCION
        assert ctx.user_data["egreso_monto"] == Decimal("500000")


class TestHandleEgresoDescripcion:
    @pytest.mark.asyncio
    async def test_guarda_descripcion_y_avanza(self) -> None:
        update = _make_update(text="Pago arriendo")
        ctx = _make_context()
        result = await handle_egreso_descripcion(update, ctx)
        assert result == EGRESO_CATEGORIA
        assert ctx.user_data["egreso_descripcion"] == "Pago arriendo"

    @pytest.mark.asyncio
    async def test_muestra_botones_de_categorias(self) -> None:
        update = _make_update(text="Gasto")
        ctx = _make_context(categorias=["arriendo", "otro"])
        await handle_egreso_descripcion(update, ctx)
        update.effective_message.reply_text.assert_called_once()


class TestHandleEgresoCategoria:
    @pytest.mark.asyncio
    async def test_categoria_valida_avanza(self) -> None:
        update = _make_update(callback_data="arriendo")
        ctx = _make_context()
        result = await handle_egreso_categoria(update, ctx)
        assert result == EGRESO_FECHA
        assert ctx.user_data["egreso_categoria"] == "arriendo"

    @pytest.mark.asyncio
    async def test_categoria_invalida_repite(self) -> None:
        update = _make_update(callback_data="inexistente")
        ctx = _make_context(categorias=["arriendo"])
        result = await handle_egreso_categoria(update, ctx)
        assert result == EGRESO_CATEGORIA


class TestHandleEgresoFecha:
    @pytest.mark.asyncio
    async def test_fecha_hoy_texto_invalido(self) -> None:
        update = _make_update(text="hoy")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_FECHA  # parser rejects "hoy" as text

    @pytest.mark.asyncio
    async def test_fecha_hoy_boton(self) -> None:
        update = _make_update(callback_data="egr_hoy")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        assert ctx.user_data["egreso_fecha"] == datetime.date.today()

    @pytest.mark.asyncio
    async def test_fecha_ddmm(self) -> None:
        update = _make_update(text="01/07")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        stored = ctx.user_data["egreso_fecha"]
        assert stored.day == 1
        assert stored.month == 7

    @pytest.mark.asyncio
    async def test_fecha_completa(self) -> None:
        update = _make_update(text="15/06/2026")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        assert ctx.user_data["egreso_fecha"] == datetime.date(2026, 6, 15)

    @pytest.mark.asyncio
    async def test_fecha_invalida_repite(self) -> None:
        update = _make_update(text="noesuna fecha")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_FECHA


class TestHandleEgresoConfirmacion:
    @pytest.mark.asyncio
    async def test_confirmar_llama_service_y_termina(self) -> None:
        update = _make_update(callback_data="confirmar")
        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("500000"),
                "egreso_descripcion": "Arriendo",
                "egreso_categoria": "arriendo",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        result = await handle_egreso_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        service.registrar.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancelar_termina_sin_registrar(self) -> None:
        update = _make_update(callback_data="cancelar")
        ctx = _make_context()
        result = await handle_egreso_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        service.registrar.assert_not_called()


class TestCmdNuevoEgresoSeleccion:
    @pytest.mark.asyncio
    async def test_muestra_botones_recurrentes_y_otro(self) -> None:
        gasto = MagicMock()
        gasto.id = _uuid.uuid4()
        gasto.nombre = "Arriendo"
        gasto.categoria = "arriendo"
        gasto.monto.monto = Decimal("800000")
        ctx = _make_context(gastos_recurrentes=[gasto])
        update = _make_update()
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == EGRESO_SELECCION
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_estado_vacio_solo_muestra_otro(self) -> None:
        ctx = _make_context(gastos_recurrentes=[])
        update = _make_update()
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == EGRESO_SELECCION
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_seleccion_cancelar_termina(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_CANCELAR_SEL)
        result = await handle_egreso_seleccion(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_seleccion_otro_egreso_va_a_monto(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_OTRO_EGRESO)
        result = await handle_egreso_seleccion(update, ctx)
        assert result == EGRESO_MONTO

    @pytest.mark.asyncio
    async def test_seleccion_recurrente_guarda_datos_y_pide_monto(self) -> None:
        rec_id = _uuid.uuid4()
        gasto = MagicMock()
        gasto.id = rec_id
        gasto.nombre = "Arriendo"
        gasto.categoria = "arriendo"
        gasto.monto.monto = Decimal("800000")
        ctx = _make_context(gastos_recurrentes=[gasto])
        update = _make_update(callback_data=f"{PREFIJO_REC}{rec_id}")
        result = await handle_egreso_seleccion(update, ctx)
        assert result == EGRESO_REC_MONTO
        assert ctx.user_data["rec_id"] == rec_id
        assert ctx.user_data["rec_nombre"] == "Arriendo"
        assert ctx.user_data["rec_categoria"] == "arriendo"
        assert ctx.user_data["rec_monto_sugerido"] == Decimal("800000")


class TestHandleEgresoRecMonto:
    @pytest.mark.asyncio
    async def test_usar_sugerido_avanza(self) -> None:
        ctx = _make_context()
        ctx.user_data["rec_monto_sugerido"] = Decimal("800000")
        update = _make_update(callback_data=CB_USAR_SUGERIDO)
        result = await handle_egreso_rec_monto(update, ctx)
        assert result == EGRESO_REC_FECHA
        assert ctx.user_data["rec_monto"] == Decimal("800000")

    @pytest.mark.asyncio
    async def test_monto_override_avanza(self) -> None:
        ctx = _make_context()
        ctx.user_data["rec_monto_sugerido"] = Decimal("800000")
        update = _make_update(text="50")  # 50 → 50000
        result = await handle_egreso_rec_monto(update, ctx)
        assert result == EGRESO_REC_FECHA
        assert ctx.user_data["rec_monto"] == Decimal("50000")

    @pytest.mark.asyncio
    async def test_monto_invalido_repite(self) -> None:
        ctx = _make_context()
        ctx.user_data["rec_monto_sugerido"] = Decimal("800000")
        update = _make_update(text="abc")
        result = await handle_egreso_rec_monto(update, ctx)
        assert result == EGRESO_REC_MONTO

    @pytest.mark.asyncio
    async def test_usar_sugerido_sin_estado_termina(self) -> None:
        # State lost (e.g. bot redeploy): no rec_monto_sugerido → end, never register 0.
        ctx = _make_context()
        update = _make_update(callback_data=CB_USAR_SUGERIDO)
        result = await handle_egreso_rec_monto(update, ctx)
        assert result == ConversationHandler.END
        assert "rec_monto" not in ctx.user_data


class TestHandleEgresoRecFecha:
    @pytest.mark.asyncio
    async def test_hoy_boton_avanza(self) -> None:
        ctx = _make_context()
        ctx.user_data.update(
            {"rec_nombre": "Arriendo", "rec_monto": Decimal("800000"), "rec_categoria": "arriendo"}
        )
        update = _make_update(callback_data=CB_HOY)
        result = await handle_egreso_rec_fecha(update, ctx)
        assert result == EGRESO_REC_CONFIRM
        assert ctx.user_data["rec_fecha"] == datetime.date.today()

    @pytest.mark.asyncio
    async def test_fecha_valida_avanza(self) -> None:
        ctx = _make_context()
        ctx.user_data.update(
            {"rec_nombre": "Arriendo", "rec_monto": Decimal("800000"), "rec_categoria": "arriendo"}
        )
        update = _make_update(text="15/06/2026")
        result = await handle_egreso_rec_fecha(update, ctx)
        assert result == EGRESO_REC_CONFIRM
        assert ctx.user_data["rec_fecha"] == datetime.date(2026, 6, 15)

    @pytest.mark.asyncio
    async def test_fecha_invalida_repite(self) -> None:
        ctx = _make_context()
        update = _make_update(text="noesuna")
        result = await handle_egreso_rec_fecha(update, ctx)
        assert result == EGRESO_REC_FECHA


class TestHandleEgresoRecConfirmacion:
    @pytest.mark.asyncio
    async def test_confirmar_persiste_egreso_con_gasto_recurrente_id(self) -> None:
        import uuid as _uuid2
        rec_id = _uuid2.uuid4()
        ctx = _make_context()
        ctx.user_data.update({
            "rec_id": rec_id,
            "rec_nombre": "Arriendo",
            "rec_categoria": "arriendo",
            "rec_monto": Decimal("800000"),
            "rec_fecha": datetime.date(2026, 7, 1),
        })
        update = _make_update(callback_data="confirmar")
        result = await handle_egreso_rec_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        call_kwargs = service.registrar.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("gasto_recurrente_id") == rec_id
        assert call_kwargs.kwargs.get("categoria") == "arriendo"
        assert call_kwargs.kwargs.get("descripcion") == "Arriendo"

    @pytest.mark.asyncio
    async def test_cancelar_termina_sin_registrar(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data="cancelar")
        result = await handle_egreso_rec_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        service.registrar.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirmar_sin_estado_no_registra(self) -> None:
        # State lost mid-flow: required keys missing → end, never call registrar.
        ctx = _make_context()
        update = _make_update(callback_data="confirmar")
        result = await handle_egreso_rec_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        service.registrar.assert_not_called()


class TestPaidIndicator:
    """Feature A: paid-this-month indicator on selection buttons."""

    @pytest.mark.asyncio
    async def test_button_shows_indicator_when_paid_this_month(self) -> None:
        rec_id = _uuid.uuid4()
        gasto = MagicMock()
        gasto.id = rec_id
        gasto.nombre = "Arriendo"
        gasto.categoria = "arriendo"
        gasto.monto.monto = Decimal("800000")

        egreso_repo = MagicMock()
        pagado = MagicMock()
        pagado.monto = Decimal("800000")
        egreso_repo.sumar_por_recurrente_en_mes.return_value = pagado

        ctx = _make_context(gastos_recurrentes=[gasto], egreso_repo=egreso_repo)

        update = _make_update()
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == EGRESO_SELECCION

        call_args = update.effective_message.reply_text.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1]
        labels = [btn.text for row in markup.inline_keyboard for btn in row]
        assert any("✅" in label and "Arriendo" in label for label in labels)

    @pytest.mark.asyncio
    async def test_button_plain_label_when_not_paid(self) -> None:
        rec_id = _uuid.uuid4()
        gasto = MagicMock()
        gasto.id = rec_id
        gasto.nombre = "Servicio"
        gasto.categoria = "servicios"
        gasto.monto.monto = Decimal("200000")

        egreso_repo = MagicMock()
        pagado = MagicMock()
        pagado.monto = Decimal("0")
        egreso_repo.sumar_por_recurrente_en_mes.return_value = pagado

        ctx = _make_context(gastos_recurrentes=[gasto], egreso_repo=egreso_repo)

        update = _make_update()
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == EGRESO_SELECCION

        call_args = update.effective_message.reply_text.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1]
        labels = [btn.text for row in markup.inline_keyboard for btn in row]
        servicio_labels = [lb for lb in labels if "Servicio" in lb]
        assert len(servicio_labels) == 1
        assert "✅" not in servicio_labels[0] or "este mes" not in servicio_labels[0]

    @pytest.mark.asyncio
    async def test_button_isolation_paid_a_does_not_affect_b(self) -> None:
        id_a = _uuid.uuid4()
        id_b = _uuid.uuid4()
        gasto_a = MagicMock()
        gasto_a.id = id_a
        gasto_a.nombre = "Arriendo"
        gasto_a.categoria = "arriendo"
        gasto_a.monto.monto = Decimal("800000")
        gasto_b = MagicMock()
        gasto_b.id = id_b
        gasto_b.nombre = "Internet"
        gasto_b.categoria = "servicios"
        gasto_b.monto.monto = Decimal("100000")

        egreso_repo = MagicMock()

        def suma_side_effect(gid, *args):  # type: ignore[no-untyped-def]
            m = MagicMock()
            m.monto = Decimal("800000") if gid == id_a else Decimal("0")
            return m

        egreso_repo.sumar_por_recurrente_en_mes.side_effect = suma_side_effect

        ctx = _make_context(gastos_recurrentes=[gasto_a, gasto_b], egreso_repo=egreso_repo)

        update = _make_update()
        await cmd_nuevo_egreso(update, ctx)

        call_args = update.effective_message.reply_text.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1]
        labels = [btn.text for row in markup.inline_keyboard for btn in row]

        arriendo_labels = [lb for lb in labels if "Arriendo" in lb]
        internet_labels = [lb for lb in labels if "Internet" in lb]
        assert len(arriendo_labels) == 1 and "este mes" in arriendo_labels[0]
        assert len(internet_labels) == 1 and "este mes" not in internet_labels[0]

    @pytest.mark.asyncio
    async def test_button_still_tappable_when_paid(self) -> None:
        """Paying again (partial/duplicate) must still be possible — button not hidden."""
        rec_id = _uuid.uuid4()
        gasto = MagicMock()
        gasto.id = rec_id
        gasto.nombre = "Arriendo"
        gasto.categoria = "arriendo"
        gasto.monto.monto = Decimal("800000")

        egreso_repo = MagicMock()
        pagado = MagicMock()
        pagado.monto = Decimal("800000")
        egreso_repo.sumar_por_recurrente_en_mes.return_value = pagado

        ctx = _make_context(gastos_recurrentes=[gasto], egreso_repo=egreso_repo)

        update = _make_update()
        await cmd_nuevo_egreso(update, ctx)

        call_args = update.effective_message.reply_text.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1]
        rec_callbacks = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
            if str(rec_id) in (btn.callback_data or "")
        ]
        assert len(rec_callbacks) == 1


class TestEditarOtro:
    """Feature B: edit flow for 'Otro' branch."""

    @pytest.mark.asyncio
    async def test_confirmacion_muestra_boton_editar(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_EDITAR,
            handle_egreso_fecha,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("500000"),
                "egreso_descripcion": "Test",
                "egreso_categoria": "arriendo",
            }
        )
        update = _make_update(callback_data=CB_HOY)
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION

        call_args = update.callback_query.edit_message_text.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1]
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert CB_EDITAR in callbacks

    @pytest.mark.asyncio
    async def test_editar_en_confirmacion_va_a_edit_menu(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_EDITAR,
            EGRESO_EDIT_MENU,
            handle_egreso_confirmacion,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("500000"),
                "egreso_descripcion": "Test",
                "egreso_categoria": "arriendo",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        update = _make_update(callback_data=CB_EDITAR)
        result = await handle_egreso_confirmacion(update, ctx)
        assert result == EGRESO_EDIT_MENU

    @pytest.mark.asyncio
    async def test_edit_monto_actualiza_y_vuelve_a_confirmacion(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            EGRESO_CONFIRMACION,
            handle_egreso_monto,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("500000"),
                "egreso_descripcion": "Test",
                "egreso_categoria": "arriendo",
                "egreso_fecha": datetime.date(2026, 7, 1),
                "editando": True,
            }
        )
        update = _make_update(text="600")  # 600 → 600000
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_CONFIRMACION
        assert ctx.user_data["egreso_monto"] == Decimal("600000")
        assert not ctx.user_data.get("editando")

    @pytest.mark.asyncio
    async def test_volver_en_edit_menu_regresa_a_confirmacion(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_EDIT_VOLVER,
            EGRESO_CONFIRMACION,
            handle_egreso_edit_menu,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("500000"),
                "egreso_descripcion": "Test",
                "egreso_categoria": "arriendo",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        update = _make_update(callback_data=CB_EDIT_VOLVER)
        result = await handle_egreso_edit_menu(update, ctx)
        assert result == EGRESO_CONFIRMACION

    @pytest.mark.asyncio
    async def test_confirmar_persiste_edited_values(self) -> None:
        """After editing monto, final Confirmar persists the NEW value."""
        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("600000"),  # already edited
                "egreso_descripcion": "Test",
                "egreso_categoria": "arriendo",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        update = _make_update(callback_data="confirmar")
        result = await handle_egreso_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        call_kwargs = service.registrar.call_args
        assert call_kwargs.kwargs.get("monto") == Decimal("600000")


class TestEditarRecurrente:
    """Feature B: edit flow for recurring branch."""

    @pytest.mark.asyncio
    async def test_rec_confirmacion_muestra_boton_editar(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_EDITAR,
            handle_egreso_rec_fecha,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "rec_nombre": "Arriendo",
                "rec_monto": Decimal("800000"),
                "rec_categoria": "arriendo",
            }
        )
        update = _make_update(callback_data=CB_HOY)
        result = await handle_egreso_rec_fecha(update, ctx)
        assert result == EGRESO_REC_CONFIRM

        call_args = update.callback_query.edit_message_text.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1]
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert CB_EDITAR in callbacks

    @pytest.mark.asyncio
    async def test_rec_editar_va_a_edit_menu(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_EDITAR,
            EGRESO_REC_EDIT_MENU,
            handle_egreso_rec_confirmacion,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "rec_id": _uuid.uuid4(),
                "rec_nombre": "Arriendo",
                "rec_categoria": "arriendo",
                "rec_monto": Decimal("800000"),
                "rec_fecha": datetime.date(2026, 7, 1),
            }
        )
        update = _make_update(callback_data=CB_EDITAR)
        result = await handle_egreso_rec_confirmacion(update, ctx)
        assert result == EGRESO_REC_EDIT_MENU

    @pytest.mark.asyncio
    async def test_rec_edit_monto_actualiza_y_vuelve_a_confirmacion(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            EGRESO_REC_CONFIRM,
            handle_egreso_rec_monto,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "rec_monto_sugerido": Decimal("800000"),
                "rec_nombre": "Arriendo",
                "rec_categoria": "arriendo",
                "rec_fecha": datetime.date(2026, 7, 1),
                "editando": True,
            }
        )
        update = _make_update(text="900")  # 900 → 900000
        result = await handle_egreso_rec_monto(update, ctx)
        assert result == EGRESO_REC_CONFIRM
        assert ctx.user_data["rec_monto"] == Decimal("900000")
        assert not ctx.user_data.get("editando")

    @pytest.mark.asyncio
    async def test_rec_volver_regresa_a_confirmacion(self) -> None:
        from garay.infraestructura.telegram.handlers_egresos import (
            CB_EDIT_VOLVER,
            EGRESO_REC_CONFIRM,
            handle_egreso_rec_edit_menu,
        )

        ctx = _make_context()
        ctx.user_data.update(
            {
                "rec_nombre": "Arriendo",
                "rec_monto": Decimal("800000"),
                "rec_categoria": "arriendo",
                "rec_fecha": datetime.date(2026, 7, 1),
            }
        )
        update = _make_update(callback_data=CB_EDIT_VOLVER)
        result = await handle_egreso_rec_edit_menu(update, ctx)
        assert result == EGRESO_REC_CONFIRM

    @pytest.mark.asyncio
    async def test_rec_confirmar_persiste_edited_monto(self) -> None:
        """After editing rec_monto, final Confirmar persists the NEW value."""
        rec_id = _uuid.uuid4()
        ctx = _make_context()
        ctx.user_data.update(
            {
                "rec_id": rec_id,
                "rec_nombre": "Arriendo",
                "rec_categoria": "arriendo",
                "rec_monto": Decimal("900000"),  # edited
                "rec_fecha": datetime.date(2026, 7, 1),
            }
        )
        update = _make_update(callback_data="confirmar")
        result = await handle_egreso_rec_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        call_kwargs = service.registrar.call_args
        assert call_kwargs.kwargs.get("monto") == Decimal("900000")
        assert call_kwargs.kwargs.get("gasto_recurrente_id") == rec_id

