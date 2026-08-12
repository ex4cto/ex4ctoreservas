"""Tests for /gestionar_ventas ConversationHandler — B2 + B3 (TDD)."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_CONFIRMAR,
    GV_DETALLE,
    GV_EDIT_FECHA,
    GV_MOTIVO,
    GV_SELECCIONAR,
    cmd_gestionar_ventas,
    handle_gv_confirmar,
    handle_gv_detalle,
    handle_gv_edit_fecha,
    handle_gv_motivo,
    handle_gv_seleccionar,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_venta(
    venta_id: uuid.UUID | None = None,
    cliente_id: uuid.UUID | None = None,
    fecha: datetime.date | None = None,
    valor_monto: float = 500_000,
) -> MagicMock:
    v = MagicMock()
    v.id = venta_id or uuid.uuid4()
    v.cliente_id = cliente_id or uuid.uuid4()
    v.servicio_ids = [uuid.uuid4()]
    v.fecha = fecha or datetime.date(2026, 8, 1)
    v.valor_venta = MagicMock()
    v.valor_venta.monto = valor_monto
    return v


def _make_update(
    user_id: int = 123,
    callback_data: str | None = None,
    text: str | None = None,
) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.message = None
    elif text is not None:
        update.callback_query = None
        update.message = MagicMock()
        update.message.text = text
    else:
        update.callback_query = None
        update.message = None
    return update


def _make_admin_freelancer() -> MagicMock:
    f = MagicMock()
    f.es_admin = True
    f.nombre = "Admin"
    return f


def _make_context(
    ventas: list[MagicMock] | None = None,
    freelancer: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}

    venta_repo = MagicMock()
    venta_repo.listar_por_periodo.return_value = ventas or []

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer or _make_admin_freelancer()

    cliente_repo = MagicMock()
    cliente = MagicMock()
    cliente.nombre = "Juan Perez"
    cliente_repo.buscar_por_id.return_value = cliente

    servicio_repo = MagicMock()
    servicio = MagicMock()
    servicio.nombre = "Tour Isla"
    servicio_repo.buscar_por_id.return_value = servicio

    anular_service = MagicMock()
    editar_fecha_service = MagicMock()
    notificador = MagicMock()

    ctx.bot_data = {
        "venta_repo": venta_repo,
        "freelancer_repo": freelancer_repo,
        "cliente_repo": cliente_repo,
        "servicio_repo": servicio_repo,
        "anular_venta_service": anular_service,
        "editar_fecha_venta_service": editar_fecha_service,
        "notificador": notificador,
        "grupo_id": "-1001234567",
    }
    return ctx


# ---------------------------------------------------------------------------
# cmd_gestionar_ventas
# ---------------------------------------------------------------------------


class TestCmdGestionarVentas:
    @pytest.mark.asyncio
    async def test_sin_ventas_reply_y_end(self) -> None:
        update = _make_update()
        ctx = _make_context(ventas=[])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_con_ventas_muestra_botones_y_retorna_gv_seleccionar(self) -> None:
        ventas = [_make_venta(), _make_venta()]
        update = _make_update()
        ctx = _make_context(ventas=ventas)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == GV_SELECCIONAR
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_admin_no_propietario_devuelve_end(self) -> None:
        no_admin = MagicMock()
        no_admin.es_admin = False
        update = _make_update(user_id=999)
        ctx = _make_context(freelancer=no_admin)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == ConversationHandler.END
        # repo must NOT have been called because auth denied early
        ctx.bot_data["venta_repo"].listar_por_periodo.assert_not_called()


# ---------------------------------------------------------------------------
# handle_gv_seleccionar
# ---------------------------------------------------------------------------


class TestHandleGvSeleccionar:
    @pytest.mark.asyncio
    async def test_seleccionar_venta_valida_retorna_gv_detalle(self) -> None:
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_seleccionar(update, ctx)

        assert result == GV_DETALLE
        assert ctx.user_data["gv_venta_id"] == str(venta.id)

    @pytest.mark.asyncio
    async def test_seleccionar_venta_no_encontrada_retorna_end(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data=f"gv_sel:{venta_id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = None

        result = await handle_gv_seleccionar(update, ctx)

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# handle_gv_detalle
# ---------------------------------------------------------------------------


class TestHandleGvDetalle:
    @pytest.mark.asyncio
    async def test_gv_anular_retorna_gv_motivo(self) -> None:
        update = _make_update(callback_data="gv_anular")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_MOTIVO

    @pytest.mark.asyncio
    async def test_gv_cancelar_retorna_end(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# handle_gv_motivo
# ---------------------------------------------------------------------------


class TestHandleGvMotivo:
    @pytest.mark.asyncio
    async def test_motivo_vacio_stays_en_gv_motivo(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_MOTIVO

    @pytest.mark.asyncio
    async def test_motivo_vacio_reply_error(self) -> None:
        update = _make_update(text="")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_MOTIVO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_motivo_valido_guarda_y_retorna_gv_confirmar(self) -> None:
        update = _make_update(text="Cliente cambio de planes")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_CONFIRMAR
        assert ctx.user_data["gv_motivo"] == "Cliente cambio de planes"

    @pytest.mark.asyncio
    async def test_motivo_editar_branch_retorna_gv_confirmar_con_confirmar_editar(self) -> None:
        """FIX 2: editar branch must return GV_CONFIRMAR and reply with confirmar_editar text."""
        from garay.mensajes.catalogo import obtener_mensaje

        venta_id = uuid.uuid4()
        nueva_fecha = datetime.datetime(2026, 9, 20, 10, 30)
        update = _make_update(text="Pasajero cambio de disponibilidad")
        ctx = _make_context()
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha.isoformat()
        ctx.user_data["gv_venta_id"] = str(venta_id)

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_CONFIRMAR
        expected_text = obtener_mensaje("gestion_ventas.confirmar_editar").format(
            fecha=f"{nueva_fecha:%d/%m/%Y %H:%M}",
            motivo="Pasajero cambio de disponibilidad",
        )
        update.effective_message.reply_text.assert_called_once_with(
            expected_text,
            reply_markup=update.effective_message.reply_text.call_args[1]["reply_markup"],
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# handle_gv_confirmar
# ---------------------------------------------------------------------------


class TestHandleGvConfirmar:
    @pytest.mark.asyncio
    async def test_cancelar_retorna_end(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancelar_limpia_user_data(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = "some-id"
        ctx.user_data["gv_motivo"] = "some-motivo"

        await handle_gv_confirmar(update, ctx)

        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_llama_servicio_y_retorna_end(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"
        ctx.user_data["gv_accion"] = "anular"

        from garay.aplicacion.ventas.comandos import AnularVentaComando

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        service = ctx.bot_data["anular_venta_service"]
        service.ejecutar.assert_called_once()
        cmd: AnularVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.motivo == "Motivo de prueba"
        assert cmd.realizada_por_telegram_id == 123

    @pytest.mark.asyncio
    async def test_confirmar_exitoso_limpia_user_data(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"
        ctx.user_data["gv_accion"] = "anular"

        await handle_gv_confirmar(update, ctx)

        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_venta_ya_anulada_reply_error_y_end(self) -> None:
        from garay.dominio.ventas.errores import VentaYaAnulada

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = VentaYaAnulada("ya anulada")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_venta_no_encontrada_reply_error_y_end(self) -> None:
        from garay.dominio.ventas.errores import VentaNoEncontrada

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = VentaNoEncontrada("no")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_generic_exception_reply_error_generico_y_end(self) -> None:
        """FIX 3: a generic RuntimeError must reply error_generico and return END."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = RuntimeError("DB exploded")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()


class TestCmdGestionarVentasClearsStaleKeys:
    @pytest.mark.asyncio
    async def test_entry_clears_stale_gv_keys(self) -> None:
        """FIX 2: cmd_gestionar_ventas must pop stale gv_* keys before listing ventas."""
        ventas = [_make_venta()]
        update = _make_update()
        ctx = _make_context(ventas=ventas)
        # Pre-seed stale keys from a previous conversation run.
        ctx.user_data["gv_venta_id"] = "old-id"
        ctx.user_data["gv_motivo"] = "old-motivo"

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            await cmd_gestionar_ventas(update, ctx)

        # Keys must be absent regardless of conversation outcome.
        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data


# ---------------------------------------------------------------------------
# B3: handle_gv_detalle — gv_editar branch
# ---------------------------------------------------------------------------


class TestHandleGvDetalleEditar:
    @pytest.mark.asyncio
    async def test_gv_editar_retorna_gv_edit_fecha(self) -> None:
        """gv_editar dispatch must return GV_EDIT_FECHA and set gv_accion='editar'."""
        update = _make_update(callback_data="gv_editar")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_EDIT_FECHA
        assert ctx.user_data.get("gv_accion") == "editar"

    @pytest.mark.asyncio
    async def test_gv_anular_sets_accion_anular(self) -> None:
        """Regression: gv_anular still goes to GV_MOTIVO and sets gv_accion='anular'."""
        update = _make_update(callback_data="gv_anular")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_accion") == "anular"


# ---------------------------------------------------------------------------
# B3: handle_gv_edit_fecha
# ---------------------------------------------------------------------------


class TestHandleGvEditFecha:
    @pytest.mark.asyncio
    async def test_fecha_invalida_stays_gv_edit_fecha(self) -> None:
        """Non-parseable text must reply fecha_invalida and stay in GV_EDIT_FECHA."""
        update = _make_update(text="no es una fecha")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_EDIT_FECHA
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_fecha_invalida_formato_incorrecto(self) -> None:
        """Triangulation: another bad format also stays in GV_EDIT_FECHA."""
        update = _make_update(text="2026-09-20")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_EDIT_FECHA

    @pytest.mark.asyncio
    async def test_fecha_valida_guarda_y_retorna_gv_motivo(self) -> None:
        """Valid date text must store gv_nueva_fecha (ISO) and return GV_MOTIVO."""
        update = _make_update(text="20/09/2026 10:30")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_MOTIVO
        assert "gv_nueva_fecha" in ctx.user_data

    @pytest.mark.asyncio
    async def test_fecha_valida_sin_hora_retorna_gv_motivo(self) -> None:
        """Triangulation: DD/MM/YYYY (no time) must also advance to GV_MOTIVO."""
        update = _make_update(text="20/09/2026")
        ctx = _make_context()

        result = await handle_gv_edit_fecha(update, ctx)

        assert result == GV_MOTIVO
        assert "gv_nueva_fecha" in ctx.user_data

    @pytest.mark.asyncio
    async def test_fecha_valida_iso_stored_correctly(self) -> None:
        """The stored gv_nueva_fecha must be parseable back to datetime."""
        update = _make_update(text="20/09/2026 14:00")
        ctx = _make_context()

        await handle_gv_edit_fecha(update, ctx)

        stored = ctx.user_data.get("gv_nueva_fecha")
        assert stored is not None
        parsed = datetime.datetime.fromisoformat(stored)
        assert parsed.year == 2026
        assert parsed.month == 9
        assert parsed.day == 20

    @pytest.mark.asyncio
    async def test_fecha_valida_reply_usa_pedir_motivo_editar(self) -> None:
        """FIX 1: valid fecha must reply with pedir_motivo_editar text, not pedir_motivo."""
        from garay.mensajes.catalogo import obtener_mensaje

        update = _make_update(text="20/09/2026")
        ctx = _make_context()

        await handle_gv_edit_fecha(update, ctx)

        expected_text = obtener_mensaje("gestion_ventas.pedir_motivo_editar")
        update.effective_message.reply_text.assert_called_once_with(
            expected_text,
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# B3: handle_gv_confirmar — editar branch
# ---------------------------------------------------------------------------


class TestHandleGvConfirmarEditar:
    @pytest.mark.asyncio
    async def test_confirmar_editar_llama_servicio_y_retorna_end(self) -> None:
        """Confirm edit: editar_fecha_venta_service.ejecutar called with correct command."""
        from garay.aplicacion.ventas.comandos import EditarFechaVentaComando

        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cambio de plan"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        service = ctx.bot_data["editar_fecha_venta_service"]
        service.ejecutar.assert_called_once()
        cmd: EditarFechaVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.nueva_fecha == datetime.datetime.fromisoformat(nueva_fecha_str)
        assert cmd.motivo == "Cambio de plan"
        assert cmd.realizada_por_telegram_id == 123

    @pytest.mark.asyncio
    async def test_confirmar_editar_limpia_user_data(self) -> None:
        """After successful edit confirm, all gv_* keys must be cleaned up."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cambio de plan"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"

        await handle_gv_confirmar(update, ctx)

        assert "gv_venta_id" not in ctx.user_data
        assert "gv_motivo" not in ctx.user_data
        assert "gv_nueva_fecha" not in ctx.user_data
        assert "gv_accion" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_confirmar_editar_venta_ya_anulada_reply_error_y_end(self) -> None:
        """TOCTOU: if venta was anulada after selection, must reply ya_anulada + END."""
        from garay.dominio.ventas.errores import VentaYaAnulada

        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.bot_data["editar_fecha_venta_service"].ejecutar.side_effect = VentaYaAnulada("ya")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_anular_path_regression(self) -> None:
        """Regression: anular path still works when gv_accion='anular'."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"
        ctx.user_data["gv_accion"] = "anular"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["anular_venta_service"].ejecutar.assert_called_once()


# ---------------------------------------------------------------------------
# B3: _limpiar clears gv_accion and gv_nueva_fecha
# ---------------------------------------------------------------------------


class TestLimpiarClearsB3Keys:
    @pytest.mark.asyncio
    async def test_limpiar_clears_gv_accion_and_gv_nueva_fecha(self) -> None:
        """_limpiar must pop gv_accion and gv_nueva_fecha (B3 keys)."""
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_nueva_fecha"] = "2026-09-20T10:30:00"
        ctx.user_data["gv_venta_id"] = "some-id"
        ctx.user_data["gv_motivo"] = "some-motivo"

        await handle_gv_confirmar(update, ctx)

        assert "gv_accion" not in ctx.user_data
        assert "gv_nueva_fecha" not in ctx.user_data


# ---------------------------------------------------------------------------
# C2: handle_gv_seleccionar — stash cliente/tour names
# ---------------------------------------------------------------------------


class TestHandleGvSeleccionarStashNames:
    @pytest.mark.asyncio
    async def test_seleccionar_stashes_cliente_nombre(self) -> None:
        """handle_gv_seleccionar must store gv_cliente_nombre in user_data."""
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_seleccionar(update, ctx)

        assert ctx.user_data.get("gv_cliente_nombre") == "Juan Perez"

    @pytest.mark.asyncio
    async def test_seleccionar_stashes_tours_str(self) -> None:
        """handle_gv_seleccionar must store gv_tours in user_data."""
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        await handle_gv_seleccionar(update, ctx)

        assert ctx.user_data.get("gv_tours") == "Tour Isla"

    @pytest.mark.asyncio
    async def test_limpiar_clears_gv_cliente_nombre_and_gv_tours(self) -> None:
        """_limpiar (via cancelar) must pop gv_cliente_nombre and gv_tours."""
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        ctx.user_data["gv_venta_id"] = "some-id"
        ctx.user_data["gv_motivo"] = "some-motivo"

        await handle_gv_confirmar(update, ctx)

        assert "gv_cliente_nombre" not in ctx.user_data
        assert "gv_tours" not in ctx.user_data


# ---------------------------------------------------------------------------
# C2: group notification on anular
# ---------------------------------------------------------------------------


class TestNotificarGrupoAnular:
    @pytest.mark.asyncio
    async def test_anular_success_calls_notificador_once(self) -> None:
        """On successful anular, notificador.notificar must be called once."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cliente cancelo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        notificador = ctx.bot_data["notificador"]
        notificador.notificar.assert_called_once()

    @pytest.mark.asyncio
    async def test_anular_notificador_message_contains_cliente_tour_motivo(self) -> None:
        """Notification message must include cliente, tour, and motivo."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cliente cancelo el viaje"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        await handle_gv_confirmar(update, ctx)

        notificador = ctx.bot_data["notificador"]
        call_args = notificador.notificar.call_args
        mensaje_arg: str = call_args[0][0]
        grupo_id_arg: str = call_args[0][1]

        assert "Juan Perez" in mensaje_arg
        assert "Tour Isla" in mensaje_arg
        assert "Cliente cancelo el viaje" in mensaje_arg
        assert grupo_id_arg == "-1001234567"

    @pytest.mark.asyncio
    async def test_anular_notificador_escapes_html_in_dynamic_values(self) -> None:
        """Dynamic values must be HTML-escaped so Telegram HTML mode never breaks."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Se fue con Juan & Pedro <urgente>"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "O'Hara & Sons"
        ctx.user_data["gv_tours"] = "Tour Isla"

        await handle_gv_confirmar(update, ctx)

        mensaje_arg: str = ctx.bot_data["notificador"].notificar.call_args[0][0]

        assert "&amp;" in mensaje_arg
        assert "&lt;urgente&gt;" in mensaje_arg
        # Raw unescaped angle brackets from user input must not leak through.
        assert "<urgente>" not in mensaje_arg

    @pytest.mark.asyncio
    async def test_anular_notificador_raises_flow_still_ends(self) -> None:
        """Notification failure must NOT break the anular flow — still returns END + reply."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        ctx.bot_data["notificador"].notificar.side_effect = RuntimeError("Telegram down")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_anular_notificador_absent_from_bot_data_no_crash(self) -> None:
        """If notificador is missing from bot_data, anular still succeeds."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        del ctx.bot_data["notificador"]

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_anular_still_replies_anulada_message(self) -> None:
        """Even with notification, user still receives the anulada reply."""
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo test"
        ctx.user_data["gv_accion"] = "anular"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        from garay.mensajes.catalogo import obtener_mensaje
        await handle_gv_confirmar(update, ctx)

        expected = obtener_mensaje("gestion_ventas.anulada")
        update.effective_message.reply_text.assert_called_once_with(
            expected, parse_mode="HTML"
        )


# ---------------------------------------------------------------------------
# C2: group notification on editar fecha
# ---------------------------------------------------------------------------


class TestNotificarGrupoEditar:
    @pytest.mark.asyncio
    async def test_editar_success_calls_notificador_once(self) -> None:
        """On successful editar, notificador.notificar must be called once."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Pasajero cambio disponibilidad"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        notificador = ctx.bot_data["notificador"]
        notificador.notificar.assert_called_once()

    @pytest.mark.asyncio
    async def test_editar_notificador_message_contains_cliente_tour_fecha_motivo(self) -> None:
        """Notification message must include cliente, tour, new fecha, and motivo."""
        venta_id = uuid.uuid4()
        nueva_fecha = datetime.datetime(2026, 9, 20, 10, 30)
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Cambio de plan del pasajero"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha.isoformat()
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        await handle_gv_confirmar(update, ctx)

        notificador = ctx.bot_data["notificador"]
        call_args = notificador.notificar.call_args
        mensaje_arg: str = call_args[0][0]
        grupo_id_arg: str = call_args[0][1]

        assert "Juan Perez" in mensaje_arg
        assert "Tour Isla" in mensaje_arg
        assert "20/09/2026" in mensaje_arg
        assert "Cambio de plan del pasajero" in mensaje_arg
        assert grupo_id_arg == "-1001234567"

    @pytest.mark.asyncio
    async def test_editar_notificador_raises_flow_still_ends(self) -> None:
        """Notification failure must NOT break the editar flow."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        ctx.bot_data["notificador"].notificar.side_effect = RuntimeError("Network error")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_editar_notificador_absent_from_bot_data_no_crash(self) -> None:
        """If notificador is missing from bot_data, editar still succeeds."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"
        del ctx.bot_data["notificador"]

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_editar_still_replies_editada_message(self) -> None:
        """Even with notification, user still receives the editada reply."""
        venta_id = uuid.uuid4()
        nueva_fecha_str = datetime.datetime(2026, 9, 20, 10, 30).isoformat()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo test"
        ctx.user_data["gv_nueva_fecha"] = nueva_fecha_str
        ctx.user_data["gv_accion"] = "editar"
        ctx.user_data["gv_cliente_nombre"] = "Juan Perez"
        ctx.user_data["gv_tours"] = "Tour Isla"

        from garay.mensajes.catalogo import obtener_mensaje
        await handle_gv_confirmar(update, ctx)

        expected = obtener_mensaje("gestion_ventas.editada")
        update.effective_message.reply_text.assert_called_once_with(
            expected, parse_mode="HTML"
        )
