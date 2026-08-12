"""PTB handlers for freelancer management commands."""

from __future__ import annotations

import contextlib
import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.freelancers.errores import CedulaInvalida
from garay.dominio.freelancers.validaciones import derivar_display, validar_cedula
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.telegram.auth import (
    dev_telegram_ids,
    requiere_admin,
    requiere_admin_conv,
)
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

# State constants — range 210-213 (/editar_freelancer)
EDITAR_SELECCIONAR: int = 210
EDITAR_CAMPO: int = 211
EDITAR_VALOR: int = 212
EDITAR_CONFIRMAR: int = 213

# ---------------------------------------------------------------------------
# /listar_freelancers
# ---------------------------------------------------------------------------


@requiere_admin
async def cmd_listar_freelancers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo is None or update.effective_message is None:
        return
    _dev_ids = dev_telegram_ids()
    freelancers = [
        f for f in repo.listar_todos()
        if f.telegram_user_id is None or f.telegram_user_id not in _dev_ids
    ]
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
    _dev_ids = dev_telegram_ids()
    activos = [
        f for f in (repo.listar_activos() if repo else [])
        if f.telegram_user_id is None or f.telegram_user_id not in _dev_ids
    ]
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


# ---------------------------------------------------------------------------
# /editar_freelancer — A2 multi-edit FSM
# ---------------------------------------------------------------------------

# Field label map for the field menu buttons.
_CAMPOS_EDITABLES: list[tuple[str, str]] = [
    ("nombre_completo", "Nombre completo"),
    ("cedula", "Cédula"),
    ("nombre", "Nombre corto"),
    ("telegram_id", "Telegram ID"),
    ("activo", "Activo"),
]


def _teclado_menu_campo() -> InlineKeyboardMarkup:
    """Build the field-selection keyboard including the Listo button."""
    botones = [
        [InlineKeyboardButton(label, callback_data=f"edf_campo:{campo}")]
        for campo, label in _CAMPOS_EDITABLES
    ]
    botones.append(
        [
            InlineKeyboardButton(
                obtener_mensaje("freelancer.editar_listo"), callback_data="edf_listo"
            )
        ]
    )
    return InlineKeyboardMarkup(botones)


def _limpiar_edf(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pop all edf_* keys from user_data."""
    if context.user_data is not None:
        for key in ("edf_target_id", "edf_campo", "edf_valor", "edf_activo"):
            context.user_data.pop(key, None)


def _render_ficha(f: Freelancer) -> str:
    """Render a freelancer detail card, shown on select and after an edit."""
    return obtener_mensaje("freelancer.editar_ficha").format(
        display=f.display or f.nombre,
        nombre_completo=f.nombre_completo or "—",
        nombre=f.nombre,
        cedula=f.cedula or "—",
        estado="Activo" if f.activo else "Inactivo",
    )


@requiere_admin_conv
async def cmd_editar_freelancer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point for /editar_freelancer — lists all freelancers (active + inactive)."""
    if update.effective_message is None:
        return ConversationHandler.END
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    _dev_ids = dev_telegram_ids()
    todos = [
        f for f in (repo.listar_todos() if repo else [])
        if f.telegram_user_id is None or f.telegram_user_id not in _dev_ids
    ]
    if not todos:
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.editar_sin_freelancers")
        )
        return ConversationHandler.END
    botones = [
        [
            InlineKeyboardButton(
                f"{f.nombre}{' [inactivo]' if not f.activo else ''}",
                callback_data=f"edf_sel:{f.id}",
            )
        ]
        for f in todos
    ]
    teclado = InlineKeyboardMarkup(botones)
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.editar_seleccionar"),
        reply_markup=teclado,
    )
    return EDITAR_SELECCIONAR


async def handle_edf_seleccionar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Callback: edf_sel:{uuid} — store target id and show field menu."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDITAR_SELECCIONAR
    freelancer_id_str = query.data.removeprefix("edf_sel:")
    if context.user_data is not None:
        context.user_data["edf_target_id"] = freelancer_id_str
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    f: Freelancer | None = None
    with contextlib.suppress(ValueError, AttributeError):
        f = repo.buscar_por_id(uuid.UUID(freelancer_id_str)) if repo else None
    if f is not None:
        await update.effective_message.reply_text(_render_ficha(f), parse_mode="HTML")
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.editar_menu_campo"),
        reply_markup=_teclado_menu_campo(),
    )
    return EDITAR_CAMPO


async def handle_edf_campo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Callback: edf_campo:{field} or edf_listo — route to value prompt or END."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDITAR_CAMPO

    data = query.data

    if data == "edf_listo":
        _limpiar_edf(context)
        return ConversationHandler.END

    campo = data.removeprefix("edf_campo:")
    if context.user_data is not None:
        context.user_data["edf_campo"] = campo

    if campo == "activo":
        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        target_id_str = (
            str(context.user_data.get("edf_target_id", ""))
            if context.user_data is not None
            else ""
        )
        f = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo and target_id_str else None
        estado_str = "Activo" if (f and f.activo) else "Inactivo"
        teclado = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Activar", callback_data="edf_activo:true"),
                    InlineKeyboardButton("❌ Desactivar", callback_data="edf_activo:false"),
                ]
            ]
        )
        await update.effective_message.reply_text(
            obtener_mensaje("freelancer.editar_activo_estado").format(estado=estado_str),
            reply_markup=teclado,
        )
        return EDITAR_CONFIRMAR

    prompt_key_map: dict[str, str] = {
        "nombre_completo": "freelancer.editar_pedir_nombre_completo",
        "cedula": "freelancer.editar_pedir_cedula",
        "nombre": "freelancer.editar_pedir_nombre_corto",
        "telegram_id": "freelancer.editar_pedir_telegram_id",
    }
    prompt_key = prompt_key_map.get(campo, "freelancer.editar_pedir_nombre_completo")

    extra_markup: InlineKeyboardMarkup | None = None
    if campo == "telegram_id":
        extra_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Quitar / Unlink", callback_data="edf_tg_none")]]
        )

    if extra_markup:
        await update.effective_message.reply_text(
            obtener_mensaje(prompt_key),
            reply_markup=extra_markup,
        )
    else:
        await update.effective_message.reply_text(obtener_mensaje(prompt_key))
    return EDITAR_VALOR


async def handle_edf_valor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle free-text (or edf_tg_none callback) value input for the chosen field."""
    # Check for the unlink callback first
    query = update.callback_query
    if query and query.data == "edf_tg_none":
        await query.answer()
        if context.user_data is not None:
            context.user_data["edf_valor"] = None
        await _mostrar_confirmacion_editar(update, context)
        return EDITAR_CONFIRMAR

    if update.effective_message is None:
        return EDITAR_VALOR

    ud = context.user_data if context.user_data is not None else {}
    campo: str = str(ud.get("edf_campo", ""))
    target_id_str: str = str(ud.get("edf_target_id", ""))
    target_id: uuid.UUID | None = None
    with contextlib.suppress(ValueError, AttributeError):
        target_id = uuid.UUID(target_id_str)

    texto = (update.effective_message.text or "").strip()

    if campo == "cedula":
        try:
            cedula = validar_cedula(texto)
        except CedulaInvalida:
            await update.effective_message.reply_text(
                obtener_mensaje("freelancer.error_cedula_invalida")
            )
            return EDITAR_VALOR
        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        found = repo.buscar_por_cedula(cedula) if repo else None
        if found and target_id and found.id != target_id:
            await update.effective_message.reply_text(
                obtener_mensaje("freelancer.error_cedula_duplicada_otro")
            )
            return EDITAR_VALOR
        if context.user_data is not None:
            context.user_data["edf_valor"] = cedula
        await _mostrar_confirmacion_editar(update, context)
        return EDITAR_CONFIRMAR

    if campo == "telegram_id":
        try:
            nuevo_tg = int(texto)
        except ValueError:
            await update.effective_message.reply_text(
                obtener_mensaje("freelancer.error_telegram_id_invalido")
            )
            return EDITAR_VALOR
        repo2: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        found_tg = (
            repo2.buscar_por_telegram_id_cualquier_estado(nuevo_tg) if repo2 else None
        )
        if found_tg and target_id and found_tg.id != target_id:
            await update.effective_message.reply_text(
                obtener_mensaje("freelancer.error_telegram_duplicado_otro").format(
                    nombre=found_tg.nombre
                )
            )
            return EDITAR_VALOR
        if context.user_data is not None:
            context.user_data["edf_valor"] = nuevo_tg
        await _mostrar_confirmacion_editar(update, context)
        return EDITAR_CONFIRMAR

    if campo in ("nombre_completo", "nombre"):
        if not texto:
            await update.effective_message.reply_text(
                obtener_mensaje("freelancer.error_nombre_completo_vacio")
            )
            return EDITAR_VALOR
        if context.user_data is not None:
            context.user_data["edf_valor"] = texto
        await _mostrar_confirmacion_editar(update, context)
        return EDITAR_CONFIRMAR

    # Fallback — unknown field, treat as error
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.error_nombre_completo_vacio")
    )
    return EDITAR_VALOR


async def _mostrar_confirmacion_editar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Send the edf confirm/cancel prompt with field diff."""
    if update.effective_message is None:
        return
    ud = context.user_data or {}
    campo = str(ud.get("edf_campo", ""))
    nuevo = ud.get("edf_valor")
    nuevo_str = str(nuevo) if nuevo is not None else "—"
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="edf_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edf_cancelar"),
            ]
        ]
    )
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.editar_confirmar").format(
            campo=campo, anterior="(actual)", nuevo=nuevo_str
        ),
        reply_markup=teclado,
        parse_mode="HTML",
    )


async def handle_edf_activo_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Callback: edf_activo:{true|false} — store boolean and show confirm prompt."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDITAR_CONFIRMAR
    valor_bool = query.data.removeprefix("edf_activo:") == "true"
    if context.user_data is not None:
        context.user_data["edf_activo"] = valor_bool
    ud = context.user_data or {}
    nuevo_str = "Activo" if valor_bool else "Inactivo"
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="edf_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edf_cancelar"),
            ]
        ]
    )
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.editar_confirmar").format(
            campo="activo", anterior="(actual)", nuevo=nuevo_str
        ),
        reply_markup=teclado,
        parse_mode="HTML",
    )
    _ = ud  # suppress unused warning
    return EDITAR_CONFIRMAR


async def handle_edf_confirmar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Callback: edf_confirmar or edf_cancelar — save mutation or abort."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None:
        return ConversationHandler.END

    accion = query.data if query else ""
    ud = context.user_data if context.user_data is not None else {}

    if accion == "edf_cancelar":
        _limpiar_edf(context)
        await update.effective_message.reply_text(obtener_mensaje("freelancer.cancelado"))
        return ConversationHandler.END

    # --- confirm branch ---
    target_id_str = str(ud.get("edf_target_id", ""))
    campo = str(ud.get("edf_campo", ""))

    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    try:
        target_uuid = uuid.UUID(target_id_str)
    except (ValueError, AttributeError):
        await update.effective_message.reply_text(obtener_mensaje("freelancer.cancelado"))
        return ConversationHandler.END

    f = repo.buscar_por_id(target_uuid) if repo else None
    if f is None:
        await update.effective_message.reply_text(obtener_mensaje("freelancer.cancelado"))
        return ConversationHandler.END

    # Mutate exactly one field
    if campo == "nombre_completo":
        nuevo_nc: str = str(ud.get("edf_valor", ""))
        f.nombre_completo = nuevo_nc
        f.display = derivar_display(nuevo_nc)
    elif campo == "cedula":
        f.cedula = str(ud.get("edf_valor", "")) or None
    elif campo == "nombre":
        f.nombre = str(ud.get("edf_valor", ""))
    elif campo == "telegram_id":
        raw_tg = ud.get("edf_valor")
        f.telegram_user_id = int(raw_tg) if isinstance(raw_tg, int) else None
    elif campo == "activo":
        f.activo = bool(ud.get("edf_activo", f.activo))

    if repo:
        repo.guardar(f)

    await update.effective_message.reply_text(obtener_mensaje("freelancer.editado"))
    await update.effective_message.reply_text(_render_ficha(f), parse_mode="HTML")

    # Clear field/value keys but KEEP edf_target_id for the multi-edit loop
    if context.user_data is not None:
        for key in ("edf_campo", "edf_valor", "edf_activo"):
            context.user_data.pop(key, None)

    # Return to field menu for the same freelancer
    await update.effective_message.reply_text(
        obtener_mensaje("freelancer.editar_menu_campo"),
        reply_markup=_teclado_menu_campo(),
    )
    return EDITAR_CAMPO
