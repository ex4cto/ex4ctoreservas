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
from garay.dominio.conciliacion.entidades import GastoRecurrente
from garay.infraestructura.telegram.auth import requiere_admin, requiere_admin_conv
from garay.mensajes.catalogo import obtener_mensaje

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
CB_EDIT_VOLVER: str = "egr_edit_volver"
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
            texto, reply_markup=teclado, parse_mode="Markdown"
        )
    elif update.effective_message is not None:
        await update.effective_message.reply_text(
            texto, reply_markup=teclado, parse_mode="Markdown"
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
    fecha: datetime.date = ud.get("egreso_fecha", datetime.date.today())  # type: ignore[assignment]
    return obtener_mensaje("egreso.confirmar_resumen").format(
        monto=_fmt_cop(monto),
        descripcion=descripcion,
        categoria=categoria,
        fecha=fecha.strftime("%d/%m/%Y"),
    )


def _resumen_rec(ud: dict[str, object]) -> str:
    nombre: str = ud.get("rec_nombre", "")  # type: ignore[assignment]
    monto: Decimal = ud.get("rec_monto", Decimal("0"))  # type: ignore[assignment]
    categoria: str = ud.get("rec_categoria", "")  # type: ignore[assignment]
    fecha: datetime.date = ud.get("rec_fecha", datetime.date.today())  # type: ignore[assignment]
    return obtener_mensaje("egreso.rec_confirmar_resumen").format(
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
        await _reply(update, obtener_mensaje("egreso.pedir_monto"))
        return EGRESO_MONTO
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
            obtener_mensaje("egreso.rec_pedir_monto").format(
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
    await _reply(update, obtener_mensaje("egreso.pedir_descripcion"))
    return EGRESO_DESCRIPCION


async def handle_egreso_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update).strip()
    ud = _ud(context)
    ud["egreso_descripcion"] = texto
    if ud.get("editando"):
        ud["editando"] = False
        await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
        return EGRESO_CONFIRMACION
    service = context.bot_data.get("egreso_service")
    categorias: list[str] = service.listar_categorias() if service else []
    teclado = _teclado_inline(categorias)
    await _reply(update, obtener_mensaje("egreso.pedir_categoria"), teclado)
    return EGRESO_CATEGORIA


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
    teclado_hoy = InlineKeyboardMarkup(
        [[InlineKeyboardButton(obtener_mensaje("egreso.boton_hoy"), callback_data=CB_HOY)]]
    )
    await _reply(update, obtener_mensaje("egreso.pedir_fecha"), teclado_hoy)
    return EGRESO_FECHA


async def handle_egreso_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    if texto == CB_HOY:
        fecha: datetime.date | None = datetime.date.today()
    else:
        resultado = parsear_fecha(texto)
        fecha = resultado.date() if resultado is not None else None
    if fecha is None:
        await _reply(update, obtener_mensaje("egreso.error_fecha"))
        return EGRESO_FECHA
    ud = _ud(context)
    ud["egreso_fecha"] = fecha
    if ud.get("editando"):
        ud["editando"] = False
    await _reply(update, _resumen_otro(ud), _teclado_confirmar_cancelar())
    return EGRESO_CONFIRMACION


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
    from garay.config.settings import obtener_settings

    moneda = obtener_settings().moneda_predeterminada
    try:
        service.registrar(
            monto=monto,
            descripcion=descripcion,
            categoria=categoria,
            fecha=fecha,
            moneda=moneda,
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
            obtener_mensaje("egreso.rec_pedir_monto").format(
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
        texto = obtener_mensaje("gastos_fijos.lista").format(lista="\n".join(lineas))
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
    resumen = obtener_mensaje("gastos_fijos.confirmacion").format(
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
        obtener_mensaje("gastos_fijos.creado").format(
            nombre=nombre, monto=_fmt_cop(monto), dia=dia
        ),
    )
    return ConversationHandler.END
