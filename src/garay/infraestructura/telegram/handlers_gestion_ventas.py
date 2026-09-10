"""PTB handlers for /gestionar_ventas — anular and editar fecha flow (Slice B2 + B3)."""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from html import escape

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.comun.fechas import parsear_fecha
from garay.aplicacion.factura.regenerar_factura import (
    RegenerarFacturaService,
    ResultadoRegenerarFactura,
)
from garay.aplicacion.ventas.anular_venta import AnularVentaService
from garay.aplicacion.ventas.comandos import (
    AnularVentaComando,
    EditarClienteVentaComando,
    EditarFechaVentaComando,
)
from garay.aplicacion.ventas.editar_cliente_venta import EditarClienteVentaService
from garay.aplicacion.ventas.editar_fecha_venta import EditarFechaVentaService
from garay.dominio.clientes.entidades import CampoCliente
from garay.dominio.clientes.errores import ClienteNoEncontrado
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    FreelancerRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    LimiteEdicionesAlcanzado,
    MotivoRequerido,
    VentaNoEncontrada,
    VentaYaAnulada,
)
from garay.infraestructura.telegram.auth import requiere_admin_o_propietario_conv
from garay.infraestructura.telegram.handlers import cerrar_flujo
from garay.infraestructura.telegram.menu import GrupoComando
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
        context.user_data.pop("gv_campo", None)
        context.user_data.pop("gv_nuevo_valor", None)
        context.user_data.pop("gv_valor_anterior", None)


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
GV_EDIT_CAMPO: int = 225
GV_EDIT_VALOR: int = 226

# Single source of truth for the GV_DETALLE callback pattern. Must match every
# callback_data the detail keyboard produces (see _construir_teclado_detalle);
# a test guards this so a new button can never silently go unrouted again.
GV_DETALLE_PATTERN = "^gv_(editar|anular|cancelar|atras)$"

# Field-submenu callbacks: one per editable field (gv_campo:<campo>) plus a back
# button to the detail view. Guarded by a test against _construir_teclado_campos.
GV_EDIT_CAMPO_PATTERN = "^(gv_campo:[a-z_]+|gv_volver_detalle)$"

# Editable client fields shown in the submenu, in display order (label key, campo).
_CAMPOS_CLIENTE: tuple[tuple[str, CampoCliente], ...] = (
    ("gestion_ventas.campo_nombre", CampoCliente.NOMBRE),
    ("gestion_ventas.campo_telefono", CampoCliente.TELEFONO),
    ("gestion_ventas.campo_email", CampoCliente.EMAIL),
    ("gestion_ventas.campo_identificacion", CampoCliente.IDENTIFICACION),
    ("gestion_ventas.campo_hotel", CampoCliente.HOTEL),
    ("gestion_ventas.campo_habitacion", CampoCliente.NUMERO_HABITACION),
)

# Window for /gestionar_ventas: how many days back to look, by REGISTRATION date
# (registrado_en), so recently-registered sales surface even if their tour date is
# in the future. Kept as a named constant — it is a UI window, not a business
# amount/percentage.
_VENTANA_DIAS_GESTION = 2
_MAX_VENTAS = 15


def _construir_teclado_ventas(ventas: list[Venta]) -> InlineKeyboardMarkup:
    """Build the inline keyboard for the venta list (up to _MAX_VENTAS).

    Preserves the order given by the repo (registration recency, newest first);
    it does not re-sort by tour date. Each button shows vendedor / cerrador · fecha
    · monto. Shared by the entry point and the "Atrás" navigation so the list is
    built in exactly one place.
    """
    ventas_sorted = ventas[:_MAX_VENTAS]
    keyboard = [
        [
            InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.boton_venta").format(
                    vendedor=v.participantes.vendedor_nombre or "—",
                    cerrador=v.participantes.cerrador_nombre or "—",
                    fecha=f"{v.fecha:%d/%m}",
                    monto=v.valor_venta.monto,
                ),
                callback_data=f"gv_sel:{v.id}",
            )
        ]
        for v in ventas_sorted
    ]
    return InlineKeyboardMarkup(keyboard)


def _construir_teclado_detalle() -> InlineKeyboardMarkup:
    """Build the detail-view keyboard. Every callback_data here MUST be covered by
    GV_DETALLE_PATTERN (a test enforces it)."""
    return InlineKeyboardMarkup(
        [
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
            [InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.boton_atras"),
                callback_data="gv_atras",
            )],
        ]
    )


def _construir_teclado_campos() -> InlineKeyboardMarkup:
    """Build the edit-field submenu: fecha + client fields, plus back-to-detail.

    Every callback_data here MUST be covered by GV_EDIT_CAMPO_PATTERN (test-guarded).
    """
    filas = [
        [InlineKeyboardButton(
            obtener_mensaje("gestion_ventas.campo_fecha"),
            callback_data="gv_campo:fecha",
        )],
    ]
    filas += [
        [InlineKeyboardButton(
            obtener_mensaje(label_key),
            callback_data=f"gv_campo:{campo.value}",
        )]
        for label_key, campo in _CAMPOS_CLIENTE
    ]
    filas.append(
        [InlineKeyboardButton(
            obtener_mensaje("gestion_ventas.boton_atras"),
            callback_data="gv_volver_detalle",
        )]
    )
    return InlineKeyboardMarkup(filas)


# ---------------------------------------------------------------------------
# /gestionar_ventas entry point
# ---------------------------------------------------------------------------


@requiere_admin_o_propietario_conv
async def cmd_gestionar_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END

    # Clear any stale gv_* keys from a previous conversation run.
    _limpiar(context)

    desde = datetime.date.today() - datetime.timedelta(days=_VENTANA_DIAS_GESTION)

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        logger.error("venta_repo not found in bot_data")
        return ConversationHandler.END

    ventas = await asyncio.to_thread(venta_repo.listar_para_gestion, desde)

    if not ventas:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.sin_ventas"),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        obtener_mensaje("gestion_ventas.seleccionar"),
        reply_markup=_construir_teclado_ventas(ventas),
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

    return await _render_detalle(query, context, venta)


async def _render_detalle(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, venta: Venta
) -> int:
    """Resolve client + tour names, stash them, and edit the message into the
    detail view (hides list / submenu). Shared by seleccionar and volver-al-detalle."""
    cliente_repo: ClienteRepository | None = context.bot_data.get("cliente_repo")
    cliente_nombre = "—"
    if cliente_repo is not None:
        cliente = await asyncio.to_thread(cliente_repo.buscar_por_id, venta.cliente_id)
        if cliente is not None:
            cliente_nombre = cliente.nombre

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

    await query.edit_message_text(
        detail_text,
        reply_markup=_construir_teclado_detalle(),
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
        # Edit the detail message in place so its buttons don't linger during the flow.
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.pedir_motivo"),
            parse_mode="HTML",
        )
        return GV_MOTIVO

    if data == "gv_editar":
        # Edit the detail message in place into the field submenu (no lingering buttons).
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.seleccionar_campo"),
            reply_markup=_construir_teclado_campos(),
            parse_mode="HTML",
        )
        return GV_EDIT_CAMPO

    if data == "gv_atras":
        return await _handle_volver_a_lista(update, context)

    if data == "gv_cancelar":
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.cancelado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


async def _handle_volver_a_lista(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Rebuild the venta list and edit the message back to it (Atrás navigation)."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    desde = datetime.date.today() - datetime.timedelta(days=_VENTANA_DIAS_GESTION)
    ventas = await asyncio.to_thread(venta_repo.listar_para_gestion, desde)

    if not ventas:
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.sin_ventas"),
            parse_mode="HTML",
        )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    await query.edit_message_text(
        obtener_mensaje("gestion_ventas.seleccionar"),
        reply_markup=_construir_teclado_ventas(ventas),
        parse_mode="HTML",
    )
    return GV_SELECCIONAR


# ---------------------------------------------------------------------------
# GV_EDIT_CAMPO state — user picks which field to edit
# ---------------------------------------------------------------------------

_ETIQUETA_POR_CAMPO: dict[CampoCliente, str] = {
    campo: label_key for label_key, campo in _CAMPOS_CLIENTE
}


async def handle_gv_edit_campo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""

    # Fetch the venta once — needed both to go back to detail and to show the
    # current value of the field being edited.
    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    venta_id_str = (context.user_data or {}).get("gv_venta_id")
    venta = None
    if venta_repo is not None and venta_id_str:
        venta = await asyncio.to_thread(venta_repo.buscar_por_id, uuid.UUID(venta_id_str))
    if venta is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if data == "gv_volver_detalle":
        return await _render_detalle(query, context, venta)

    campo_str = data.removeprefix("gv_campo:")

    if campo_str == "fecha":
        if context.user_data is not None:
            context.user_data["gv_accion"] = "editar"
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.pedir_fecha").format(
                actual=f"{venta.fecha:%d/%m/%Y}"
            ),
            parse_mode="HTML",
        )
        return GV_EDIT_FECHA

    try:
        campo = CampoCliente(campo_str)
    except ValueError:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    valor_actual = await _valor_actual_cliente(context, venta.cliente_id, campo)

    if context.user_data is not None:
        context.user_data["gv_accion"] = "editar_cliente"
        context.user_data["gv_campo"] = campo.value
        context.user_data["gv_valor_anterior"] = valor_actual

    await query.edit_message_text(
        obtener_mensaje("gestion_ventas.pedir_valor").format(
            campo=obtener_mensaje(_ETIQUETA_POR_CAMPO[campo]),
            actual=valor_actual,
        ),
        parse_mode="HTML",
    )
    return GV_EDIT_VALOR


async def _valor_actual_cliente(
    context: ContextTypes.DEFAULT_TYPE, cliente_id: uuid.UUID, campo: CampoCliente
) -> str:
    """Return the client's current value for `campo`, or a '(sin dato)' placeholder."""
    cliente_repo: ClienteRepository | None = context.bot_data.get("cliente_repo")
    if cliente_repo is not None:
        cliente = await asyncio.to_thread(cliente_repo.buscar_por_id, cliente_id)
        if cliente is not None:
            valor = getattr(cliente, campo.value)
            if valor:
                return str(valor)
    return obtener_mensaje("gestion_ventas.sin_dato")


# ---------------------------------------------------------------------------
# GV_EDIT_VALOR state — text input for the new client-field value
# ---------------------------------------------------------------------------


async def handle_gv_edit_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    text = update.message.text if update.message else ""
    valor = (text or "").strip()
    if not valor:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.valor_vacio"),
            parse_mode="HTML",
        )
        return GV_EDIT_VALOR

    if context.user_data is not None:
        context.user_data["gv_nuevo_valor"] = valor

    await update.effective_message.reply_text(
        obtener_mensaje("gestion_ventas.pedir_motivo_editar"),
        parse_mode="HTML",
    )
    return GV_MOTIVO


# ---------------------------------------------------------------------------
# GV_EDIT_FECHA state — text input for new date
# ---------------------------------------------------------------------------


async def handle_gv_edit_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive a date string for the new tour date; validates using the canonical parser."""
    if update.effective_message is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

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
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

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
    elif gv_accion == "editar_cliente":
        campo_str: str | None = user_data.get("gv_campo")
        campo_label = (
            obtener_mensaje(_ETIQUETA_POR_CAMPO[CampoCliente(campo_str)])
            if campo_str
            else "—"
        )
        confirm_text = obtener_mensaje("gestion_ventas.confirmar_editar_cliente").format(
            campo=campo_label,
            anterior=user_data.get("gv_valor_anterior") or "—",
            valor=user_data.get("gv_nuevo_valor") or "—",
            motivo=motivo,
        )
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
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if data != "gv_confirmar":
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    user = update.effective_user
    if user is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    user_data = context.user_data or {}
    gv_accion: str = user_data.get("gv_accion", "anular")

    if gv_accion == "editar":
        return await _handle_confirmar_editar(update, context, user_data, user)

    if gv_accion == "editar_cliente":
        return await _handle_confirmar_editar_cliente(update, context, user_data, user)

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
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

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
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    try:
        await asyncio.to_thread(editar_service.ejecutar, cmd)
    except VentaYaAnulada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.ya_anulada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except VentaNoEncontrada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except LimiteEdicionesAlcanzado:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.limite_ediciones"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except MotivoRequerido:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.motivo_vacio"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except Exception:
        logger.exception("Unexpected error in handle_gv_confirmar (editar)")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    nueva_fecha_dt = datetime.datetime.fromisoformat(nueva_fecha_str)
    mensaje_grupo = obtener_mensaje("gestion_ventas.correccion_edicion_fecha").format(
        cliente=escape(user_data.get("gv_cliente_nombre") or "—", quote=False),
        tours=escape(user_data.get("gv_tours") or "—", quote=False),
        fecha=f"{nueva_fecha_dt:%d/%m/%Y %H:%M}",
        motivo=escape(motivo, quote=False),
        actor=escape(nombre or "—", quote=False),
    )
    await _notificar_grupo(context, mensaje_grupo)

    # C3: regenerate and resend the client invoice with the updated date.
    regenerar_service: RegenerarFacturaService | None = context.bot_data.get(
        "regenerar_factura_service"
    )
    resultado_factura: ResultadoRegenerarFactura | None = None
    if regenerar_service is not None:
        try:
            resultado_factura = await asyncio.to_thread(
                regenerar_service.ejecutar, uuid.UUID(venta_id_str)
            )
        except Exception:
            logger.exception("Error al regenerar/reenviar la factura tras editar fecha")

    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.editada"),
            parse_mode="HTML",
        )
        if resultado_factura is ResultadoRegenerarFactura.REENVIADA:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.factura_reenviada"),
                parse_mode="HTML",
            )
        elif resultado_factura is ResultadoRegenerarFactura.ERROR_ENVIO:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.factura_error"),
                parse_mode="HTML",
            )
    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


async def _handle_confirmar_editar_cliente(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the editar-cliente action."""
    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")
    campo_str: str | None = user_data.get("gv_campo")
    nuevo_valor: str | None = user_data.get("gv_nuevo_valor")

    if not venta_id_str or not motivo or not campo_str or not nuevo_valor:
        logger.error("editar_cliente confirm: estado incompleto")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    user_id: int = getattr(user, "id", 0)
    freelancer_repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    nombre: str | None = None
    if freelancer_repo is not None:
        fl = await asyncio.to_thread(freelancer_repo.buscar_por_telegram_id, user_id)
        if fl is not None:
            nombre = fl.nombre

    cmd = EditarClienteVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        campo=CampoCliente(campo_str),
        nuevo_valor=nuevo_valor,
        motivo=motivo,
        realizada_por_telegram_id=user_id,
        realizada_por_nombre=nombre,
    )

    service: EditarClienteVentaService | None = context.bot_data.get(
        "editar_cliente_venta_service"
    )
    if service is None:
        logger.error("editar_cliente_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    try:
        await asyncio.to_thread(service.ejecutar, cmd)
    except LimiteEdicionesAlcanzado:
        mensaje_key = "gestion_ventas.limite_ediciones"
    except VentaNoEncontrada:
        mensaje_key = "gestion_ventas.no_encontrada"
    except ClienteNoEncontrado:
        mensaje_key = "gestion_ventas.no_encontrada"
    except MotivoRequerido:
        mensaje_key = "gestion_ventas.motivo_vacio"
    except Exception:
        logger.exception("Unexpected error in handle_gv_confirmar (editar_cliente)")
        mensaje_key = "gestion_ventas.error_generico"
    else:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.cliente_editado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje(mensaje_key),
            parse_mode="HTML",
        )
    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


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
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

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
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    try:
        await asyncio.to_thread(anular_service.ejecutar, cmd)
    except VentaYaAnulada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.ya_anulada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except VentaNoEncontrada:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except MotivoRequerido:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.motivo_vacio"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except Exception:
        logger.exception("Unexpected error in handle_gv_confirmar")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

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
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)
