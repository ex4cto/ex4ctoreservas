"""PTB handlers for freelancer management commands."""

from __future__ import annotations

import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.freelancers.errores import CedulaInvalida
from garay.dominio.freelancers.validaciones import derivar_display, validar_cedula
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.telegram.auth import requiere_admin, requiere_admin_conv
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 200-209 (tiquetera: 0-24, egresos: 100-114)
# ---------------------------------------------------------------------------

FL_TELEGRAM_ID: int = 201
FL_CONFIRMACION: int = 202
FL_NOMBRE_CORTO: int = 203
FL_DISPLAY_OVERRIDE: int = 204

EF_SELECCIONAR: int = 205
EF_CONFIRMAR: int = 206

FL_NOMBRE_COMPLETO: int = 207
FL_CEDULA: int = 208

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
# /nuevo_freelancer — A1 identity flow
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_nuevo_freelancer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.pedir_nombre_completo")
    )
    return FL_NOMBRE_COMPLETO


async def handle_fl_nombre_completo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.effective_message is None:
        return FL_NOMBRE_COMPLETO
    texto = (update.effective_message.text or "").strip()
    if not texto:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_nombre_completo_vacio")
        )
        return FL_NOMBRE_COMPLETO
    # Derive default short name = first token
    nombre_corto_default = texto.split()[0]
    if context.user_data is not None:
        context.user_data["fl_nombre_completo"] = texto
        context.user_data["fl_nombre"] = nombre_corto_default
    await update.effective_message.reply_text(obtener_mensaje("freelancer.pedir_cedula"))
    return FL_CEDULA


async def handle_fl_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return FL_CEDULA
    texto = (update.effective_message.text or "").strip()
    try:
        cedula = validar_cedula(texto)
    except CedulaInvalida:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_cedula_invalida")
        )
        return FL_CEDULA
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo and repo.buscar_por_cedula(cedula) is not None:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.error_cedula_duplicada")
        )
        return FL_CEDULA
    if context.user_data is not None:
        context.user_data["fl_cedula"] = cedula
    prefill = (
        context.user_data.get("fl_nombre", "") if context.user_data is not None else ""
    )
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.pedir_nombre_corto").format(prefill=prefill)
    )
    return FL_NOMBRE_CORTO


async def handle_fl_nombre_corto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return FL_NOMBRE_CORTO
    texto = (update.effective_message.text or "").strip()
    if context.user_data is not None:
        if texto:
            context.user_data["fl_nombre"] = texto
        nombre_completo = str(context.user_data.get("fl_nombre_completo", ""))
        auto_display = derivar_display(nombre_completo)
        context.user_data["fl_display"] = auto_display
    else:
        auto_display = ""
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.pedir_display_override").format(display=auto_display)
    )
    return FL_DISPLAY_OVERRIDE


async def handle_fl_display_override(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.effective_message is None:
        return FL_DISPLAY_OVERRIDE
    texto = (update.effective_message.text or "").strip()
    if context.user_data is not None and texto:
        context.user_data["fl_display"] = texto
    # Show telegram step with Omitir button
    teclado = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Omitir", callback_data="fl_skip_tg")]]
    )
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.telegram_id_opcional"),
        reply_markup=teclado,
    )
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
    await _mostrar_confirmacion(update, context)
    return FL_CONFIRMACION


async def handle_fl_skip_tg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback handler for the 'Omitir' button in the telegram step."""
    query = update.callback_query
    if query:
        await query.answer()
    if context.user_data is not None:
        context.user_data["fl_telegram_id"] = None
    await _mostrar_confirmacion(update, context)
    return FL_CONFIRMACION


async def _mostrar_confirmacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_message is None:
        return
    ud = context.user_data or {}
    nombre = str(ud.get("fl_nombre", ""))
    cedula = str(ud.get("fl_cedula", ""))
    display = str(ud.get("fl_display", ""))
    telegram_id = ud.get("fl_telegram_id")
    telegram_str = str(telegram_id) if telegram_id is not None else "—"
    texto_conf = obtener_mensaje("freelancer.confirmacion_nuevo").format(
        nombre=nombre,
        cedula=cedula,
        display=display,
        telegram_id=telegram_str,
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
    ud = context.user_data or {}
    nombre = str(ud.get("fl_nombre", ""))
    nombre_completo = str(ud.get("fl_nombre_completo", "")) or None
    cedula = str(ud.get("fl_cedula", "")) or None
    display = str(ud.get("fl_display", "")) or None
    raw_tg = ud.get("fl_telegram_id")
    telegram_id: int | None = int(raw_tg) if isinstance(raw_tg, int) else None
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo:
        freelancer = Freelancer(
            id=uuid.uuid4(),
            nombre=nombre,
            nombre_completo=nombre_completo,
            cedula=cedula,
            display=display,
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
        for key in (
            "fl_nombre",
            "fl_nombre_completo",
            "fl_cedula",
            "fl_display",
            "fl_telegram_id",
        ):
            context.user_data.pop(key, None)


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
        freelancer = repo.buscar_por_id(uuid.UUID(str(freelancer_id_str)))
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
