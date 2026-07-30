"""PTB handlers for freelancer management commands."""

from __future__ import annotations

import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.telegram.auth import requiere_admin, requiere_admin_conv
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 200-209 (tiquetera: 0-24, egresos: 100-114)
# ---------------------------------------------------------------------------

FL_NOMBRE: int = 200
FL_TELEGRAM_ID: int = 201
FL_CONFIRMACION: int = 202

EF_SELECCIONAR: int = 205
EF_CONFIRMAR: int = 206

# ---------------------------------------------------------------------------
# /listar_freelancers
# ---------------------------------------------------------------------------


@requiere_admin
async def cmd_listar_freelancers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo is None or update.effective_message is None:
        return
    freelancers = repo.listar_todos()
    if not freelancers:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.lista_vacia"), parse_mode="HTML"
        )
        return
    lineas = [obtener_mensaje("freelancer.lista_encabezado")]
    for f in freelancers:
        estado = "✅" if f.activo else "❌"
        vinculo = f"ID: {f.telegram_user_id}" if f.telegram_user_id else "sin vincular"
        lineas.append(f"{estado} {f.nombre} — {vinculo}")
    await update.effective_message.reply_text("\n".join(lineas), parse_mode="HTML")


# ---------------------------------------------------------------------------
# /nuevo_freelancer
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_nuevo_freelancer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END
    await update.effective_message.reply_text(obtener_mensaje("freelancer.pedir_nombre"))
    return FL_NOMBRE


async def handle_fl_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return FL_NOMBRE
    texto = (update.effective_message.text or "").strip()
    if not texto:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_nombre_vacio")
        )
        return FL_NOMBRE
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo and repo.buscar_por_nombre(texto) is not None:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_nombre_duplicado")
        )
        return FL_NOMBRE
    if context.user_data is not None:
        context.user_data["fl_nombre"] = texto
    await update.effective_message.reply_text(obtener_mensaje("freelancer.pedir_telegram_id"))
    return FL_TELEGRAM_ID


async def handle_fl_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return FL_TELEGRAM_ID
    texto = (update.effective_message.text or "").strip()
    try:
        telegram_id = int(texto)
    except ValueError:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_telegram_id_invalido")
        )
        return FL_TELEGRAM_ID
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo and repo.buscar_por_telegram_id(telegram_id) is not None:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_telegram_id_duplicado")
        )
        return FL_TELEGRAM_ID
    if context.user_data is not None:
        context.user_data["fl_telegram_id"] = telegram_id
    nombre = context.user_data.get("fl_nombre", "") if context.user_data is not None else ""
    texto_conf = obtener_mensaje("freelancer.confirmacion_nuevo").format(
        nombre=nombre, telegram_id=telegram_id
    )
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="fl_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="fl_cancelar"),
            ]
        ]
    )
    await update.effective_message.reply_text(
        texto_conf, reply_markup=teclado, parse_mode="HTML"
    )
    return FL_CONFIRMACION


async def handle_fl_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None:
        return ConversationHandler.END
    accion = query.data if query else ""
    if accion == "fl_cancelar":
        _limpiar_fl(context)
        await update.effective_message.reply_text(obtener_mensaje("freelancer.cancelado"))
        return ConversationHandler.END
    nombre = context.user_data.get("fl_nombre", "") if context.user_data is not None else ""
    telegram_id: int = (
        context.user_data.get("fl_telegram_id", 0) if context.user_data is not None else 0
    )
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo:
        freelancer = Freelancer(
            id=uuid.uuid4(),
            nombre=nombre,
            telegram_user_id=telegram_id,
            activo=True,
            es_admin=False,
        )
        repo.guardar(freelancer)
    _limpiar_fl(context)
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.creado").format(nombre=nombre), parse_mode="HTML"
    )
    return ConversationHandler.END


def _limpiar_fl(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data is not None:
        context.user_data.pop("fl_nombre", None)
        context.user_data.pop("fl_telegram_id", None)


# ---------------------------------------------------------------------------
# /eliminar_freelancer
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_eliminar_freelancer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    activos = repo.listar_activos() if repo else []
    if not activos:
        await update.effective_message.reply_text(obtener_mensaje("freelancer.sin_activos"))
        return ConversationHandler.END
    botones = [
        [InlineKeyboardButton(f.nombre, callback_data=f"ef_sel:{f.id}")]
        for f in activos
    ]
    teclado = InlineKeyboardMarkup(botones)
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.seleccionar_eliminar"), reply_markup=teclado
    )
    return EF_SELECCIONAR


async def handle_ef_seleccionar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EF_SELECCIONAR
    freelancer_id_str = query.data.removeprefix("ef_sel:")
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    freelancer = repo.buscar_por_id(uuid.UUID(freelancer_id_str)) if repo else None
    if freelancer is None:
        await update.effective_message.reply_text(obtener_mensaje("freelancer.sin_activos"))
        return ConversationHandler.END
    if context.user_data is not None:
        context.user_data["ef_freelancer_id"] = str(freelancer.id)
        context.user_data["ef_freelancer_nombre"] = freelancer.nombre
    texto = obtener_mensaje("freelancer.confirmar_eliminar").format(nombre=freelancer.nombre)
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="ef_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="ef_cancelar"),
            ]
        ]
    )
    await update.effective_message.reply_text(texto, reply_markup=teclado, parse_mode="HTML")
    return EF_CONFIRMAR


async def handle_ef_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None:
        return ConversationHandler.END
    accion = query.data if query else ""
    nombre = (
        context.user_data.get("ef_freelancer_nombre", "")
        if context.user_data is not None
        else ""
    )
    if accion == "ef_cancelar":
        _limpiar_ef(context)
        await update.effective_message.reply_text(obtener_mensaje("freelancer.cancelado"))
        return ConversationHandler.END
    freelancer_id_str = (
        context.user_data.get("ef_freelancer_id", "") if context.user_data is not None else ""
    )
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo and freelancer_id_str:
        freelancer = repo.buscar_por_id(uuid.UUID(freelancer_id_str))
        if freelancer:
            freelancer.activo = False
            repo.guardar(freelancer)
    _limpiar_ef(context)
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.eliminado").format(nombre=nombre), parse_mode="HTML"
    )
    return ConversationHandler.END


def _limpiar_ef(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data is not None:
        context.user_data.pop("ef_freelancer_id", None)
        context.user_data.pop("ef_freelancer_nombre", None)
