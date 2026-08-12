"""PTB handlers for /gestionar_ventas — anular and editar fecha flow (Slice B2 + B3)."""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.comun.fechas import parsear_fecha
from garay.aplicacion.ventas.anular_venta import AnularVentaService
from garay.aplicacion.ventas.comandos import AnularVentaComando, EditarFechaVentaComando
from garay.aplicacion.ventas.editar_fecha_venta import EditarFechaVentaService
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    FreelancerRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada, VentaYaAnulada
from garay.infraestructura.telegram.auth import requiere_admin_o_propietario_conv
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)


def _limpiar(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove gv_* keys from user_data to prevent stale state across conversation runs."""
    if context.user_data is not None:
        context.user_data.pop("gv_venta_id", None)
        context.user_data.pop("gv_motivo", None)
        context.user_data.pop("gv_accion", None)
        context.user_data.pop("gv_nueva_fecha", None)
        context.user_data.pop("gv_cliente_nombre", None)
        context.user_data.pop("gv_tours", None)


async def _notificar_grupo(context: ContextTypes.DEFAULT_TYPE, mensaje: str) -> None:
    """Send a correction message to the Telegram group without crashing the caller.

    The notificador uses a blocking urllib implementation, so it is called via
    asyncio.to_thread.  Any exception is swallowed — a notification failure must
    never roll back a committed domain operation.
    """
    notificador = context.bot_data.get("notificador")
    grupo_id: str | None = context.bot_data.get("grupo_id")
    if not notificador or not grupo_id:
        return
    try:
        await asyncio.to_thread(notificador.notificar, mensaje, grupo_id)
    except Exception:
        logger.exception("Failed to send group correction message")


# ---------------------------------------------------------------------------
# State constants — range 220-224 (freelancers: 200-213)
# ---------------------------------------------------------------------------

GV_SELECCIONAR: int = 220
GV_DETALLE: int = 221
GV_MOTIVO: int = 222
GV_CONFIRMAR: int = 223
GV_EDIT_FECHA: int = 224

_ROLLING_DAYS = 30
_MAX_VENTAS = 15


# ---------------------------------------------------------------------------
# /gestionar_ventas entry point
# ---------------------------------------------------------------------------


@requiere_admin_o_propietario_conv
async def cmd_gestionar_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END

    # Clear any stale gv_* keys from a previous conversation run.
    _limpiar(context)

    hasta = datetime.date.today()
    desde = hasta - datetime.timedelta(days=_ROLLING_DAYS)

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        logger.error("venta_repo not found in bot_data")
        return ConversationHandler.END

    ventas = await asyncio.to_thread(venta_repo.listar_por_periodo, desde, hasta)

    if not ventas:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.sin_ventas"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # Sort newest-first, take up to 15
    ventas_sorted = sorted(ventas, key=lambda v: v.fecha, reverse=True)[:_MAX_VENTAS]

    keyboard = [
        [
            InlineKeyboardButton(
                f"{v.fecha:%d/%m} · ${v.valor_venta.monto:,.0f}",
                callback_data=f"gv_sel:{v.id}",
            )
        ]
        for v in ventas_sorted
    ]

    await update.effective_message.reply_text(
        obtener_mensaje("gestion_ventas.seleccionar"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return GV_SELECCIONAR


# ---------------------------------------------------------------------------
# GV_SELECCIONAR state — user picks a venta
# ---------------------------------------------------------------------------


async def handle_gv_seleccionar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""
    raw = data.removeprefix("gv_sel:")
    try:
        venta_id = uuid.UUID(raw)
    except ValueError:
        return ConversationHandler.END

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        return ConversationHandler.END

    venta = await asyncio.to_thread(venta_repo.buscar_por_id, venta_id)
    if venta is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        return ConversationHandler.END

    # Resolve client name
    cliente_repo: ClienteRepository | None = context.bot_data.get("cliente_repo")
    cliente_nombre = "—"
    if cliente_repo is not None:
        cliente = await asyncio.to_thread(cliente_repo.buscar_por_id, venta.cliente_id)
        if cliente is not None:
            cliente_nombre = cliente.nombre

    # Resolve tour names
    servicio_repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    tour_nombres: list[str] = []
    if servicio_repo is not None:
        for sid in venta.servicio_ids:
            servicio = await asyncio.to_thread(servicio_repo.buscar_por_id, sid)
            if servicio is not None:
                tour_nombres.append(servicio.nombre)
    tours_str = ", ".join(tour_nombres) if tour_nombres else "—"

    if context.user_data is not None:
        context.user_data["gv_venta_id"] = str(venta.id)
        context.user_data["gv_cliente_nombre"] = cliente_nombre
        context.user_data["gv_tours"] = tours_str

    detail_text = obtener_mensaje("gestion_ventas.detalle").format(
        cliente=cliente_nombre,
        tours=tours_str,
        fecha=f"{venta.fecha:%d/%m/%Y}",
        valor=venta.valor_venta.monto,
    )

    keyboard = [
        [InlineKeyboardButton(
            obtener_mensaje("gestion_ventas.boton_editar"),
            callback_data="gv_editar",
        )],
        [
            InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.boton_anular"),
                callback_data="gv_anular",
            ),
            InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.boton_cancelar"),
                callback_data="gv_cancelar",
            ),
        ],
    ]

    if update.effective_message:
        await update.effective_message.reply_text(
            detail_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    return GV_DETALLE


# ---------------------------------------------------------------------------
# GV_DETALLE state — user chooses action
# ---------------------------------------------------------------------------


async def handle_gv_detalle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data

    if data == "gv_anular":
        if context.user_data is not None:
            context.user_data["gv_accion"] = "anular"
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.pedir_motivo"),
                parse_mode="HTML",
            )
        return GV_MOTIVO

    if data == "gv_editar":
        if context.user_data is not None:
            context.user_data["gv_accion"] = "editar"
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.pedir_fecha"),
                parse_mode="HTML",
            )
        return GV_EDIT_FECHA

    if data == "gv_cancelar":
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.cancelado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    _limpiar(context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# GV_EDIT_FECHA state — text input for new date
# ---------------------------------------------------------------------------


async def handle_gv_edit_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive a date string for the new tour date; validates using the canonical parser."""
    if update.effective_message is None:
        _limpiar(context)
        return ConversationHandler.END

    text = update.message.text if update.message else ""

    parsed = parsear_fecha(text or "")
    if parsed is None:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.fecha_invalida"),
            parse_mode="HTML",
        )
        return GV_EDIT_FECHA

    if context.user_data is not None:
        context.user_data["gv_nueva_fecha"] = parsed.isoformat()

    await update.effective_message.reply_text(
        obtener_mensaje("gestion_ventas.pedir_motivo_editar"),
        parse_mode="HTML",
    )
    return GV_MOTIVO


# ---------------------------------------------------------------------------
# GV_MOTIVO state — text input for justification
# ---------------------------------------------------------------------------


async def handle_gv_motivo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        _limpiar(context)
        return ConversationHandler.END

    text = update.message.text if update.message else ""
    motivo = (text or "").strip()

    if not motivo:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.motivo_vacio"),
            parse_mode="HTML",
        )
        return GV_MOTIVO

    if context.user_data is not None:
        context.user_data["gv_motivo"] = motivo

    user_data = context.user_data or {}
    gv_accion: str = user_data.get("gv_accion", "anular")

    if gv_accion == "editar":
        gv_nueva_fecha_str: str | None = user_data.get("gv_nueva_fecha")
        if gv_nueva_fecha_str:
            nueva_fecha_dt = datetime.datetime.fromisoformat(gv_nueva_fecha_str)
            confirm_text = obtener_mensaje("gestion_ventas.confirmar_editar").format(
                fecha=f"{nueva_fecha_dt:%d/%m/%Y %H:%M}",
                motivo=motivo,
            )
        else:
            confirm_text = obtener_mensaje("gestion_ventas.confirmar").format(motivo=motivo)
    else:
        confirm_text = obtener_mensaje("gestion_ventas.confirmar").format(motivo=motivo)

    keyboard = [
        [
            InlineKeyboardButton("Confirmar", callback_data="gv_confirmar"),
            InlineKeyboardButton("Cancelar", callback_data="gv_cancelar"),
        ]
    ]

    await update.effective_message.reply_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return GV_CONFIRMAR


# ---------------------------------------------------------------------------
# GV_CONFIRMAR state — final confirm or cancel
# ---------------------------------------------------------------------------


async def handle_gv_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data

    if data == "gv_cancelar":
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.cancelado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    if data != "gv_confirmar":
        _limpiar(context)
        return ConversationHandler.END

    user = update.effective_user
    if user is None:
        _limpiar(context)
        return ConversationHandler.END

    user_data = context.user_data or {}
    gv_accion: str = user_data.get("gv_accion", "anular")

    if gv_accion == "editar":
        return await _handle_confirmar_editar(update, context, user_data, user)

    # Default: anular path.
    return await _handle_confirmar_anular(update, context, user_data, user)


async def _handle_confirmar_editar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the editar-fecha action."""
    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")
    nueva_fecha_str: str | None = user_data.get("gv_nueva_fecha")

    if not venta_id_str or not motivo or not nueva_fecha_str:
        logger.error(
            "editar confirm: estado incompleto — gv_nueva_fecha/gv_venta_id/gv_motivo faltante"
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    # Resolve realizada_por nombre
    user_id: int = getattr(user, "id", 0)
    freelancer_repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    nombre: str | None = None
    if freelancer_repo is not None:
        fl = await asyncio.to_thread(freelancer_repo.buscar_por_telegram_id, user_id)
        if fl is not None:
            nombre = fl.nombre

    cmd = EditarFechaVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        nueva_fecha=datetime.datetime.fromisoformat(nueva_fecha_str),
        motivo=motivo,
        realizada_por_telegram_id=user_id,
        realizada_por_nombre=nombre,
    )

    editar_service: EditarFechaVentaService | None = context.bot_data.get(
        "editar_fecha_venta_service"
    )
    if editar_service is None:
        logger.error("editar_fecha_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    try:
        await asyncio.to_thread(editar_service.ejecutar, cmd)
    except VentaYaAnulada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.ya_anulada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END
    except VentaNoEncontrada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END
    except MotivoRequerido:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.motivo_vacio"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END
    except Exception:
        logger.exception("Unexpected error in handle_gv_confirmar (editar)")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    nueva_fecha_dt = datetime.datetime.fromisoformat(nueva_fecha_str)
    mensaje_grupo = obtener_mensaje("gestion_ventas.correccion_edicion_fecha").format(
        cliente=escape(user_data.get("gv_cliente_nombre") or "—", quote=False),
        tours=escape(user_data.get("gv_tours") or "—", quote=False),
        fecha=f"{nueva_fecha_dt:%d/%m/%Y %H:%M}",
        motivo=escape(motivo, quote=False),
        actor=escape(nombre or "—", quote=False),
    )
    await _notificar_grupo(context, mensaje_grupo)

    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.editada"),
            parse_mode="HTML",
        )
    _limpiar(context)
    return ConversationHandler.END


async def _handle_confirmar_anular(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the anular action."""
    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")

    if not venta_id_str or not motivo:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    # Resolve realizada_por nombre
    user_id_anular: int = getattr(user, "id", 0)
    freelancer_repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    nombre: str | None = None
    if freelancer_repo is not None:
        fl = await asyncio.to_thread(freelancer_repo.buscar_por_telegram_id, user_id_anular)
        if fl is not None:
            nombre = fl.nombre

    cmd = AnularVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        motivo=motivo,
        realizada_por_telegram_id=user_id_anular,
        realizada_por_nombre=nombre,
    )

    anular_service: AnularVentaService | None = context.bot_data.get("anular_venta_service")
    if anular_service is None:
        logger.error("anular_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    try:
        await asyncio.to_thread(anular_service.ejecutar, cmd)
    except VentaYaAnulada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.ya_anulada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END
    except VentaNoEncontrada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END
    except MotivoRequerido:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.motivo_vacio"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END
    except Exception:
        logger.exception("Unexpected error in handle_gv_confirmar")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return ConversationHandler.END

    mensaje_grupo = obtener_mensaje("gestion_ventas.correccion_anulacion").format(
        cliente=escape(user_data.get("gv_cliente_nombre") or "—", quote=False),
        tours=escape(user_data.get("gv_tours") or "—", quote=False),
        motivo=escape(motivo, quote=False),
        actor=escape(nombre or "—", quote=False),
    )
    await _notificar_grupo(context, mensaje_grupo)

    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.anulada"),
            parse_mode="HTML",
        )
    _limpiar(context)
    return ConversationHandler.END
