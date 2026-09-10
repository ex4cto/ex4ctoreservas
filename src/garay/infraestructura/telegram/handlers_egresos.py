"""PTB handlers for /nuevo_egreso and /gastos_fijos."""

from __future__ import annotations

import datetime
import logging
import uuid
import zoneinfo
from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.comun.fechas import parsear_fecha
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.categorias import (
    CATEGORIA_TRANSPORTE,
    es_categoria_duplicada,
    es_categoria_protegida,
    sugerir_categoria_parecida,
)
from garay.dominio.conciliacion.entidades import CategoriaEgreso, GastoRecurrente
from garay.dominio.conciliacion.errores import CategoriaEgresoProtegida
from garay.infraestructura.telegram.auth import requiere_admin, requiere_admin_conv
from garay.mensajes.catalogo import formatear_html, obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 100-120 to avoid collision with tiquetera (0-24)
# ---------------------------------------------------------------------------

EGRESO_MONTO: int = 100
EGRESO_DESCRIPCION: int = 101
EGRESO_CATEGORIA: int = 102
EGRESO_FECHA: int = 103
EGRESO_CONFIRMACION: int = 104
EGRESO_EDIT_MENU: int = 105  # "Otro" edit field menu
EGRESO_DESTINATARIO: int = 106  # "¿A quién?" (opcional) en la rama Otro
EGRESO_DUP_CONFIRM: int = 107  # confirmar posible duplicado de transporte

# New states for recurring egreso branch
EGRESO_SELECCION: int = 120
EGRESO_REC_MONTO: int = 121
EGRESO_REC_FECHA: int = 122
EGRESO_REC_CONFIRM: int = 123
EGRESO_REC_EDIT_MENU: int = 124  # Recurring edit field menu

# Callback data constants
PREFIJO_REC: str = "egr_rec:"
CB_OTRO_EGRESO: str = "egr_otro"
CB_CANCELAR_SEL: str = "egr_cancelar"
CB_USAR_SUGERIDO: str = "egr_sugerido"
CB_HOY: str = "egr_hoy"
CB_CONFIRMAR: str = "confirmar"
CB_CANCELAR: str = "cancelar"
CB_EDITAR: str = "egr_editar"
# Edit menu field selectors — "Otro" branch
CB_EDIT_MONTO: str = "egr_edit_monto"
CB_EDIT_DESCRIPCION: str = "egr_edit_desc"
CB_EDIT_CATEGORIA: str = "egr_edit_cat"
CB_EDIT_FECHA: str = "egr_edit_fecha"
CB_EDIT_DESTINATARIO: str = "egr_edit_dest"
CB_EDIT_VOLVER: str = "egr_edit_volver"
CB_OMITIR: str = "egr_omitir"
CB_DUP_OTRO: str = "egr_dup_otro"  # "Sí, es otro" en la guardia de duplicado
# (CB_EDIT_MONTO, CB_EDIT_FECHA, CB_EDIT_VOLVER are shared with recurring branch)

GF_NOMBRE: int = 110
GF_MONTO: int = 111
GF_CATEGORIA: int = 112
GF_DIA: int = 113
GF_CONFIRMACION: int = 114

# ---------------------------------------------------------------------------
# Bogota timezone helper (local — avoids circular import with bot.py)
# ---------------------------------------------------------------------------

_ZONA_BOGOTA: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("America/Bogota")


def _hoy_bogota() -> datetime.date:
    """Current date in Bogota timezone. Testable via monkeypatching."""
    return datetime.datetime.now(_ZONA_BOGOTA).date()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parsear_monto_cop(texto: str) -> Decimal | None:
    """Parse Colombian peso amount.

    Plain numbers < 1000 are treated as miles de pesos.
    """
    limpio = texto.strip().replace(".", "").replace(",", "")
    try:
        valor = Decimal(limpio)
        if valor <= Decimal("0"):
            return None
        if Decimal("0") < valor < Decimal("1000"):
            valor = valor * 1000
        return valor
    except InvalidOperation:
        return None


def _fmt_cop(valor: Decimal) -> str:
    return "$" + f"{int(valor):,}".replace(",", ".")


def _teclado_inline(opciones: list[str]) -> InlineKeyboardMarkup:
    botones = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones]
    return InlineKeyboardMarkup(botones)


def _teclado_omitir() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(obtener_mensaje("egreso.boton_omitir"), callback_data=CB_OMITIR)]]
    )


def _teclado_dup() -> InlineKeyboardMarkup:
    otro = InlineKeyboardButton(
        obtener_mensaje("egreso.boton_dup_otro"), callback_data=CB_DUP_OTRO
    )
    cancelar = InlineKeyboardButton(
        obtener_mensaje("egreso.boton_cancelar"), callback_data=CB_CANCELAR
    )
    return InlineKeyboardMarkup([[otro], [cancelar]])


def _posible_duplicado_transporte(
    context: ContextTypes.DEFAULT_TYPE, ud: dict[str, object], fecha: datetime.date
) -> bool:
    """True si ya existe un egreso de transporte del mismo monto en ventana ±2 días."""
    if str(ud.get("egreso_categoria", "")) != CATEGORIA_TRANSPORTE:
        return False
    monto = ud.get("egreso_monto")
    if not isinstance(monto, Decimal):
        return False
    egreso_repo = context.bot_data.get("egreso_repo")
    if egreso_repo is None:
        return False
    desde = fecha - datetime.timedelta(days=2)
    hasta = fecha + datetime.timedelta(days=2)
    existentes = egreso_repo.listar_por_periodo(desde, hasta)
    return any(e.monto.monto == monto for e in existentes)


def _teclado_confirmar_cancelar() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_confirmar"), callback_data=CB_CONFIRMAR
                ),
                InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_editar"), callback_data=CB_EDITAR
                ),
                InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_cancelar"), callback_data=CB_CANCELAR
                ),
            ]
        ]
    )


async def _reply(update: Update, texto: str, teclado: InlineKeyboardMarkup | None = None) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            texto, reply_markup=teclado, parse_mode="HTML"
        )
    elif update.effective_message is not None:
        await update.effective_message.reply_text(
            texto, reply_markup=teclado, parse_mode="HTML"
        )


def _input_text(update: Update) -> str:
    if update.callback_query is not None:
        return update.callback_query.data or ""
    if update.message is not None and update.message.text:
        return update.message.text
    return ""


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict[str, object]:
    """Return user_data, never None (PTB always initialises it for conversation handlers)."""
    if context.user_data is None:
        return {}
    return context.user_data


def _resumen_otro(ud: dict[str, object]) -> str:
    monto: Decimal = ud.get("egreso_monto", Decimal("0"))  # type: ignore[assignment]
    descripcion: str = ud.get("egreso_descripcion", "")  # type: ignore[assignment]
    categoria: str = ud.get("egreso_categoria", "")  # type: ignore[assignment]
    destinatario_val = ud.get("egreso_destinatario")
    destinatario = str(destinatario_val) if destinatario_val else "—"
    fecha: datetime.date = ud.get("egreso_fecha", datetime.date.today())  # type: ignore[assignment]
    return formatear_html(
        obtener_mensaje("egreso.confirmar_resumen"),
        monto=_fmt_cop(monto),
        descripcion=descripcion,
        categoria=categoria,
        destinatario=destinatario,
        fecha=fecha.strftime("%d/%m/%Y"),
    )


def _resumen_rec(ud: dict[str, object]) -> str:
    nombre: str = ud.get("rec_nombre", "")  # type: ignore[assignment]
    monto: Decimal = ud.get("rec_monto", Decimal("0"))  # type: ignore[assignment]
    categoria: str = ud.get("rec_categoria", "")  # type: ignore[assignment]
    fecha: datetime.date = ud.get("rec_fecha", datetime.date.today())  # type: ignore[assignment]
    return formatear_html(
        obtener_mensaje("egreso.rec_confirmar_resumen"),
        nombre=nombre,
        monto=_fmt_cop(monto),
        fecha=fecha.strftime("%d/%m/%Y"),
        categoria=categoria,
    )


# ---------------------------------------------------------------------------
# /nuevo_egreso — ConversationHandler states
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_nuevo_egreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /nuevo_egreso."""
    service = context.bot_data.get("recurrente_service")
    gastos: list[GastoRecurrente] = service.listar_activos() if service else []
    egreso_repo = context.bot_data.get("egreso_repo")
    hoy = _hoy_bogota()
    filas: list[list[InlineKeyboardButton]] = []
    for g in gastos:
        label = f"{g.nombre} — {_fmt_cop(g.monto.monto)}"
        if egreso_repo is not None:
            pagado = egreso_repo.sumar_por_recurrente_en_mes(g.id, hoy.year, hoy.month)
            if pagado.monto > Decimal("0"):
                label = label + obtener_mensaje("egreso.indicador_pagado").format(
                    pagado=_fmt_cop(pagado.monto)
                )
        filas.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"{PREFIJO_REC}{g.id}",
                )
            ]
        )
    filas.append(
        [InlineKeyboardButton(obtener_mensaje("egreso.boton_otro"), callback_data=CB_OTRO_EGRESO)]
    )
    filas.append(
        [
            InlineKeyboardButton(
                obtener_mensaje("egreso.boton_cancelar"), callback_data=CB_CANCELAR_SEL
            )
        ]
    )
    titulo = (
        obtener_mensaje("egreso.seleccion_titulo")
        if gastos
        else obtener_mensaje("egreso.seleccion_sin_recurrentes")
    )
    await _reply(update, titulo, InlineKeyboardMarkup(filas))
    return EGRESO_SELECCION


async def handle_egreso_seleccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    if texto == CB_CANCELAR_SEL:
        await _reply(update, obtener_mensaje("venta_cancelada"))
        return ConversationHandler.END
    if texto == CB_OTRO_EGRESO:
        service = context.bot_data.get("egreso_service")
        categorias_otro: list[str] = service.listar_categorias() if service else []
        await _reply(
            update, obtener_mensaje("egreso.pedir_categoria"), _teclado_inline(categorias_otro)
        )
        return EGRESO_CATEGORIA
    # Pattern: PREFIJO_REC + uuid
    if texto.startswith(PREFIJO_REC):
        rec_id_str = texto[len(PREFIJO_REC):]
        try:
            rec_id = uuid.UUID(rec_id_str)
        except ValueError:
            await _reply(update, obtener_mensaje("egreso.recurrente_no_encontrado"))
            return ConversationHandler.END
        service = context.bot_data.get("recurrente_service")
        gastos: list[GastoRecurrente] = service.listar_activos() if service else []
        gasto = next((g for g in gastos if g.id == rec_id), None)
        if gasto is None:
            await _reply(update, obtener_mensaje("egreso.recurrente_no_encontrado"))
            return ConversationHandler.END
        ud = _ud(context)
        ud["rec_id"] = gasto.id
        ud["rec_nombre"] = gasto.nombre
        ud["rec_categoria"] = gasto.categoria
        ud["rec_monto_sugerido"] = gasto.monto.monto
        monto_fmt = _fmt_cop(gasto.monto.monto)
        teclado = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        obtener_mensaje("egreso.boton_usar_sugerido").format(
                            monto_sugerido=monto_fmt
                        ),
                        callback_data=CB_USAR_SUGERIDO,
                    )
                ]
            ]
        )
        await _reply(
            update,
            formatear_html(
                obtener_mensaje("egreso.rec_pedir_monto"),
                nombre=gasto.nombre,
                monto_sugerido=monto_fmt,
            ),
            teclado,
        )
        return EGRESO_REC_MONTO
    # Unknown callback
    await _reply(update, obtener_mensaje("venta_cancelada"))
    return ConversationHandler.END


async def handle_egreso_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    monto = _parsear_monto_cop(texto)
    if monto is None:
        await _reply(update, obtener_mensaje("egreso.error_monto"))
        return EGRESO_MONTO
    ud = _ud(context)
    ud["egreso_monto"] = monto
    if ud.get("editando"):
        ud["editando"] = False
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    teclado_hoy = InlineKeyboardMarkup(
        [[InlineKeyboardButton(obtener_mensaje("egreso.boton_hoy"), callback_data=CB_HOY)]]
    )
    await _reply(update, obtener_mensaje("egreso.pedir_fecha"), teclado_hoy)
    return EGRESO_FECHA


async def handle_egreso_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update).strip()
    ud = _ud(context)
    ud["egreso_descripcion"] = texto
    if ud.get("editando"):
        ud["editando"] = False
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    await _reply(update, obtener_mensaje("egreso.pedir_monto"))
    return EGRESO_MONTO


async def handle_egreso_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    categoria = _input_text(update).strip()
    service = context.bot_data.get("egreso_service")
    categorias: list[str] = service.listar_categorias() if service else []
    if categoria not in categorias:
        teclado = _teclado_inline(categorias)
        await _reply(update, obtener_mensaje("egreso.error_categoria"), teclado)
        return EGRESO_CATEGORIA
    ud = _ud(context)
    ud["egreso_categoria"] = categoria
    if ud.get("editando"):
        ud["editando"] = False
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    prompt = obtener_mensaje("egreso.pedir_destinatario")
    if categoria == CATEGORIA_TRANSPORTE:
        prompt = obtener_mensaje("egreso.transporte_aviso") + "\n\n" + prompt
    await _reply(update, prompt, _teclado_omitir())
    return EGRESO_DESTINATARIO


async def handle_egreso_destinatario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """'¿A quién?' — opcional. Botón Omitir o texto libre. Reutiliza Egreso.destinatario."""
    texto = _input_text(update)
    ud = _ud(context)
    if texto == CB_OMITIR:
        ud["egreso_destinatario"] = None
    else:
        limpio = texto.strip()
        ud["egreso_destinatario"] = limpio or None
    if ud.get("editando"):
        ud["editando"] = False
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    await _reply(update, obtener_mensaje("egreso.pedir_descripcion"))
    return EGRESO_DESCRIPCION


async def handle_egreso_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    if texto == CB_HOY:
        fecha: datetime.date | None = _hoy_bogota()
    else:
        resultado = parsear_fecha(texto)
        fecha = resultado.date() if resultado is not None else None
    if fecha is None:
        await _reply(update, obtener_mensaje("egreso.error_fecha"))
        return EGRESO_FECHA
    ud = _ud(context)
    ud["egreso_fecha"] = fecha
    editando = bool(ud.get("editando"))
    ud["editando"] = False
    if not editando and _posible_duplicado_transporte(context, ud, fecha):
        monto_val: Decimal = ud.get("egreso_monto", Decimal("0"))  # type: ignore[assignment]
        aviso = formatear_html(
            obtener_mensaje("egreso.dup_aviso"),
            monto=_fmt_cop(monto_val),
            fecha=fecha.strftime("%d/%m/%Y"),
        )
        await _reply(update, aviso, _teclado_dup())
        return EGRESO_DUP_CONFIRM
    await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
    return EGRESO_CONFIRMACION


async def handle_egreso_dup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirmar un posible duplicado de transporte: 'Sí, es otro' o cancelar."""
    accion = _input_text(update).strip()
    ud = _ud(context)
    if accion == CB_DUP_OTRO:
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    await _reply(update, obtener_mensaje("venta_cancelada"))
    return ConversationHandler.END


async def handle_egreso_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    accion = _input_text(update).strip()
    if accion == CB_EDITAR:
        teclado = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_monto"), callback_data=CB_EDIT_MONTO
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_descripcion"), callback_data=CB_EDIT_DESCRIPCION
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_categoria_label"),
                    callback_data=CB_EDIT_CATEGORIA,
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_destinatario_label"),
                    callback_data=CB_EDIT_DESTINATARIO,
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_fecha"), callback_data=CB_EDIT_FECHA
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_volver"), callback_data=CB_EDIT_VOLVER
                )],
            ]
        )
        await _reply(update, obtener_mensaje("egreso.edit_menu_otro"), teclado)
        return EGRESO_EDIT_MENU
    if accion != CB_CONFIRMAR:
        await _reply(update, obtener_mensaje("venta_cancelada"))
        return ConversationHandler.END
    service = context.bot_data.get("egreso_service")
    if service is None:
        logger.error("egreso_service not found in bot_data")
        return ConversationHandler.END
    ud = _ud(context)
    monto: Decimal = ud.get("egreso_monto")  # type: ignore[assignment]
    descripcion: str = ud.get("egreso_descripcion")  # type: ignore[assignment]
    categoria: str = ud.get("egreso_categoria")  # type: ignore[assignment]
    fecha: datetime.date = ud.get("egreso_fecha")  # type: ignore[assignment]
    destinatario: str | None = ud.get("egreso_destinatario")  # type: ignore[assignment]
    from garay.config.settings import obtener_settings

    moneda = obtener_settings().moneda_predeterminada
    try:
        service.registrar(
            monto=monto,
            descripcion=descripcion,
            categoria=categoria,
            fecha=fecha,
            moneda=moneda,
            destinatario=destinatario,
        )
    except Exception:
        logger.exception("Error registrando egreso manual")
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END
    await _reply(update, obtener_mensaje("egreso.registrado"))
    return ConversationHandler.END


async def handle_egreso_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Route field selection for the 'Otro' branch edit menu."""
    accion = _input_text(update).strip()
    ud = _ud(context)
    if accion == CB_EDIT_VOLVER:
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    if accion == CB_EDIT_MONTO:
        ud["editando"] = True
        await _reply(update, obtener_mensaje("egreso.pedir_monto"))
        return EGRESO_MONTO
    if accion == CB_EDIT_DESCRIPCION:
        ud["editando"] = True
        await _reply(update, obtener_mensaje("egreso.pedir_descripcion"))
        return EGRESO_DESCRIPCION
    if accion == CB_EDIT_CATEGORIA:
        ud["editando"] = True
        service = context.bot_data.get("egreso_service")
        categorias: list[str] = service.listar_categorias() if service else []
        teclado = _teclado_inline(categorias)
        await _reply(update, obtener_mensaje("egreso.pedir_categoria"), teclado)
        return EGRESO_CATEGORIA
    if accion == CB_EDIT_DESTINATARIO:
        ud["editando"] = True
        await _reply(update, obtener_mensaje("egreso.pedir_destinatario"), _teclado_omitir())
        return EGRESO_DESTINATARIO
    if accion == CB_EDIT_FECHA:
        ud["editando"] = True
        teclado_hoy = InlineKeyboardMarkup(
            [[InlineKeyboardButton(obtener_mensaje("egreso.boton_hoy"), callback_data=CB_HOY)]]
        )
        await _reply(update, obtener_mensaje("egreso.pedir_fecha"), teclado_hoy)
        return EGRESO_FECHA
    # Unknown — return to summary
    await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
    return EGRESO_CONFIRMACION


# ---------------------------------------------------------------------------
# /nuevo_egreso — recurring branch (egreso originating from a GastoRecurrente)
# ---------------------------------------------------------------------------


async def handle_egreso_rec_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    ud = _ud(context)
    monto: Decimal
    if texto == CB_USAR_SUGERIDO:
        sugerido = ud.get("rec_monto_sugerido")
        if not isinstance(sugerido, Decimal):
            await _reply(update, obtener_mensaje("egreso.sesion_expirada"))
            return ConversationHandler.END
        monto = sugerido
    else:
        parsed = _parsear_monto_cop(texto)
        if parsed is None:
            await _reply(update, obtener_mensaje("egreso.error_monto"))
            return EGRESO_REC_MONTO
        monto = parsed
    ud["rec_monto"] = monto
    if ud.get("editando"):
        ud["editando"] = False
        await _reply(update, _resumen_rec(ud), _teclado_confirmar_cancelar())
        return EGRESO_REC_CONFIRM
    teclado_hoy = InlineKeyboardMarkup(
        [[InlineKeyboardButton(obtener_mensaje("egreso.boton_hoy"), callback_data=CB_HOY)]]
    )
    await _reply(update, obtener_mensaje("egreso.rec_pedir_fecha"), teclado_hoy)
    return EGRESO_REC_FECHA


async def handle_egreso_rec_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    if texto == CB_HOY:
        fecha: datetime.date = datetime.date.today()
    else:
        resultado = parsear_fecha(texto)
        if resultado is None:
            await _reply(update, obtener_mensaje("egreso.error_fecha"))
            return EGRESO_REC_FECHA
        fecha = resultado.date()
    ud = _ud(context)
    ud["rec_fecha"] = fecha
    if ud.get("editando"):
        ud["editando"] = False
    await _reply(update, _resumen_rec(ud), _teclado_confirmar_cancelar())
    return EGRESO_REC_CONFIRM


async def handle_egreso_rec_confirmacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    accion = _input_text(update).strip()
    if accion == CB_EDITAR:
        teclado = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_monto"), callback_data=CB_EDIT_MONTO
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_fecha"), callback_data=CB_EDIT_FECHA
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("egreso.boton_volver"), callback_data=CB_EDIT_VOLVER
                )],
            ]
        )
        await _reply(update, obtener_mensaje("egreso.edit_menu_rec"), teclado)
        return EGRESO_REC_EDIT_MENU
    if accion != CB_CONFIRMAR:
        await _reply(update, obtener_mensaje("venta_cancelada"))
        return ConversationHandler.END
    service = context.bot_data.get("egreso_service")
    if service is None:
        logger.error("egreso_service not found in bot_data")
        return ConversationHandler.END
    ud = _ud(context)
    requeridos = ("rec_id", "rec_nombre", "rec_categoria", "rec_monto", "rec_fecha")
    if any(ud.get(clave) is None for clave in requeridos):
        await _reply(update, obtener_mensaje("egreso.sesion_expirada"))
        return ConversationHandler.END
    rec_id: uuid.UUID = ud.get("rec_id")  # type: ignore[assignment]
    nombre: str = ud.get("rec_nombre")  # type: ignore[assignment]
    categoria: str = ud.get("rec_categoria")  # type: ignore[assignment]
    monto: Decimal = ud.get("rec_monto")  # type: ignore[assignment]
    fecha: datetime.date = ud.get("rec_fecha")  # type: ignore[assignment]
    from garay.config.settings import obtener_settings

    moneda = obtener_settings().moneda_predeterminada
    try:
        service.registrar(
            monto=monto,
            descripcion=nombre,
            categoria=categoria,
            fecha=fecha,
            moneda=moneda,
            gasto_recurrente_id=rec_id,
        )
    except Exception:
        logger.exception("Error registrando egreso recurrente")
        await _reply(update, obtener_mensaje("error_generico"))
        return ConversationHandler.END
    await _reply(update, obtener_mensaje("egreso.registrado"))
    return ConversationHandler.END


async def handle_egreso_rec_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Route field selection for the recurring branch edit menu."""
    accion = _input_text(update).strip()
    ud = _ud(context)
    if accion == CB_EDIT_VOLVER:
        await _reply(update, _resumen_rec(ud), _teclado_confirmar_cancelar())
        return EGRESO_REC_CONFIRM
    if accion == CB_EDIT_MONTO:
        ud["editando"] = True
        monto_fmt = _fmt_cop(ud.get("rec_monto_sugerido", Decimal("0")))  # type: ignore[arg-type]
        teclado = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        obtener_mensaje("egreso.boton_usar_sugerido").format(
                            monto_sugerido=monto_fmt
                        ),
                        callback_data=CB_USAR_SUGERIDO,
                    )
                ]
            ]
        )
        await _reply(
            update,
            formatear_html(
                obtener_mensaje("egreso.rec_pedir_monto"),
                nombre=ud.get("rec_nombre", ""),
                monto_sugerido=monto_fmt,
            ),
            teclado,
        )
        return EGRESO_REC_MONTO
    if accion == CB_EDIT_FECHA:
        ud["editando"] = True
        teclado_hoy = InlineKeyboardMarkup(
            [[InlineKeyboardButton(obtener_mensaje("egreso.boton_hoy"), callback_data=CB_HOY)]]
        )
        await _reply(update, obtener_mensaje("egreso.rec_pedir_fecha"), teclado_hoy)
        return EGRESO_REC_FECHA
    # Unknown — return to summary
    await _reply(update, _resumen_rec(ud), _teclado_confirmar_cancelar())
    return EGRESO_REC_CONFIRM


# ---------------------------------------------------------------------------
# /gastos_fijos — list and create recurring expenses
# ---------------------------------------------------------------------------


@requiere_admin
async def cmd_gastos_fijos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /gastos_fijos — list active recurring expenses."""
    service = context.bot_data.get("recurrente_service")
    gastos: list[GastoRecurrente] = service.listar_activos() if service else []
    if not gastos:
        await _reply(update, obtener_mensaje("gastos_fijos.vacio"))
    else:
        lineas = [f"• {g.nombre} — {_fmt_cop(g.monto.monto)} (dia {g.dia_mes})" for g in gastos]
        texto = formatear_html(
            obtener_mensaje("gastos_fijos.lista"), lista="\n".join(lineas)
        )
        botones = [
            [InlineKeyboardButton(f"Desactivar {g.nombre}", callback_data=f"desactivar:{g.id}")]
            for g in gastos
        ]
        botones.append(
            [InlineKeyboardButton("+ Nuevo gasto fijo", callback_data="nuevo_gasto_fijo")]
        )
        await _reply(update, texto, InlineKeyboardMarkup(botones))
    return ConversationHandler.END


@requiere_admin_conv
async def handle_gf_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = _input_text(update).strip()
    _ud(context)["gf_nombre"] = nombre
    await _reply(update, obtener_mensaje("gastos_fijos.pedir_monto"))
    return GF_MONTO


async def handle_gf_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    monto = _parsear_monto_cop(texto)
    if monto is None:
        await _reply(update, obtener_mensaje("egreso.error_monto"))
        return GF_MONTO
    _ud(context)["gf_monto"] = monto
    service = context.bot_data.get("egreso_service")
    categorias: list[str] = service.listar_categorias() if service else []
    teclado = _teclado_inline(categorias)
    await _reply(update, obtener_mensaje("gastos_fijos.pedir_categoria"), teclado)
    return GF_CATEGORIA


async def handle_gf_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    categoria = _input_text(update).strip()
    service = context.bot_data.get("egreso_service")
    categorias: list[str] = service.listar_categorias() if service else []
    if categoria not in categorias:
        teclado = _teclado_inline(categorias)
        await _reply(update, obtener_mensaje("egreso.error_categoria"), teclado)
        return GF_CATEGORIA
    _ud(context)["gf_categoria"] = categoria
    await _reply(update, obtener_mensaje("gastos_fijos.pedir_dia"))
    return GF_DIA


async def handle_gf_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update).strip()
    try:
        dia = int(texto)
        if not (1 <= dia <= 28):
            raise ValueError("fuera de rango")
    except ValueError:
        await _reply(update, obtener_mensaje("gastos_fijos.pedir_dia"))
        return GF_DIA
    ud = _ud(context)
    ud["gf_dia"] = dia
    nombre: str = ud.get("gf_nombre", "")  # type: ignore[assignment]
    monto: Decimal = ud.get("gf_monto", Decimal("0"))  # type: ignore[assignment]
    categoria: str = ud.get("gf_categoria", "")  # type: ignore[assignment]
    resumen = formatear_html(
        obtener_mensaje("gastos_fijos.confirmacion"),
        nombre=nombre,
        monto=_fmt_cop(monto),
        categoria=categoria,
        dia=dia,
    )
    await _reply(update, resumen, _teclado_confirmar_cancelar())
    return GF_CONFIRMACION


async def handle_gf_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    accion = _input_text(update).strip()
    if accion != "confirmar":
        await _reply(update, obtener_mensaje("venta_cancelada"))
        return ConversationHandler.END
    service = context.bot_data.get("recurrente_service")
    if service is None:
        logger.error("recurrente_service not found in bot_data")
        return ConversationHandler.END
    ud = _ud(context)
    nombre: str = ud.get("gf_nombre")  # type: ignore[assignment]
    monto: Decimal = ud.get("gf_monto")  # type: ignore[assignment]
    categoria: str = ud.get("gf_categoria")  # type: ignore[assignment]
    dia: int = ud.get("gf_dia")  # type: ignore[assignment]
    from garay.config.settings import obtener_settings

    moneda = obtener_settings().moneda_predeterminada
    gasto = GastoRecurrente(
        id=uuid.uuid4(),
        nombre=nombre,
        monto=Dinero(monto, moneda),
        categoria=categoria,
        dia_mes=dia,
        activo=True,
    )
    service.guardar(gasto)
    await _reply(
        update,
        formatear_html(
            obtener_mensaje("gastos_fijos.creado"),
            nombre=nombre,
            monto=_fmt_cop(monto),
            dia=dia,
        ),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /categorias_egreso — manage egreso categories (list, create, toggle, edit)
# States 130-134 to avoid collision with egreso (100-124) and gastos fijos (110-114).
# ---------------------------------------------------------------------------

CAT_MENU: int = 130
CAT_ACCIONES: int = 131
CAT_NUEVA_NOMBRE: int = 132
CAT_NUEVA_PARECIDO: int = 133
CAT_EDIT_DESC: int = 134

PREFIJO_CATSEL: str = "catsel:"
CB_CAT_NUEVA: str = "cat_nueva"
CB_CAT_CERRAR: str = "cat_cerrar"
CB_CAT_ATRAS: str = "cat_atras"
CB_CAT_TOGGLE: str = "cat_toggle"
CB_CAT_EDIT_DESC: str = "cat_edit_desc"
CB_CAT_USAR_EXISTENTE: str = "cat_usar_existente"
CB_CAT_CREAR_IGUAL: str = "cat_crear_igual"
CB_CAT_CANCELAR: str = "cat_cancelar"


def _fila_boton(texto: str, data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(texto, callback_data=data)]


def _menu_categorias(
    context: ContextTypes.DEFAULT_TYPE, ud: dict[str, object]
) -> tuple[str, InlineKeyboardMarkup]:
    """Render the category list and store the index->nombre map for callbacks."""
    service = context.bot_data.get("categoria_service")
    categorias: list[CategoriaEgreso] = service.listar_todas() if service else []
    ud["cat_indices"] = [c.nombre for c in categorias]
    filas: list[list[InlineKeyboardButton]] = []
    for i, c in enumerate(categorias):
        icono = "✅" if c.activo else "🚫"
        candado = " 🔒" if es_categoria_protegida(c.nombre) else ""
        filas.append(_fila_boton(f"{icono} {c.nombre}{candado}", f"{PREFIJO_CATSEL}{i}"))
    filas.append(_fila_boton(obtener_mensaje("categoria.boton_nueva"), CB_CAT_NUEVA))
    filas.append(_fila_boton(obtener_mensaje("categoria.boton_cerrar"), CB_CAT_CERRAR))
    return obtener_mensaje("categoria.menu_titulo"), InlineKeyboardMarkup(filas)


def _acciones_categoria(ud: dict[str, object]) -> tuple[str, InlineKeyboardMarkup]:
    nombre = str(ud.get("cat_sel_nombre", ""))
    activo = bool(ud.get("cat_sel_activo", True))
    protegida = bool(ud.get("cat_sel_protegida", False))
    estado = obtener_mensaje(
        "categoria.estado_activa" if activo else "categoria.estado_inactiva"
    )
    filas: list[list[InlineKeyboardButton]] = []
    if not protegida:
        toggle = obtener_mensaje(
            "categoria.boton_desactivar" if activo else "categoria.boton_activar"
        )
        filas.append(_fila_boton(toggle, CB_CAT_TOGGLE))
    filas.append(_fila_boton(obtener_mensaje("categoria.boton_editar_desc"), CB_CAT_EDIT_DESC))
    filas.append(_fila_boton(obtener_mensaje("categoria.boton_atras"), CB_CAT_ATRAS))
    texto = formatear_html(
        obtener_mensaje("categoria.acciones_titulo"), nombre=nombre, estado=estado
    )
    if protegida:
        texto = texto + "\n\n" + obtener_mensaje("categoria.nota_protegida")
    return texto, InlineKeyboardMarkup(filas)


@requiere_admin_conv
async def cmd_categorias_egreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /categorias_egreso."""
    ud = _ud(context)
    texto, teclado = _menu_categorias(context, ud)
    await _reply(update, texto, teclado)
    return CAT_MENU


async def handle_cat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    data = _input_text(update)
    if data == CB_CAT_CERRAR:
        await _reply(update, obtener_mensaje("categoria.cerrado"))
        return ConversationHandler.END
    if data == CB_CAT_NUEVA:
        await _reply(update, obtener_mensaje("categoria.pedir_nombre"))
        return CAT_NUEVA_NOMBRE
    if data.startswith(PREFIJO_CATSEL):
        indices: list[str] = ud.get("cat_indices", [])  # type: ignore[assignment]
        try:
            nombre = indices[int(data[len(PREFIJO_CATSEL):])]
        except (ValueError, IndexError):
            texto, teclado = _menu_categorias(context, ud)
            await _reply(update, texto, teclado)
            return CAT_MENU
        service = context.bot_data.get("categoria_service")
        categorias: list[CategoriaEgreso] = service.listar_todas() if service else []
        categoria = next((c for c in categorias if c.nombre == nombre), None)
        if categoria is None:
            texto, teclado = _menu_categorias(context, ud)
            await _reply(update, texto, teclado)
            return CAT_MENU
        ud["cat_sel_nombre"] = categoria.nombre
        ud["cat_sel_activo"] = categoria.activo
        ud["cat_sel_protegida"] = es_categoria_protegida(categoria.nombre)
        texto, teclado = _acciones_categoria(ud)
        await _reply(update, texto, teclado)
        return CAT_ACCIONES
    texto, teclado = _menu_categorias(context, ud)
    await _reply(update, texto, teclado)
    return CAT_MENU


async def handle_cat_acciones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    data = _input_text(update)
    service = context.bot_data.get("categoria_service")
    nombre = str(ud.get("cat_sel_nombre", ""))
    if data == CB_CAT_ATRAS:
        texto, teclado = _menu_categorias(context, ud)
        await _reply(update, texto, teclado)
        return CAT_MENU
    if data == CB_CAT_EDIT_DESC:
        await _reply(
            update,
            formatear_html(obtener_mensaje("categoria.pedir_descripcion"), nombre=nombre),
        )
        return CAT_EDIT_DESC
    if data == CB_CAT_TOGGLE:
        activo = bool(ud.get("cat_sel_activo", True))
        aviso = ""
        try:
            if service is not None:
                if activo:
                    service.desactivar(nombre)
                else:
                    service.activar(nombre)
        except CategoriaEgresoProtegida:
            aviso = formatear_html(obtener_mensaje("categoria.protegida"), nombre=nombre) + "\n\n"
        texto, teclado = _menu_categorias(context, ud)
        await _reply(update, aviso + texto, teclado)
        return CAT_MENU
    texto, teclado = _menu_categorias(context, ud)
    await _reply(update, texto, teclado)
    return CAT_MENU


async def handle_cat_nueva_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    nombre = _input_text(update).strip()
    service = context.bot_data.get("categoria_service")
    existentes = [c.nombre for c in (service.listar_todas() if service else [])]
    if not nombre:
        await _reply(update, obtener_mensaje("categoria.nombre_vacio"))
        return CAT_NUEVA_NOMBRE
    if es_categoria_duplicada(nombre, existentes):
        await _reply(
            update, formatear_html(obtener_mensaje("categoria.duplicada"), nombre=nombre)
        )
        return CAT_NUEVA_NOMBRE
    parecida = sugerir_categoria_parecida(nombre, existentes)
    if parecida is not None:
        ud["cat_nueva_pendiente"] = nombre
        ud["cat_parecida"] = parecida
        teclado = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(
                    obtener_mensaje("categoria.boton_usar_existente").format(parecida=parecida),
                    callback_data=CB_CAT_USAR_EXISTENTE,
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("categoria.boton_crear_igual").format(nombre=nombre),
                    callback_data=CB_CAT_CREAR_IGUAL,
                )],
                [InlineKeyboardButton(
                    obtener_mensaje("categoria.boton_cancelar_parecido"),
                    callback_data=CB_CAT_CANCELAR,
                )],
            ]
        )
        await _reply(
            update,
            formatear_html(
                obtener_mensaje("categoria.parecida_aviso"), nombre=nombre, parecida=parecida
            ),
            teclado,
        )
        return CAT_NUEVA_PARECIDO
    if service is not None:
        service.crear(nombre)
    texto, teclado = _menu_categorias(context, ud)
    creada = formatear_html(obtener_mensaje("categoria.creada"), nombre=nombre)
    await _reply(update, creada + "\n\n" + texto, teclado)
    return CAT_MENU


async def handle_cat_nueva_parecido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    data = _input_text(update)
    service = context.bot_data.get("categoria_service")
    pendiente = str(ud.get("cat_nueva_pendiente", ""))
    aviso = ""
    if data == CB_CAT_CREAR_IGUAL and pendiente:
        if service is not None:
            service.crear(pendiente)
        aviso = formatear_html(obtener_mensaje("categoria.creada"), nombre=pendiente) + "\n\n"
    elif data == CB_CAT_USAR_EXISTENTE:
        parecida = str(ud.get("cat_parecida", ""))
        aviso = (
            formatear_html(obtener_mensaje("categoria.usa_existente"), parecida=parecida)
            + "\n\n"
        )
    ud.pop("cat_nueva_pendiente", None)
    ud.pop("cat_parecida", None)
    texto, teclado = _menu_categorias(context, ud)
    await _reply(update, aviso + texto, teclado)
    return CAT_MENU


async def handle_cat_edit_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = _ud(context)
    descripcion = _input_text(update).strip()
    service = context.bot_data.get("categoria_service")
    nombre = str(ud.get("cat_sel_nombre", ""))
    if service is not None:
        service.editar_descripcion(nombre, descripcion)
    texto, teclado = _menu_categorias(context, ud)
    actualizada = formatear_html(
        obtener_mensaje("categoria.descripcion_actualizada"), nombre=nombre
    )
    await _reply(update, actualizada + "\n\n" + texto, teclado)
    return CAT_MENU


# ---------------------------------------------------------------------------
# /egresos — hub menu that routes to the existing flows.
# The buttons are callback entry points of the respective ConversationHandlers
# (nuevo egreso, gastos fijos, categorías), so no flow is rewritten here.
# ---------------------------------------------------------------------------

CB_HUB_NUEVO: str = "hub_egreso_nuevo"
CB_HUB_FIJOS: str = "hub_egreso_fijos"
CB_HUB_CATEGORIAS: str = "hub_categorias"
CB_HUB_CANCELAR: str = "hub_cancelar"


@requiere_admin
async def cmd_egresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hub de egresos: registrar, gastos fijos y categorías."""
    teclado = InlineKeyboardMarkup(
        [
            _fila_boton(obtener_mensaje("hub.boton_nuevo"), CB_HUB_NUEVO),
            _fila_boton(obtener_mensaje("hub.boton_fijos"), CB_HUB_FIJOS),
            _fila_boton(obtener_mensaje("hub.boton_categorias"), CB_HUB_CATEGORIAS),
            _fila_boton(obtener_mensaje("hub.boton_cancelar"), CB_HUB_CANCELAR),
        ]
    )
    await _reply(update, obtener_mensaje("hub.titulo"), teclado)


async def handle_hub_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cierra el hub, quitando los botones (no dejar botones colgados)."""
    await _reply(update, obtener_mensaje("hub.cerrado"))
