"""PTB handlers for /gestionar_ventas — anular and editar fecha flow (Slice B2 + B3 + filtros)."""

from __future__ import annotations

import asyncio
import calendar
import contextlib
import datetime
import logging
import re
import uuid
from decimal import Decimal
from html import escape

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.comun.fechas import parsear_fecha
from garay.aplicacion.comun.formato import fmt_cop
from garay.aplicacion.comun.montos import parsear_monto
from garay.aplicacion.factura.regenerar_factura import (
    RegenerarFacturaService,
    ResultadoRegenerarFactura,
)
from garay.aplicacion.ventas.anular_venta import AnularVentaService
from garay.aplicacion.ventas.comandos import (
    AnularVentaComando,
    EditarCanalVentaComando,
    EditarClienteVentaComando,
    EditarFechaVentaComando,
    EditarNetoVentaComando,
    EditarParticipantesVentaComando,
    EditarValorVentaComando,
)
from garay.aplicacion.ventas.editar_canal import EditarCanalVentaService
from garay.aplicacion.ventas.editar_cliente_venta import EditarClienteVentaService
from garay.aplicacion.ventas.editar_fecha_venta import EditarFechaVentaService
from garay.aplicacion.ventas.editar_neto import EditarNetoVentaService
from garay.aplicacion.ventas.editar_participantes import EditarParticipantesVentaService
from garay.aplicacion.ventas.editar_valor_venta import EditarValorVentaService
from garay.config.settings import obtener_settings
from garay.dominio.clientes.entidades import CampoCliente
from garay.dominio.clientes.errores import ClienteNoEncontrado
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    ComisionRegistradaRepository,
    FreelancerRepository,
    ServicioRepository,
    SocioConfigRepository,
    VentaRepository,
)
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    DigitalConPuntoDeVenta,
    LimiteEdicionesAlcanzado,
    MismoCanal,
    MismoNeto,
    MismosParticipantes,
    MismoValorVenta,
    MotivoRequerido,
    NetoIgualOSuperaValorVenta,
    PuntoDeVentaRequerido,
    ValorVentaMenorQueAbono,
    VentaNoEncontrada,
    VentaYaAnulada,
)
from garay.infraestructura.telegram.auth import (
    es_admin_o_propietario,
    requiere_admin_o_propietario_conv,
)
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
        context.user_data.pop("gv_desde", None)
        context.user_data.pop("gv_hasta", None)
        context.user_data.pop("gv_nuevo_tipo", None)
        context.user_data.pop("gv_punto_id", None)
        context.user_data.pop("gv_nuevo_freelancer_id", None)
        context.user_data.pop("gv_nuevo_freelancer_nombre", None)
        context.user_data.pop("gv_participante_anterior", None)
        context.user_data.pop("gv_nuevo_neto", None)
        context.user_data.pop("gv_nuevo_valor_venta", None)


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


async def _notificar_edicion(
    context: ContextTypes.DEFAULT_TYPE,
    venta: Venta,
    mensaje_grupo: str,
    campo_label: str,
    *,
    es_financiero: bool,
    dm_socios_text: str | None = None,
    dm_admins_text: str | None = None,
) -> None:
    """Delete the old group message (best-effort), send the updated one, DM socios/admins.

    All steps are best-effort: any Telegram exception is swallowed.  The caller has
    already committed the domain change — notification failure must never roll it back.

    Args:
        context: PTB context — provides bot + bot_data.
        venta: The updated Venta entity; used to read/write mensaje_grupo_id.
        mensaje_grupo: Pre-formatted text to send to the group chat.
        campo_label: Human-readable field label (used in admin DM fallback).
        es_financiero: If True, DMs are sent to socios.
        dm_socios_text: Pre-formatted text for the socios DM (only when es_financiero).
        dm_admins_text: Pre-formatted text for the admin DM; falls back to mensaje_grupo.
    """
    grupo_id: str | None = context.bot_data.get("grupo_id")

    # Step 1 — delete original group message (best-effort).
    if grupo_id and venta.mensaje_grupo_id is not None:
        try:
            await context.bot.delete_message(
                chat_id=grupo_id, message_id=venta.mensaje_grupo_id
            )
        except Exception:
            logger.warning(
                "Could not delete old group message %s — continuing", venta.mensaje_grupo_id
            )

    # Step 2 — send new group message and capture message_id.
    if grupo_id:
        try:
            sent = await context.bot.send_message(
                chat_id=grupo_id, text=mensaje_grupo, parse_mode="HTML"
            )
            # Step 3 — persist new message_id onto the venta.
            new_id: int | None = getattr(sent, "message_id", None)
            if new_id is not None:
                venta.mensaje_grupo_id = new_id
                venta_repo = context.bot_data.get("venta_repo")
                if venta_repo is not None:
                    try:
                        venta_repo.guardar(venta)
                    except Exception:
                        logger.warning(
                            "Could not persist new mensaje_grupo_id for venta %s", venta.id
                        )
        except Exception:
            logger.warning("Failed to send updated group message for venta %s", venta.id)

    # Step 4 — DM socios (financial edits only).
    if es_financiero and dm_socios_text:
        socios_config_repo = context.bot_data.get("socios_config_repo")
        if socios_config_repo is not None:
            try:
                socios = socios_config_repo.listar()
            except Exception:
                socios = []
            for socio in socios:
                tid: int | None = getattr(socio, "telegram_id", None)
                if tid is None:
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=tid, text=dm_socios_text, parse_mode="HTML"
                    )
                except Exception:
                    logger.warning("Could not DM socio %s", tid)

    # Step 5 — DM admins (all edits).
    _dm_admin_text = dm_admins_text or mensaje_grupo
    try:
        ids_str = obtener_settings().propietario_telegram_ids.strip()
        admin_ids = {int(x.strip()) for x in ids_str.split(",") if x.strip()}
    except Exception:
        admin_ids = set()
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=_dm_admin_text, parse_mode="HTML"
            )
        except Exception:
            logger.warning("Could not DM admin %s", admin_id)


# ---------------------------------------------------------------------------
# State constants — range 220-230 (freelancers: 200-213)
# ---------------------------------------------------------------------------

GV_SELECCIONAR: int = 220
GV_DETALLE: int = 221
GV_MOTIVO: int = 222
GV_CONFIRMAR: int = 223
GV_EDIT_FECHA: int = 224
GV_EDIT_CAMPO: int = 225
GV_EDIT_VALOR: int = 226
GV_FILTRO: int = 227
GV_RANGO_INPUT: int = 228
GV_EDIT_CANAL_TIPO: int = 229
GV_EDIT_CANAL_PUNTO: int = 230
GV_EDIT_PARTICIPANTE: int = 231
GV_EDIT_NETO: int = 232
GV_EDIT_VALOR_VENTA: int = 233

# Single source of truth for the GV_DETALLE callback pattern. Must match every
# callback_data the detail keyboard produces (see _construir_teclado_detalle);
# a test guards this so a new button can never silently go unrouted again.
GV_DETALLE_PATTERN = "^gv_(editar|anular|cancelar|atras)$"

# Field-submenu callbacks: one per editable field (gv_campo:<campo>) plus a back
# button to the detail view. Guarded by a test against _construir_teclado_campos.
GV_EDIT_CAMPO_PATTERN = "^(gv_campo:[a-z_]+|gv_volver_detalle)$"

# Canal-type selector: gv_canal:<TIPO> OR back-to-field-submenu.
GV_EDIT_CANAL_TIPO_PATTERN = "^(gv_canal:.*|gv_volver_detalle)$"

# Freelancer picker: gv_freelancer:<uuid> OR back-to-detail.
GV_EDIT_PARTICIPANTE_PATTERN = "^(gv_freelancer:.+|gv_volver_detalle)$"

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
_VENTANA_DIAS_GESTION = 180
_MAX_VENTAS = 40

_TIPO_CLIENTE_LABEL: dict[TipoCliente, str] = {
    TipoCliente.INTERNO: "Presencial",
    TipoCliente.EXTERNO: "Externo",
    TipoCliente.DIGITAL: "Digital",
}


def _construir_teclado_filtros() -> InlineKeyboardMarkup:
    """Build the filter selection keyboard shown at the entry point."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Últimos 7 días", callback_data="gv_f_7d")],
            [InlineKeyboardButton("📅 Este mes", callback_data="gv_f_mes")],
            [InlineKeyboardButton("📅 Mes anterior", callback_data="gv_f_mes_ant")],
            [InlineKeyboardButton("📅 Rango personalizado", callback_data="gv_f_rango")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="gv_cancelar")],
        ]
    )


def _construir_teclado_ventas(ventas: list[Venta]) -> InlineKeyboardMarkup:
    """Build the inline keyboard for the venta list (up to _MAX_VENTAS).

    Preserves the order given by the repo (registration recency, newest first);
    it does not re-sort by tour date. Each button shows vendedor / cerrador · fecha
    · monto. Includes Atrás and Cancelar buttons at the end.
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
    keyboard.append(
        [
            InlineKeyboardButton("← Atrás", callback_data="gv_atras"),
            InlineKeyboardButton("❌ Cancelar", callback_data="gv_cancelar"),
        ]
    )
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


def _construir_teclado_campos(
    venta: Venta | None = None, *, es_admin: bool = False
) -> InlineKeyboardMarkup:
    """Build the edit-field submenu in summary-field order, plus back-to-detail.

    Order mirrors the detail view: Nombre, Fecha, Canal de ventas, (Neto, Valor de venta
    — admin/propietario/dev only), (Vendedor, Cerrador when non-null), Hotel, Habitación,
    Teléfono, Correo, Identificación, Atrás.
    Every callback_data here MUST be covered by GV_EDIT_CAMPO_PATTERN (test-guarded).
    """

    def _btn(label_key: str, data: str) -> list[InlineKeyboardButton]:
        return [InlineKeyboardButton(obtener_mensaje(label_key), callback_data=data)]

    rows: list[list[InlineKeyboardButton]] = [
        _btn("gestion_ventas.campo_nombre", "gv_campo:nombre"),
        _btn("gestion_ventas.campo_fecha", "gv_campo:fecha"),
        _btn("gestion_ventas.campo_canal", "gv_campo:tipo_cliente"),
    ]
    if es_admin:
        rows.append(_btn("gestion_ventas.campo_neto", "gv_campo:neto"))
        rows.append(_btn("gestion_ventas.campo_valor_venta", "gv_campo:valor_venta"))
    if venta is not None and venta.participantes.vendedor_nombre is not None:
        rows.append(_btn("gestion_ventas.campo_vendedor", "gv_campo:vendedor"))
    if venta is not None and venta.participantes.cerrador_nombre is not None:
        rows.append(_btn("gestion_ventas.campo_cerrador", "gv_campo:cerrador"))
    rows += [
        _btn("gestion_ventas.campo_hotel", "gv_campo:hotel"),
        _btn("gestion_ventas.campo_habitacion", "gv_campo:numero_habitacion"),
        _btn("gestion_ventas.campo_telefono", "gv_campo:telefono"),
        _btn("gestion_ventas.campo_email", "gv_campo:email"),
        _btn("gestion_ventas.campo_identificacion", "gv_campo:identificacion"),
        [InlineKeyboardButton(
            obtener_mensaje("gestion_ventas.boton_atras"),
            callback_data="gv_volver_detalle",
        )],
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# /gestionar_ventas entry point
# ---------------------------------------------------------------------------


@requiere_admin_o_propietario_conv
async def cmd_gestionar_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END

    # Clear any stale gv_* keys from a previous conversation run.
    _limpiar(context)

    await update.effective_message.reply_text(
        "Selecciona el período de ventas a gestionar:",
        reply_markup=_construir_teclado_filtros(),
        parse_mode="HTML",
    )
    return GV_FILTRO


# ---------------------------------------------------------------------------
# Shared helper: apply client-side "hasta" filter on a venta list
# ---------------------------------------------------------------------------


def _filtrar_por_hasta(ventas: list[Venta], hasta: datetime.date) -> list[Venta]:
    """Keep ventas whose business date (fecha) <= hasta."""
    return [v for v in ventas if v.fecha <= hasta]


async def _cargar_y_mostrar_lista(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    desde: datetime.date,
    hasta: datetime.date,
) -> int:
    """Load ventas from repo, apply client-side hasta filter, and show the list."""
    if context.user_data is not None:
        context.user_data["gv_desde"] = desde.isoformat()
        context.user_data["gv_hasta"] = hasta.isoformat()

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        logger.error("venta_repo not found in bot_data")
        return ConversationHandler.END

    ventas = await asyncio.to_thread(venta_repo.listar_para_gestion, desde)
    ventas = _filtrar_por_hasta(ventas, hasta)

    if not ventas:
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.sin_ventas"),
            parse_mode="HTML",
        )
        _limpiar(context)
        return ConversationHandler.END

    await query.edit_message_text(
        obtener_mensaje("gestion_ventas.seleccionar"),
        reply_markup=_construir_teclado_ventas(ventas),
        parse_mode="HTML",
    )
    return GV_SELECCIONAR


# ---------------------------------------------------------------------------
# GV_FILTRO state — user picks a date filter
# ---------------------------------------------------------------------------


async def handle_gv_filtro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle filter selection callbacks (gv_f_7d, gv_f_mes, gv_f_mes_ant, gv_f_rango)."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""
    today = datetime.date.today()

    if data == "gv_f_7d":
        desde = today - datetime.timedelta(days=7)
        hasta = today
        return await _cargar_y_mostrar_lista(query, context, desde, hasta)

    if data == "gv_f_mes":
        desde = datetime.date(today.year, today.month, 1)
        ultimo_dia = calendar.monthrange(today.year, today.month)[1]
        hasta = datetime.date(today.year, today.month, ultimo_dia)
        return await _cargar_y_mostrar_lista(query, context, desde, hasta)

    if data == "gv_f_mes_ant":
        primer_dia_mes_actual = datetime.date(today.year, today.month, 1)
        ultimo_dia_mes_ant = primer_dia_mes_actual - datetime.timedelta(days=1)
        desde = datetime.date(ultimo_dia_mes_ant.year, ultimo_dia_mes_ant.month, 1)
        hasta = ultimo_dia_mes_ant
        return await _cargar_y_mostrar_lista(query, context, desde, hasta)

    if data == "gv_f_rango":
        await query.edit_message_text(
            "Ingresa el rango (DD/MM/YYYY - DD/MM/YYYY):",
            parse_mode="HTML",
        )
        return GV_RANGO_INPUT

    if data == "gv_cancelar":
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    return ConversationHandler.END


# ---------------------------------------------------------------------------
# GV_RANGO_INPUT state — user types a custom date range
# ---------------------------------------------------------------------------

_RANGO_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s*[-]\s*(\d{2}/\d{2}/\d{4})$"
)


def _parsear_rango(text: str) -> tuple[datetime.date, datetime.date] | None:
    """Parse 'DD/MM/YYYY - DD/MM/YYYY' and return (desde, hasta) or None if invalid."""
    m = _RANGO_PATTERN.match(text.strip())
    if not m:
        return None
    try:
        desde_str, hasta_str = m.group(1), m.group(2)
        desde = datetime.datetime.strptime(desde_str, "%d/%m/%Y").date()
        hasta = datetime.datetime.strptime(hasta_str, "%d/%m/%Y").date()
    except ValueError:
        return None
    if desde > hasta:
        return None
    return desde, hasta


async def handle_gv_rango_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and parse the custom date range typed by the user."""
    if update.effective_message is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    text = update.message.text if update.message else ""
    parsed = _parsear_rango(text or "")

    if parsed is None:
        await update.effective_message.reply_text(
            "Formato inválido. Ingresa el rango así: DD/MM/YYYY - DD/MM/YYYY",
            parse_mode="HTML",
        )
        return GV_RANGO_INPUT

    desde, hasta = parsed

    # Reuse the callback-query path: we need a CallbackQuery to edit_message_text.
    # For text messages we build a synthetic flow via the update's callback_query.
    # Since a text message has no callback_query, we reply with a new message instead.
    if context.user_data is not None:
        context.user_data["gv_desde"] = desde.isoformat()
        context.user_data["gv_hasta"] = hasta.isoformat()

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        logger.error("venta_repo not found in bot_data")
        return ConversationHandler.END

    ventas = await asyncio.to_thread(venta_repo.listar_para_gestion, desde)
    ventas = _filtrar_por_hasta(ventas, hasta)

    if not ventas:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.sin_ventas"),
            parse_mode="HTML",
        )
        _limpiar(context)
        return ConversationHandler.END

    # Use callback_query.edit_message_text if available; otherwise reply_text.
    query = update.callback_query
    if query is not None:
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.seleccionar"),
            reply_markup=_construir_teclado_ventas(ventas),
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.seleccionar"),
            reply_markup=_construir_teclado_ventas(ventas),
            parse_mode="HTML",
        )
    return GV_SELECCIONAR


# ---------------------------------------------------------------------------
# GV_SELECCIONAR — gv_atras navigation back to filter screen
# ---------------------------------------------------------------------------


async def handle_gv_seleccionar_atras(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the Atrás button from the ventas list → go back to the filter screen."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    await query.edit_message_text(
        "Selecciona el período de ventas a gestionar:",
        reply_markup=_construir_teclado_filtros(),
        parse_mode="HTML",
    )
    return GV_FILTRO


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
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    venta: Venta,
    *,
    modo_edicion: bool = False,
) -> int:
    """Resolve client + tour names, stash them, and edit the message into the
    detail view.  When modo_edicion=True the campo-edit keyboard is shown instead
    of the default detail keyboard, and GV_EDIT_CAMPO is returned."""
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

    canal_display = _TIPO_CLIENTE_LABEL.get(venta.tipo_cliente, venta.tipo_cliente.value)

    punto_line = ""
    if venta.tipo_cliente == TipoCliente.INTERNO and venta.participantes.punto_de_venta_id:
        pdv_repo = context.bot_data.get("pdv_repo")
        if pdv_repo is not None:
            pdv_id = venta.participantes.punto_de_venta_id
            punto = await asyncio.to_thread(pdv_repo.buscar_por_id, pdv_id)
            if punto is not None:
                punto_line = f"🏠 Punto: {punto.nombre}\n"

    origen_line = (
        f"📲 Origen: {escape(venta.canal_origen, quote=False)}\n" if venta.canal_origen else ""
    )

    vendedor_line = (
        f"{escape(venta.participantes.vendedor_nombre, quote=False)}\n"
        if venta.participantes.vendedor_nombre else ""
    )
    cerrador_line = (
        f"{escape(venta.participantes.cerrador_nombre, quote=False)}\n"
        if venta.participantes.cerrador_nombre else ""
    )

    # --- Pax ---
    pax_ninos = f" / {venta.ninos} niño(s)" if venta.ninos > 0 else ""
    pax = f"{venta.adultos} adulto(s){pax_ninos}"

    # --- Método de pago ---
    metodo_pago_line = (
        f"💳 Pago: {escape(venta.metodo_pago.value, quote=False)}\n"
        if venta.metodo_pago is not None else ""
    )

    # --- Ticket (best-effort) ---
    ticket_line = ""
    tiquetera_repo = context.bot_data.get("tiquetera_repo")
    if tiquetera_repo is not None:
        tiquetera = await asyncio.to_thread(tiquetera_repo.buscar_por_venta_id, venta.id)
        if tiquetera is not None and tiquetera.numero_fisico:
            ticket_line = f"🎫 Ticket: {escape(tiquetera.numero_fisico, quote=False)}\n"

    # --- Fecha de registro ---
    registrado_en_line = ""
    if venta.registrado_en is not None:
        registrado_en_line = f"🕐 Registrado: {venta.registrado_en:%d/%m/%Y %H:%M}\n"

    # --- Financiero ---
    abono = venta.abono
    abono_line = f"💵 Abono: {fmt_cop(abono)}\n" if abono is not None else ""
    saldo = (venta.valor_venta - abono) if abono is not None else venta.valor_venta

    # --- Comisiones (best-effort) ---
    comisiones_section = ""
    comision_repo: ComisionRegistradaRepository | None = context.bot_data.get(
        "comision_registrada_repo"
    )
    if comision_repo is not None:
        comision = await asyncio.to_thread(comision_repo.buscar_por_venta_id, venta.id)
        if comision is not None:
            d = comision.desglose
            lineas_com = ["\nComisiones:"]
            lineas_com.append(f"  Agencia: {fmt_cop(d.agencia)}")
            if venta.participantes.vendedor_nombre and d.vendedor.monto > 0:
                lineas_com.append(
                    f"  Vendedor ({escape(venta.participantes.vendedor_nombre, quote=False)})"
                    f": {fmt_cop(d.vendedor)}"
                )
            if venta.participantes.cerrador_nombre and d.cerrador.monto > 0:
                lineas_com.append(
                    f"  Cerrador ({escape(venta.participantes.cerrador_nombre, quote=False)})"
                    f": {fmt_cop(d.cerrador)}"
                )
            comisiones_section = "\n".join(lineas_com) + "\n"

    detail_text = obtener_mensaje("gestion_ventas.detalle").format(
        cliente=escape(cliente_nombre, quote=False),
        tours=escape(tours_str, quote=False),
        fecha=f"{venta.fecha:%d/%m/%Y}",
        registrado_en_line=registrado_en_line,
        canal=escape(canal_display, quote=False),
        punto_line=punto_line,
        origen_line=origen_line,
        pax=pax,
        metodo_pago_line=metodo_pago_line,
        ticket_line=ticket_line,
        valor=fmt_cop(venta.valor_venta),
        abono_line=abono_line,
        saldo=fmt_cop(saldo),
        neto=fmt_cop(venta.neto),
        ganancia=fmt_cop(venta.ganancia),
        comisiones_section=comisiones_section,
        vendedor_line=vendedor_line,
        cerrador_line=cerrador_line,
    )

    if modo_edicion:
        _user_for_auth = query.from_user
        _uid = _user_for_auth.id if _user_for_auth else 0
        _es_admin = await es_admin_o_propietario(_uid, context)
        keyboard = _construir_teclado_campos(venta, es_admin=_es_admin)
    else:
        keyboard = _construir_teclado_detalle()
    await query.edit_message_text(
        detail_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return GV_EDIT_CAMPO if modo_edicion else GV_DETALLE


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
        # Swap only the keyboard — keep the detail text visible so the user can
        # see current values while choosing which field to edit.
        venta_repo_ed: VentaRepository | None = context.bot_data.get("venta_repo")
        venta_id_str_ed = (context.user_data or {}).get("gv_venta_id")
        venta_ed = None
        if venta_repo_ed is not None and venta_id_str_ed:
            venta_ed = await asyncio.to_thread(
                venta_repo_ed.buscar_por_id, uuid.UUID(venta_id_str_ed)
            )
        if venta_ed is None:
            _limpiar(context)
            return await cerrar_flujo(update, context, GrupoComando.VENTAS)
        _user_ed = query.from_user
        _uid_ed = _user_ed.id if _user_ed else 0
        _es_admin_ed = await es_admin_o_propietario(_uid_ed, context)
        await query.edit_message_reply_markup(
            reply_markup=_construir_teclado_campos(venta_ed, es_admin=_es_admin_ed)
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
    """Rebuild the venta list and edit the message back to it (Atrás navigation).

    Uses the stored gv_desde/gv_hasta filter from user_data when available;
    falls back to the default 180-day window.
    """
    query = update.callback_query
    if query is None:
        return ConversationHandler.END

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    if venta_repo is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    user_data = context.user_data or {}
    desde_str: str | None = user_data.get("gv_desde")
    hasta_str: str | None = user_data.get("gv_hasta")

    if desde_str:
        desde = datetime.date.fromisoformat(desde_str)
    else:
        desde = datetime.date.today() - datetime.timedelta(days=_VENTANA_DIAS_GESTION)

    ventas = await asyncio.to_thread(venta_repo.listar_para_gestion, desde)

    if hasta_str:
        hasta = datetime.date.fromisoformat(hasta_str)
        ventas = _filtrar_por_hasta(ventas, hasta)

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

    if campo_str == "tipo_cliente":
        if context.user_data is not None:
            context.user_data["gv_accion"] = "editar_canal"
        actual_label = _TIPO_CLIENTE_LABEL.get(
            venta.tipo_cliente, venta.tipo_cliente.value
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.canal_interno"),
                callback_data="gv_canal:INTERNO",
            )],
            [InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.canal_externo"),
                callback_data="gv_canal:EXTERNO",
            )],
            [InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.canal_digital"),
                callback_data="gv_canal:DIGITAL",
            )],
            [InlineKeyboardButton(
                obtener_mensaje("gestion_ventas.boton_atras"),
                callback_data="gv_volver_detalle",
            )],
        ])
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.seleccionar_canal").format(
                actual=actual_label
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return GV_EDIT_CANAL_TIPO

    if campo_str in ("vendedor", "cerrador"):
        if context.user_data is not None:
            context.user_data["gv_accion"] = f"editar_{campo_str}"
        actual_nombre = (
            venta.participantes.vendedor_nombre
            if campo_str == "vendedor"
            else venta.participantes.cerrador_nombre
        ) or "—"
        rol_label = "Vendedor" if campo_str == "vendedor" else "Cerrador"
        if context.user_data is not None:
            context.user_data["gv_participante_anterior"] = actual_nombre

        freelancer_repo = context.bot_data.get("freelancer_repo")
        freelancers: list[object] = []
        if freelancer_repo is not None:
            freelancers = await asyncio.to_thread(freelancer_repo.listar_activos)
        keyboard_rows: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(
                getattr(f, "nombre", "?"),
                callback_data=f"gv_freelancer:{getattr(f, 'id', '')}",
            )]
            for f in freelancers
        ]
        keyboard_rows.append([InlineKeyboardButton(
            obtener_mensaje("gestion_ventas.boton_atras"),
            callback_data="gv_volver_detalle",
        )])
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.seleccionar_freelancer").format(
                rol=rol_label,
                actual=actual_nombre,
            ),
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            parse_mode="HTML",
        )
        return GV_EDIT_PARTICIPANTE

    if campo_str == "neto":
        # Financial field — admin/propietario/dev only.
        _user_neto = query.from_user
        _uid_neto = _user_neto.id if _user_neto else 0
        if not await es_admin_o_propietario(_uid_neto, context):
            _limpiar(context)
            return await cerrar_flujo(update, context, GrupoComando.VENTAS)
        if context.user_data is not None:
            context.user_data["gv_accion"] = "editar_neto"
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.pedir_neto").format(
                actual=fmt_cop(venta.neto),
            ),
            parse_mode="HTML",
        )
        return GV_EDIT_NETO

    if campo_str == "valor_venta":
        # Financial field — admin/propietario/dev only.
        _user_vv = query.from_user
        _uid_vv = _user_vv.id if _user_vv else 0
        if not await es_admin_o_propietario(_uid_vv, context):
            _limpiar(context)
            return await cerrar_flujo(update, context, GrupoComando.VENTAS)
        if context.user_data is not None:
            context.user_data["gv_accion"] = "editar_valor_venta"
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.pedir_valor_venta").format(
                actual=fmt_cop(venta.valor_venta),
            ),
            parse_mode="HTML",
        )
        return GV_EDIT_VALOR_VENTA

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
# GV_EDIT_NETO / GV_EDIT_VALOR_VENTA states — Decimal text capture for financial edits
# ---------------------------------------------------------------------------


async def handle_gv_capturar_neto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture the new neto text, validate it is a positive Decimal, store it, ask motivo."""
    if update.effective_message is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    text = (update.message.text if update.message else "") or ""
    valor_decimal = parsear_monto(text.strip())
    if valor_decimal is None or valor_decimal <= Decimal("0"):
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.neto_invalido"),
            parse_mode="HTML",
        )
        return GV_EDIT_NETO

    if context.user_data is not None:
        context.user_data["gv_nuevo_neto"] = str(valor_decimal)

    await update.effective_message.reply_text(
        obtener_mensaje("gestion_ventas.pedir_motivo_editar"),
        parse_mode="HTML",
    )
    return GV_MOTIVO


async def handle_gv_capturar_valor_venta(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Capture the new valor_venta text, validate it is a positive Decimal, store it, ask motivo."""
    if update.effective_message is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    text = (update.message.text if update.message else "") or ""
    valor_decimal = parsear_monto(text.strip())
    if valor_decimal is None or valor_decimal <= Decimal("0"):
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.valor_venta_invalido"),
            parse_mode="HTML",
        )
        return GV_EDIT_VALOR_VENTA

    if context.user_data is not None:
        context.user_data["gv_nuevo_valor_venta"] = str(valor_decimal)

    await update.effective_message.reply_text(
        obtener_mensaje("gestion_ventas.pedir_motivo_editar"),
        parse_mode="HTML",
    )
    return GV_MOTIVO


# ---------------------------------------------------------------------------
# GV_EDIT_CANAL_TIPO state — user picks new TipoCliente
# ---------------------------------------------------------------------------


async def handle_gv_edit_canal_tipo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle gv_canal:<TIPO> callback. INTERNO goes to punto selector; others go to motivo."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""

    if data == "gv_volver_detalle":
        venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
        venta_id_str = (context.user_data or {}).get("gv_venta_id")
        venta = None
        if venta_repo is not None and venta_id_str:
            venta = await asyncio.to_thread(venta_repo.buscar_por_id, uuid.UUID(venta_id_str))
        if venta is None:
            _limpiar(context)
            return await cerrar_flujo(update, context, GrupoComando.VENTAS)
        return await _render_detalle(query, context, venta, modo_edicion=True)

    tipo_str = data.removeprefix("gv_canal:")

    if context.user_data is not None:
        context.user_data["gv_nuevo_tipo"] = tipo_str

    if tipo_str == "INTERNO":
        # Load puntos de venta and show selector
        puntos_repo = context.bot_data.get("pdv_repo")
        puntos = []
        if puntos_repo is not None:
            puntos = await asyncio.to_thread(puntos_repo.listar)

        keyboard_rows = [
            [InlineKeyboardButton(p.nombre, callback_data=f"gv_punto:{p.id}")]
            for p in puntos
        ]
        await query.edit_message_text(
            obtener_mensaje("gestion_ventas.seleccionar_punto"),
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            parse_mode="HTML",
        )
        return GV_EDIT_CANAL_PUNTO

    # EXTERNO / DIGITAL: clear any stored punto_id and go directly to motivo
    if context.user_data is not None:
        context.user_data.pop("gv_punto_id", None)
        context.user_data["gv_punto_id"] = None

    await query.edit_message_text(
        obtener_mensaje("gestion_ventas.pedir_motivo_editar"),
        parse_mode="HTML",
    )
    return GV_MOTIVO


# ---------------------------------------------------------------------------
# GV_EDIT_CANAL_PUNTO state — user picks a punto de venta (INTERNO only)
# ---------------------------------------------------------------------------


async def handle_gv_edit_canal_punto(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle gv_punto:<uuid> callback. Stores punto_id and prompts for motivo."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""
    punto_id_str = data.removeprefix("gv_punto:")

    if context.user_data is not None:
        context.user_data["gv_punto_id"] = punto_id_str

    if update.effective_message is not None:
        await update.effective_message.reply_text(
            obtener_mensaje("gestion_ventas.pedir_motivo_editar"),
            parse_mode="HTML",
        )
    return GV_MOTIVO


# ---------------------------------------------------------------------------
# GV_EDIT_PARTICIPANTE state — user picks a freelancer from the list
# ---------------------------------------------------------------------------


async def handle_gv_edit_participante(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle gv_freelancer:<uuid> or gv_volver_detalle from the freelancer picker."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""

    if data == "gv_volver_detalle":
        venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
        venta_id_str = (context.user_data or {}).get("gv_venta_id")
        venta = None
        if venta_repo is not None and venta_id_str:
            venta = await asyncio.to_thread(
                venta_repo.buscar_por_id, uuid.UUID(venta_id_str)
            )
        if venta is None:
            _limpiar(context)
            return await cerrar_flujo(update, context, GrupoComando.VENTAS)
        return await _render_detalle(query, context, venta, modo_edicion=True)

    freelancer_id_str = data.removeprefix("gv_freelancer:")
    try:
        freelancer_id = uuid.UUID(freelancer_id_str)
    except ValueError:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    freelancer_repo = context.bot_data.get("freelancer_repo")
    freelancer = None
    if freelancer_repo is not None:
        freelancer = await asyncio.to_thread(freelancer_repo.buscar_por_id, freelancer_id)
    if freelancer is None:
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if context.user_data is not None:
        context.user_data["gv_nuevo_freelancer_id"] = str(freelancer_id)
        context.user_data["gv_nuevo_freelancer_nombre"] = freelancer.nombre

    await query.edit_message_text(
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
    elif gv_accion == "editar_canal":
        nuevo_tipo_str: str | None = user_data.get("gv_nuevo_tipo")
        confirm_text = obtener_mensaje("gestion_ventas.confirmar").format(motivo=motivo)
        if nuevo_tipo_str:
            confirm_text = (
                f"¿Confirmas cambiar el canal a <b>{nuevo_tipo_str}</b>?\n"
                f"Motivo: {motivo}"
            )
    elif gv_accion in ("editar_vendedor", "editar_cerrador"):
        rol_label = "Vendedor" if gv_accion == "editar_vendedor" else "Cerrador"
        nuevo_nombre = user_data.get("gv_nuevo_freelancer_nombre") or "—"
        anterior = user_data.get("gv_participante_anterior") or "—"
        confirm_text = obtener_mensaje("gestion_ventas.confirmar_editar_cliente").format(
            campo=rol_label,
            anterior=anterior,
            valor=nuevo_nombre,
            motivo=motivo,
        )
    elif gv_accion == "editar_neto":
        nuevo_neto_str: str | None = user_data.get("gv_nuevo_neto")
        confirm_text = obtener_mensaje("gestion_ventas.confirmar_editar_neto").format(
            valor=nuevo_neto_str or "—",
            motivo=motivo,
        )
    elif gv_accion == "editar_valor_venta":
        nuevo_vv_str: str | None = user_data.get("gv_nuevo_valor_venta")
        confirm_text = obtener_mensaje("gestion_ventas.confirmar_editar_valor_venta").format(
            valor=nuevo_vv_str or "—",
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

    if gv_accion == "editar_canal":
        return await _handle_confirmar_editar_canal(update, context, user_data, user)

    if gv_accion in ("editar_vendedor", "editar_cerrador"):
        return await _handle_confirmar_editar_participante(update, context, user_data, user)

    if gv_accion == "editar_neto":
        return await _handle_confirmar_editar_neto(update, context, user_data, user)

    if gv_accion == "editar_valor_venta":
        return await _handle_confirmar_editar_valor_venta(update, context, user_data, user)

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
    # Reload venta after service execution so we have the current mensaje_grupo_id.
    _venta_repo_fecha: VentaRepository | None = context.bot_data.get("venta_repo")
    _venta_fecha = None
    if _venta_repo_fecha is not None:
        _venta_fecha = await asyncio.to_thread(
            _venta_repo_fecha.buscar_por_id, uuid.UUID(venta_id_str)
        )
    if _venta_fecha is not None:
        await _notificar_edicion(
            context, _venta_fecha, mensaje_grupo, campo_label="Fecha",
            es_financiero=False,
        )
    else:
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

    mensaje_key_cliente: str | None = None
    try:
        await asyncio.to_thread(service.ejecutar, cmd)
    except LimiteEdicionesAlcanzado:
        mensaje_key_cliente = "gestion_ventas.limite_ediciones"
    except VentaNoEncontrada:
        mensaje_key_cliente = "gestion_ventas.no_encontrada"
    except ClienteNoEncontrado:
        mensaje_key_cliente = "gestion_ventas.no_encontrada"
    except MotivoRequerido:
        mensaje_key_cliente = "gestion_ventas.motivo_vacio"
    except Exception:
        logger.exception("Unexpected error in handle_gv_confirmar (editar_cliente)")
        mensaje_key_cliente = "gestion_ventas.error_generico"
    else:
        campo_label_c = (
            obtener_mensaje(_ETIQUETA_POR_CAMPO[CampoCliente(campo_str)])
            if campo_str
            else campo_str or "—"
        )
        mensaje_grupo_c = obtener_mensaje("gestion_ventas.correccion_edicion_participante").format(
            cliente=escape(user_data.get("gv_cliente_nombre") or "—", quote=False),
            tours=escape(user_data.get("gv_tours") or "—", quote=False),
            rol=campo_label_c,
            nuevo=escape(nuevo_valor, quote=False),
            motivo=escape(motivo, quote=False),
            actor=escape(nombre or "—", quote=False),
        )
        _venta_repo_c: VentaRepository | None = context.bot_data.get("venta_repo")
        _venta_c = None
        if _venta_repo_c is not None:
            _venta_c = await asyncio.to_thread(
                _venta_repo_c.buscar_por_id, uuid.UUID(venta_id_str)
            )
        if _venta_c is not None:
            await _notificar_edicion(
                context, _venta_c, mensaje_grupo_c, campo_label=campo_label_c,
                es_financiero=False,
            )
        else:
            await _notificar_grupo(context, mensaje_grupo_c)
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.cliente_editado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if update.effective_message and mensaje_key_cliente:
        await update.effective_message.reply_text(
            obtener_mensaje(mensaje_key_cliente),
            parse_mode="HTML",
        )
    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


async def _handle_confirmar_editar_canal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the editar-canal action."""
    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")
    nuevo_tipo_str: str | None = user_data.get("gv_nuevo_tipo")
    punto_id_str: str | None = user_data.get("gv_punto_id")

    if not venta_id_str or not motivo or not nuevo_tipo_str:
        logger.error("editar_canal confirm: incomplete state")
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

    try:
        nuevo_tipo = TipoCliente(nuevo_tipo_str)
    except ValueError:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    punto_id: uuid.UUID | None = None
    if punto_id_str and punto_id_str != "None":
        with contextlib.suppress(ValueError):
            punto_id = uuid.UUID(punto_id_str)

    cmd = EditarCanalVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        nuevo_tipo=nuevo_tipo,
        punto_id=punto_id,
        motivo=motivo,
        realizada_por_telegram_id=user_id,
        realizada_por_nombre=nombre,
    )

    service: EditarCanalVentaService | None = context.bot_data.get(
        "editar_canal_venta_service"
    )
    if service is None:
        logger.error("editar_canal_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    mensaje_key: str | None = None
    try:
        await asyncio.to_thread(service.ejecutar, cmd)
    except MismoCanal:
        canal_label = _TIPO_CLIENTE_LABEL.get(nuevo_tipo, nuevo_tipo_str)
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.canal_igual").format(canal=canal_label),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except PuntoDeVentaRequerido:
        mensaje_key = "gestion_ventas.punto_requerido"
    except VentaYaAnulada:
        mensaje_key = "gestion_ventas.ya_anulada"
    except LimiteEdicionesAlcanzado:
        mensaje_key = "gestion_ventas.limite_ediciones"
    except VentaNoEncontrada:
        mensaje_key = "gestion_ventas.no_encontrada"
    except MotivoRequerido:
        mensaje_key = "gestion_ventas.motivo_vacio"
    except DigitalConPuntoDeVenta:
        mensaje_key = "gestion_ventas.error_generico"
    except Exception:
        logger.exception("Unexpected error in _handle_confirmar_editar_canal")
        mensaje_key = "gestion_ventas.error_generico"
    else:
        # Success
        canal_label = _TIPO_CLIENTE_LABEL.get(nuevo_tipo, nuevo_tipo.value)
        punto_line_grupo = ""
        if nuevo_tipo == TipoCliente.INTERNO and punto_id is not None:
            pdv_repo = context.bot_data.get("pdv_repo")
            if pdv_repo is not None:
                pdv_obj = await asyncio.to_thread(pdv_repo.buscar_por_id, punto_id)
                if pdv_obj is not None:
                    punto_line_grupo = (
                        f"🏠 Punto: {escape(pdv_obj.nombre, quote=False)}\n"
                    )
        mensaje_grupo = obtener_mensaje("gestion_ventas.correccion_edicion_canal").format(
            cliente=escape(user_data.get("gv_cliente_nombre") or "—", quote=False),
            tours=escape(user_data.get("gv_tours") or "—", quote=False),
            canal=escape(canal_label, quote=False),
            punto_line=punto_line_grupo,
            motivo=escape(motivo, quote=False),
            actor=escape(nombre or "—", quote=False),
        )
        _venta_repo_canal: VentaRepository | None = context.bot_data.get("venta_repo")
        _venta_canal = None
        if _venta_repo_canal is not None:
            _venta_canal = await asyncio.to_thread(
                _venta_repo_canal.buscar_por_id, uuid.UUID(venta_id_str)
            )
        if _venta_canal is not None:
            await _notificar_edicion(
                context, _venta_canal, mensaje_grupo, campo_label="Canal",
                es_financiero=True,
            )
        else:
            await _notificar_grupo(context, mensaje_grupo)
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.canal_editado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if update.effective_message and mensaje_key:
        await update.effective_message.reply_text(
            obtener_mensaje(mensaje_key),
            parse_mode="HTML",
        )
    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


async def _handle_confirmar_editar_participante(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the editar-participante action (vendedor or cerrador)."""
    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")
    nuevo_fl_id_str: str | None = user_data.get("gv_nuevo_freelancer_id")
    nuevo_fl_nombre: str | None = user_data.get("gv_nuevo_freelancer_nombre")
    gv_accion: str = user_data.get("gv_accion", "")

    if not venta_id_str or not motivo or not nuevo_fl_id_str or not nuevo_fl_nombre:
        logger.error("editar_participante confirm: incomplete state")
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

    try:
        nuevo_fl_id = uuid.UUID(nuevo_fl_id_str)
    except ValueError:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    venta = None
    if venta_repo is not None:
        venta = await asyncio.to_thread(venta_repo.buscar_por_id, uuid.UUID(venta_id_str))
    if venta is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    es_vendedor = gv_accion == "editar_vendedor"
    cmd = EditarParticipantesVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        nuevo_vendedor_id=nuevo_fl_id if es_vendedor else venta.participantes.vendedor_id,
        nuevo_vendedor_nombre=(
            nuevo_fl_nombre if es_vendedor else venta.participantes.vendedor_nombre
        ),
        nuevo_cerrador_id=(
            venta.participantes.cerrador_id if es_vendedor else nuevo_fl_id
        ),
        nuevo_cerrador_nombre=(
            venta.participantes.cerrador_nombre if es_vendedor else nuevo_fl_nombre
        ),
        motivo=motivo,
        realizada_por_telegram_id=user_id,
        realizada_por_nombre=nombre,
    )

    service: EditarParticipantesVentaService | None = context.bot_data.get(
        "editar_participantes_venta_service"
    )
    if service is None:
        logger.error("editar_participantes_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    mensaje_key: str | None = None
    try:
        await asyncio.to_thread(service.ejecutar, cmd)
    except MismosParticipantes:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.mismo_participante"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)
    except VentaYaAnulada:
        mensaje_key = "gestion_ventas.ya_anulada"
    except LimiteEdicionesAlcanzado:
        mensaje_key = "gestion_ventas.limite_ediciones"
    except VentaNoEncontrada:
        mensaje_key = "gestion_ventas.no_encontrada"
    except MotivoRequerido:
        mensaje_key = "gestion_ventas.motivo_vacio"
    except Exception:
        logger.exception("Unexpected error in _handle_confirmar_editar_participante")
        mensaje_key = "gestion_ventas.error_generico"
    else:
        rol_label = "Vendedor" if es_vendedor else "Cerrador"
        mensaje_grupo = obtener_mensaje("gestion_ventas.correccion_edicion_participante").format(
            cliente=escape(user_data.get("gv_cliente_nombre") or "—", quote=False),
            tours=escape(user_data.get("gv_tours") or "—", quote=False),
            rol=escape(rol_label, quote=False),
            nuevo=escape(nuevo_fl_nombre, quote=False),
            motivo=escape(motivo, quote=False),
            actor=escape(nombre or "—", quote=False),
        )
        # venta is already loaded above — participante edit does not change mensaje_grupo_id.
        await _notificar_edicion(
            context, venta, mensaje_grupo, campo_label=rol_label, es_financiero=False
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.participante_editado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if update.effective_message and mensaje_key:
        await update.effective_message.reply_text(
            obtener_mensaje(mensaje_key),
            parse_mode="HTML",
        )
    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


async def _construir_textos_edicion_financiera(
    context: ContextTypes.DEFAULT_TYPE,
    venta: Venta,
    *,
    campo_label: str,
    anterior: str,
    nuevo: str,
    motivo: str,
    actor: str,
) -> tuple[str, str, str]:
    """Build the three notification texts for a financial edit (neto or valor_venta).

    Returns (mensaje_grupo_text, dm_socios_text, dm_admins_text).
    All three are pre-formatted HTML strings ready to pass to _notificar_edicion.
    Every step is best-effort: missing repos/data fall back to safe defaults.
    """
    # --- Resolve client data ---
    cliente_repo: ClienteRepository | None = context.bot_data.get("cliente_repo")
    cliente_nombre = "—"
    telefono_line = ""
    hotel_line = ""
    if cliente_repo is not None:
        cliente = await asyncio.to_thread(cliente_repo.buscar_por_id, venta.cliente_id)
        if cliente is not None:
            cliente_nombre = cliente.nombre
            if cliente.telefono:
                telefono_line = (
                    f"📞 Teléfono: {escape(cliente.telefono, quote=False)}\n"
                )
            if cliente.hotel:
                hab = (
                    f" | Hab: {escape(cliente.numero_habitacion, quote=False)}"
                    if cliente.numero_habitacion
                    else ""
                )
                hotel_line = (
                    f"🏨 Hotel: {escape(cliente.hotel, quote=False)}{hab}\n"
                )

    # --- Resolve tour names ---
    servicio_repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    tour_nombres: list[str] = []
    if servicio_repo is not None:
        for sid in venta.servicio_ids:
            svc = await asyncio.to_thread(servicio_repo.buscar_por_id, sid)
            if svc is not None:
                tour_nombres.append(escape(svc.nombre, quote=False))
    tours_str = ", ".join(tour_nombres) if tour_nombres else "—"

    # --- Resolve commissions ---
    comision_repo: ComisionRegistradaRepository | None = context.bot_data.get(
        "comision_registrada_repo"
    )
    desglose = None
    if comision_repo is not None:
        comision = await asyncio.to_thread(comision_repo.buscar_por_venta_id, venta.id)
        if comision is not None:
            desglose = comision.desglose

    # --- Resolve socios config ---
    socios_config_repo: SocioConfigRepository | None = context.bot_data.get(
        "socios_config_repo"
    )
    socios = []
    if socios_config_repo is not None:
        try:
            socios = await asyncio.to_thread(socios_config_repo.listar)
        except Exception:
            socios = []

    # --- Build optional line fragments ---
    destinos_line = f"📍 Destino: {tours_str}\n"
    fecha_line = f"📅 Fecha: {venta.fecha:%d/%m/%Y}\n"
    cliente_line = f"👤 Cliente: {escape(cliente_nombre, quote=False)}\n"
    pax_ninos = (
        f" / {venta.ninos} niño(s)" if venta.ninos > 0 else ""
    )
    pax_line = f"👥 Pax: {venta.adultos} adultos{pax_ninos}\n"
    canal_label = _TIPO_CLIENTE_LABEL.get(venta.tipo_cliente, venta.tipo_cliente.value)
    canal_line = f"\n📲 Canal: {escape(canal_label, quote=False)}"
    abono_dinero = venta.abono
    abono_line = ""
    if abono_dinero is not None and abono_dinero.monto > 0:
        abono_line = f" | Abono: {fmt_cop(abono_dinero)}"
    saldo = (
        venta.valor_venta - abono_dinero
        if abono_dinero is not None
        else venta.valor_venta
    )

    # Commissions section for group message
    tipo_label = venta.tipo_cliente.value
    metodo_pago_line = (
        f"\n💳 Pago: {escape(venta.metodo_pago.value, quote=False)}"
        if venta.metodo_pago is not None
        else ""
    )
    agencia_com = fmt_cop(desglose.agencia) if desglose else "—"
    vendedor_line_com = ""
    cerrador_line_com = ""
    if desglose is not None:
        snap = desglose.snapshot
        if venta.participantes.vendedor_nombre and desglose.vendedor.monto > 0:
            vendedor_line_com = (
                f"\n  Vendedor ({escape(venta.participantes.vendedor_nombre, quote=False)})"
                f": {fmt_cop(desglose.vendedor)}"
            )
        if venta.participantes.cerrador_nombre and desglose.cerrador.monto > 0:
            cerrador_line_com = (
                f"\n  Cerrador ({escape(venta.participantes.cerrador_nombre, quote=False)})"
                f": {fmt_cop(desglose.cerrador)}"
            )

    mensaje_grupo_text = obtener_mensaje("gestion_ventas.venta_actualizada_grupo").format(
        destinos_line=destinos_line,
        fecha_line=fecha_line,
        cliente_line=cliente_line,
        telefono_line=telefono_line,
        hotel_line=hotel_line,
        pax_line=pax_line,
        valor=fmt_cop(venta.valor_venta),
        abono_line=abono_line,
        saldo=fmt_cop(saldo),
        tipo=escape(tipo_label, quote=False),
        canal_line=canal_line,
        metodo_pago_line=metodo_pago_line,
        agencia=agencia_com,
        vendedor_line=vendedor_line_com,
        cerrador_line=cerrador_line_com,
        campo_label=escape(campo_label, quote=False),
        anterior=escape(anterior, quote=False),
        nuevo=escape(nuevo, quote=False),
        motivo=escape(motivo, quote=False),
        actor=escape(actor, quote=False),
    )

    # --- Build DM socios text ---
    ganancia = venta.ganancia
    neto = venta.neto
    comisiones_lines = ""
    if desglose is not None:
        snap = desglose.snapshot
        if venta.participantes.vendedor_nombre and desglose.vendedor.monto > 0:
            comisiones_lines += (
                f"👤 Vendedor ({snap.porcentaje_vendedor}%): {fmt_cop(desglose.vendedor)}\n"
            )
        if venta.participantes.cerrador_nombre and desglose.cerrador.monto > 0:
            comisiones_lines += (
                f"🔑 Cerrador ({snap.porcentaje_cerrador}%): {fmt_cop(desglose.cerrador)}\n"
            )
        if desglose.punto_de_venta.monto > 0:
            pct_pv = snap.porcentaje_capa_punto
            comisiones_lines += (
                f"🏪 Punto de venta ({pct_pv}%): {fmt_cop(desglose.punto_de_venta)}\n"
            )
    agencia_neta = fmt_cop(desglose.agencia) if desglose else "—"
    split_lines = ""
    for socio in socios:
        parte = desglose.agencia.aplicar_porcentaje(socio.porcentaje) if desglose else None
        if parte is not None:
            nombre_socio = escape(socio.nombre, quote=False)
            split_lines += (
                f"   📊 {nombre_socio} ({socio.porcentaje}%): {fmt_cop(parte)}\n"
            )
    # mi_parte is the total agencia net (shown to every socio equally)
    mi_parte = fmt_cop(desglose.agencia) if desglose else "—"

    dm_socios_text = obtener_mensaje("gestion_ventas.dm_socio_edicion_financiera").format(
        destinos_line=destinos_line,
        fecha_line=f"📅 Fecha: {venta.fecha:%d/%m/%Y}",
        valor=fmt_cop(venta.valor_venta),
        neto=fmt_cop(neto),
        ganancia=fmt_cop(ganancia),
        comisiones_lines=comisiones_lines,
        agencia=agencia_neta,
        split_lines=split_lines,
        mi_parte=mi_parte,
        campo_label=escape(campo_label, quote=False),
        anterior=escape(anterior, quote=False),
        nuevo=escape(nuevo, quote=False),
    )

    # --- Build DM admins text ---
    dm_admins_text = obtener_mensaje("gestion_ventas.dm_admin_edicion").format(
        cliente=escape(cliente_nombre, quote=False),
        tours=tours_str,
        campo_label=escape(campo_label, quote=False),
        anterior=escape(anterior, quote=False),
        nuevo=escape(nuevo, quote=False),
        actor=escape(actor, quote=False),
    )

    return mensaje_grupo_text, dm_socios_text, dm_admins_text


async def _handle_confirmar_editar_neto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the editar-neto action."""

    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")
    nuevo_neto_str: str | None = user_data.get("gv_nuevo_neto")

    if not venta_id_str or not motivo or not nuevo_neto_str:
        logger.error("editar_neto confirm: incomplete state")
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

    # Load the venta to know its currency for the Dinero object.
    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    venta = None
    if venta_repo is not None:
        venta = await asyncio.to_thread(venta_repo.buscar_por_id, uuid.UUID(venta_id_str))
    if venta is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    try:
        nuevo_neto = Dinero(Decimal(nuevo_neto_str), venta.neto.moneda)
    except Exception:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.neto_invalido"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    cmd = EditarNetoVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        nuevo_neto=nuevo_neto,
        motivo=motivo,
        realizada_por_telegram_id=user_id,
        realizada_por_nombre=nombre,
    )

    service: EditarNetoVentaService | None = context.bot_data.get("editar_neto_venta_service")
    if service is None:
        logger.error("editar_neto_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    # Capture the old value before the service mutates the entity in-place.
    anterior_neto_str = fmt_cop(venta.neto)
    mensaje_key: str | None = None
    try:
        await asyncio.to_thread(service.ejecutar, cmd)
    except MismoNeto:
        mensaje_key = "gestion_ventas.neto_igual"
    except NetoIgualOSuperaValorVenta:
        mensaje_key = "gestion_ventas.neto_supera_valor"
    except VentaYaAnulada:
        mensaje_key = "gestion_ventas.ya_anulada"
    except LimiteEdicionesAlcanzado:
        mensaje_key = "gestion_ventas.limite_ediciones"
    except VentaNoEncontrada:
        mensaje_key = "gestion_ventas.no_encontrada"
    except MotivoRequerido:
        mensaje_key = "gestion_ventas.motivo_vacio"
    except Exception:
        logger.exception("Unexpected error in _handle_confirmar_editar_neto")
        mensaje_key = "gestion_ventas.error_generico"
    else:
        # Reload venta from repo so it reflects the updated neto and recalculated comisiones.
        venta_actualizada: Venta | None = None
        if venta_repo is not None:
            venta_actualizada = await asyncio.to_thread(
                venta_repo.buscar_por_id, uuid.UUID(venta_id_str)
            )
        _venta_para_notif = venta_actualizada if venta_actualizada is not None else venta
        campo_label_neto = obtener_mensaje("gestion_ventas.campo_neto")
        mensaje_grupo_text, dm_socios_text, dm_admins_text = (
            await _construir_textos_edicion_financiera(
                context,
                _venta_para_notif,
                campo_label=campo_label_neto,
                anterior=anterior_neto_str,
                nuevo=fmt_cop(nuevo_neto),
                motivo=motivo,
                actor=nombre or "—",
            )
        )
        await _notificar_edicion(
            context,
            _venta_para_notif,
            mensaje_grupo_text,
            campo_label=campo_label_neto,
            es_financiero=True,
            dm_socios_text=dm_socios_text,
            dm_admins_text=dm_admins_text,
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.neto_editado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if update.effective_message and mensaje_key:
        await update.effective_message.reply_text(
            obtener_mensaje(mensaje_key),
            parse_mode="HTML",
        )
    _limpiar(context)
    return await cerrar_flujo(update, context, GrupoComando.VENTAS)


async def _handle_confirmar_editar_valor_venta(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,  # type: ignore[type-arg]
    user: object,
) -> int:
    """Handle confirmation for the editar-valor-venta action."""

    venta_id_str: str | None = user_data.get("gv_venta_id")
    motivo: str | None = user_data.get("gv_motivo")
    nuevo_vv_str: str | None = user_data.get("gv_nuevo_valor_venta")

    if not venta_id_str or not motivo or not nuevo_vv_str:
        logger.error("editar_valor_venta confirm: incomplete state")
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

    # Load the venta to know its currency for the Dinero object.
    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    venta = None
    if venta_repo is not None:
        venta = await asyncio.to_thread(venta_repo.buscar_por_id, uuid.UUID(venta_id_str))
    if venta is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.no_encontrada"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    try:
        nuevo_vv = Dinero(Decimal(nuevo_vv_str), venta.valor_venta.moneda)
    except Exception:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.valor_venta_invalido"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    cmd = EditarValorVentaComando(
        venta_id=uuid.UUID(venta_id_str),
        nuevo_valor_venta=nuevo_vv,
        motivo=motivo,
        realizada_por_telegram_id=user_id,
        realizada_por_nombre=nombre,
    )

    service: EditarValorVentaService | None = context.bot_data.get(
        "editar_valor_venta_service"
    )
    if service is None:
        logger.error("editar_valor_venta_service not found in bot_data — wiring error")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.error_generico"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    # Capture the old value before the service mutates the entity in-place.
    anterior_vv_str = fmt_cop(venta.valor_venta)
    mensaje_key: str | None = None
    try:
        await asyncio.to_thread(service.ejecutar, cmd)
    except MismoValorVenta:
        mensaje_key = "gestion_ventas.valor_venta_igual"
    except NetoIgualOSuperaValorVenta:
        mensaje_key = "gestion_ventas.neto_supera_valor"
    except ValorVentaMenorQueAbono:
        mensaje_key = "gestion_ventas.valor_menor_abono"
    except VentaYaAnulada:
        mensaje_key = "gestion_ventas.ya_anulada"
    except LimiteEdicionesAlcanzado:
        mensaje_key = "gestion_ventas.limite_ediciones"
    except VentaNoEncontrada:
        mensaje_key = "gestion_ventas.no_encontrada"
    except MotivoRequerido:
        mensaje_key = "gestion_ventas.motivo_vacio"
    except Exception:
        logger.exception("Unexpected error in _handle_confirmar_editar_valor_venta")
        mensaje_key = "gestion_ventas.error_generico"
    else:
        # Reload venta from repo so it reflects the updated valor_venta and recalculated comisiones.
        venta_actualizada_vv: Venta | None = None
        if venta_repo is not None:
            venta_actualizada_vv = await asyncio.to_thread(
                venta_repo.buscar_por_id, uuid.UUID(venta_id_str)
            )
        _venta_para_notif_vv = venta_actualizada_vv if venta_actualizada_vv is not None else venta
        campo_label_vv = obtener_mensaje("gestion_ventas.campo_valor_venta")
        mensaje_grupo_text, dm_socios_text, dm_admins_text = (
            await _construir_textos_edicion_financiera(
                context,
                _venta_para_notif_vv,
                campo_label=campo_label_vv,
                anterior=anterior_vv_str,
                nuevo=fmt_cop(nuevo_vv),
                motivo=motivo,
                actor=nombre or "—",
            )
        )
        await _notificar_edicion(
            context,
            _venta_para_notif_vv,
            mensaje_grupo_text,
            campo_label=campo_label_vv,
            es_financiero=True,
            dm_socios_text=dm_socios_text,
            dm_admins_text=dm_admins_text,
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("gestion_ventas.valor_venta_editado"),
                parse_mode="HTML",
            )
        _limpiar(context)
        return await cerrar_flujo(update, context, GrupoComando.VENTAS)

    if update.effective_message and mensaje_key:
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
