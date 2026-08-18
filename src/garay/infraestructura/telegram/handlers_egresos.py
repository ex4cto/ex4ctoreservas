"""PTB handlers for /nuevo_egreso and /gastos_fijos."""

from __future__ import annotations

import datetime
import logging
import uuid
from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

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

GF_NOMBRE: int = 110
GF_MONTO: int = 111
GF_CATEGORIA: int = 112
GF_DIA: int = 113
GF_CONFIRMACION: int = 114

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


def _parsear_fecha_egreso(texto: str) -> datetime.date | None:
    """Parse date: 'hoy', DD/MM, DD/MM/YY, DD/MM/YYYY."""
    t = texto.strip().lower()
    if t == "hoy":
        return datetime.date.today()
    hoy = datetime.date.today()
    formatos = ["%d/%m/%Y", "%d/%m/%y"]
    for fmt in formatos:
        try:
            return datetime.datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    # DD/MM — assume current year
    try:
        return datetime.datetime.strptime(f"{t}/{hoy.year}", "%d/%m/%Y").date()
    except ValueError:
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
                InlineKeyboardButton("✅ Confirmar", callback_data="confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
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


# ---------------------------------------------------------------------------
# /nuevo_egreso — ConversationHandler states
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_nuevo_egreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /nuevo_egreso."""
    await _reply(update, obtener_mensaje("egreso.pedir_monto"))
    return EGRESO_MONTO


async def handle_egreso_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    monto = _parsear_monto_cop(texto)
    if monto is None:
        await _reply(update, obtener_mensaje("egreso.error_monto"))
        return EGRESO_MONTO
    _ud(context)["egreso_monto"] = monto
    await _reply(update, obtener_mensaje("egreso.pedir_descripcion"))
    return EGRESO_DESCRIPCION


async def handle_egreso_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update).strip()
    _ud(context)["egreso_descripcion"] = texto
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
    _ud(context)["egreso_categoria"] = categoria
    await _reply(update, obtener_mensaje("egreso.pedir_fecha"))
    return EGRESO_FECHA


async def handle_egreso_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = _input_text(update)
    fecha = _parsear_fecha_egreso(texto)
    if fecha is None:
        await _reply(update, obtener_mensaje("egreso.error_fecha"))
        return EGRESO_FECHA
    _ud(context)["egreso_fecha"] = fecha
    ud = _ud(context)
    monto: Decimal = ud.get("egreso_monto", Decimal("0"))  # type: ignore[assignment]
    descripcion: str = ud.get("egreso_descripcion", "")  # type: ignore[assignment]
    categoria: str = ud.get("egreso_categoria", "")  # type: ignore[assignment]
    resumen = obtener_mensaje("egreso.confirmar_resumen").format(
        monto=_fmt_cop(monto),
        descripcion=descripcion,
        categoria=categoria,
        fecha=fecha.strftime("%d/%m/%Y"),
    )
    await _reply(update, resumen, _teclado_confirmar_cancelar())
    return EGRESO_CONFIRMACION


async def handle_egreso_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    accion = _input_text(update).strip()
    if accion != "confirmar":
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

