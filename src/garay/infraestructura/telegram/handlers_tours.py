"""PTB handlers for tour management commands (/editar_tour, /eliminar_tour)."""

from __future__ import annotations

import contextlib
import logging
import uuid
from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.dominio.puertos.repositorios import ServicioRepository
from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.telegram.auth import requiere_admin_conv
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants — range 220-229
# (tiquetera: 0-24, egresos: 100-114, freelancers: 200-213)
# ---------------------------------------------------------------------------

EDF_FAMILIA: int = 220
EDF_TOUR: int = 221
EDF_FICHA: int = 222
EDF_CAMPO: int = 223
EDF_CONFIRMA: int = 224

ELT_FAMILIA: int = 225
ELT_TOUR: int = 226
ELT_CONFIRMA: int = 227

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_CAMPOS_EDITABLES: list[tuple[str, str]] = [
    ("nombre", "Nombre"),
    ("neto_adulto", "Neto adulto"),
    ("neto_nino", "Neto niño"),
    ("familia", "Familia"),
    ("activo", "Activar / Desactivar"),
]


def _render_ficha(s: Servicio) -> str:
    """Render a tour detail card."""
    neto_adulto = str(s.precio_neto_adulto) if s.precio_neto_adulto is not None else "—"
    neto_nino = str(s.precio_neto_nino) if s.precio_neto_nino is not None else "—"
    estado = "Activo" if s.activo else "Inactivo"
    return obtener_mensaje("tour_ficha").format(
        nombre=s.nombre,
        familia=s.categoria or "—",
        neto_adulto=neto_adulto,
        neto_nino=neto_nino,
        estado=estado,
    )


def _teclado_campos() -> InlineKeyboardMarkup:
    """Build the field-selection keyboard."""
    botones = [
        [InlineKeyboardButton(label, callback_data=f"edt_campo:{campo}")]
        for campo, label in _CAMPOS_EDITABLES
    ]
    botones.append([InlineKeyboardButton("✅ Listo", callback_data="edt_listo")])
    return InlineKeyboardMarkup(botones)


def _teclado_familias(servicios: list[Servicio], prefix: str) -> InlineKeyboardMarkup:
    """Build a family selection keyboard from a list of services."""
    familias: list[str] = []
    seen: set[str] = set()
    for s in servicios:
        fam = s.categoria or ""
        if fam and fam not in seen:
            familias.append(fam)
            seen.add(fam)
    botones = [
        [InlineKeyboardButton(fam, callback_data=f"{prefix}{fam}")]
        for fam in familias
    ]
    return InlineKeyboardMarkup(botones)


def _teclado_tours(servicios: list[Servicio], familia: str, prefix: str) -> InlineKeyboardMarkup:
    """Build a tour selection keyboard for a given family."""
    tours = [s for s in servicios if (s.categoria or "") == familia]
    botones = [
        [
            InlineKeyboardButton(
                f"{s.nombre}{' [inactivo]' if not s.activo else ''}",
                callback_data=f"{prefix}{s.id}",
            )
        ]
        for s in tours
    ]
    return InlineKeyboardMarkup(botones)


def _refrescar_fsm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh the FSM catalog using listar_activos() — NEVER listar()."""
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    fsm = context.bot_data.get("fsm")
    if repo is None or fsm is None:
        return
    activos = repo.listar_activos()
    tuples = [
        (s.numero, s.nombre, s.precio_neto_adulto, s.precio_neto_nino, s.categoria)
        for s in activos
    ]
    fsm.refrescar_servicios(tuples)


def _limpiar_edt(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pop all edt_* keys from user_data."""
    if context.user_data is not None:
        for key in (
            "edt_servicios",
            "edt_familia",
            "edt_target_id",
            "edt_campo",
            "edt_valor",
            "edt_activo_nuevo",
        ):
            context.user_data.pop(key, None)


def _limpiar_elt(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pop all elt_* keys from user_data."""
    if context.user_data is not None:
        for key in ("elt_servicios", "elt_familia", "elt_target_id", "elt_nombre"):
            context.user_data.pop(key, None)


# ---------------------------------------------------------------------------
# /editar_tour
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_editar_tour(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point for /editar_tour — list all tours grouped by family."""
    if update.effective_message is None:
        return ConversationHandler.END
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    todos = repo.listar() if repo else []
    if not todos:
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END
    if context.user_data is not None:
        context.user_data["edt_servicios"] = todos
    teclado = _teclado_familias(todos, "edt_familia:")
    await update.effective_message.reply_text(
        obtener_mensaje("tour_selecciona_familia"), reply_markup=teclado
    )
    return EDF_FAMILIA


async def handle_edt_familia(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle family selection in /editar_tour.

    Two cases:
    - callback_data="edt_familia:{name}" during navigation → show tour list.
    - callback_data="edt_familia_nueva:{name}" during field edit → family reassign confirm.
    - callback_data="edt_familia_nueva_libre" during field edit → prompt for free text.
    """
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDF_FAMILIA

    data: str = query.data

    # Familia reassign — pick existing family
    if data.startswith("edt_familia_nueva:"):
        nueva_familia = data.removeprefix("edt_familia_nueva:")
        ud = context.user_data if context.user_data is not None else {}
        target_id_str = str(ud.get("edt_target_id", ""))
        repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
        s: Servicio | None = None
        with contextlib.suppress(ValueError, AttributeError):
            s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None
        anterior = s.categoria if s else "—"
        if context.user_data is not None:
            context.user_data["edt_valor"] = nueva_familia
        teclado = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirmar", callback_data="edt_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edt_cancelar"),
            ]]
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_confirmar_cambio").format(
                anterior=anterior, nuevo=nueva_familia
            ),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return EDF_CONFIRMA

    # Familia reassign — prompt for new free-text family name
    if data == "edt_familia_nueva_libre":
        await update.effective_message.reply_text(
            obtener_mensaje("tour_nueva_familia_prompt")
        )
        return EDF_CAMPO

    # Navigation: edt_familia:{family_name}
    familia = data.removeprefix("edt_familia:")
    if context.user_data is not None:
        context.user_data["edt_familia"] = familia
    ud = context.user_data if context.user_data is not None else {}
    todos: list[Servicio] = list(ud.get("edt_servicios", []))
    teclado = _teclado_tours(todos, familia, "edt_tour:")
    await update.effective_message.reply_text(
        obtener_mensaje("tour_selecciona_tour"), reply_markup=teclado
    )
    return EDF_TOUR


async def handle_edt_tour(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle tour selection in /editar_tour — show detail card."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDF_TOUR
    tour_id_str = query.data.removeprefix("edt_tour:")
    if context.user_data is not None:
        context.user_data["edt_target_id"] = tour_id_str
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(tour_id_str)) if repo else None
    if s is not None:
        await update.effective_message.reply_text(_render_ficha(s), parse_mode="HTML")
    await update.effective_message.reply_text(
        obtener_mensaje("tour_editar_campo"),
        reply_markup=_teclado_campos(),
    )
    return EDF_FICHA


async def handle_edt_ficha(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle field selection from the tour detail screen."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDF_FICHA

    data = query.data

    if data == "edt_listo":
        _limpiar_edt(context)
        return ConversationHandler.END

    if not data.startswith("edt_campo:"):
        return EDF_FICHA

    campo = data.removeprefix("edt_campo:")
    if context.user_data is not None:
        context.user_data["edt_campo"] = campo

    if campo == "activo":
        ud = context.user_data if context.user_data is not None else {}
        target_id_str = str(ud.get("edt_target_id", ""))
        repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
        s: Servicio | None = None
        with contextlib.suppress(ValueError, AttributeError):
            s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None
        nuevo_activo = not (s.activo if s else True)
        nuevo_str = "Activo" if nuevo_activo else "Inactivo"
        actual_str = "Activo" if (s and s.activo) else "Inactivo"
        if context.user_data is not None:
            context.user_data["edt_activo_nuevo"] = nuevo_activo
        teclado = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirmar", callback_data="edt_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edt_cancelar"),
            ]]
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_confirmar_cambio").format(
                anterior=actual_str, nuevo=nuevo_str
            ),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return EDF_CONFIRMA

    if campo == "familia":
        # Show existing families + "Nueva familia" button
        ud = context.user_data if context.user_data is not None else {}
        todos: list[Servicio] = list(ud.get("edt_servicios", []))
        repo2: ServicioRepository | None = context.bot_data.get("servicio_repo")
        if not todos and repo2:
            todos = repo2.listar()
        familias: list[str] = []
        seen: set[str] = set()
        for sv in todos:
            fam = sv.categoria or ""
            if fam and fam not in seen:
                familias.append(fam)
                seen.add(fam)
        botones = [
            [InlineKeyboardButton(fam, callback_data=f"edt_familia_nueva:{fam}")]
            for fam in familias
        ]
        nueva_label = "➕ Nueva familia"  # noqa: RUF001
        botones.append(
            [InlineKeyboardButton(nueva_label, callback_data="edt_familia_nueva_libre")]
        )
        teclado2 = InlineKeyboardMarkup(botones)
        await update.effective_message.reply_text(
            obtener_mensaje("tour_selecciona_familia"), reply_markup=teclado2
        )
        return EDF_FAMILIA

    # Text field prompts
    prompts: dict[str, str] = {
        "nombre": "Ingresa el nuevo nombre del tour:",
        "neto_adulto": "Ingresa el nuevo neto adulto (número positivo o vacío para limpiar):",
        "neto_nino": "Ingresa el nuevo neto niño (número positivo o vacío para limpiar):",
    }
    prompt = prompts.get(campo, "Ingresa el nuevo valor:")
    await update.effective_message.reply_text(prompt)
    return EDF_CAMPO


async def handle_edt_valor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle free-text value input for the chosen field."""
    if update.effective_message is None:
        return EDF_CAMPO

    ud = context.user_data if context.user_data is not None else {}
    campo: str = str(ud.get("edt_campo", ""))
    target_id_str: str = str(ud.get("edt_target_id", ""))
    texto = (update.effective_message.text or "").strip()

    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None

    if campo == "nombre":
        if not texto:
            await update.effective_message.reply_text(
                obtener_mensaje("tour_nombre_vacio")
            )
            return EDF_CAMPO
        if s and texto == s.nombre:
            await update.effective_message.reply_text(
                obtener_mensaje("tour_campo_sin_cambio")
            )
            # Return to ficha without saving
            if s is not None:
                await update.effective_message.reply_text(_render_ficha(s), parse_mode="HTML")
            await update.effective_message.reply_text(
                obtener_mensaje("tour_editar_campo"), reply_markup=_teclado_campos()
            )
            return EDF_FICHA
        anterior = s.nombre if s else "—"
        if context.user_data is not None:
            context.user_data["edt_valor"] = texto
        teclado = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirmar", callback_data="edt_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edt_cancelar"),
            ]]
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_confirmar_cambio").format(
                anterior=anterior, nuevo=texto
            ),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return EDF_CONFIRMA

    if campo in ("neto_adulto", "neto_nino"):
        if texto == "":
            # Empty → clear field
            if context.user_data is not None:
                context.user_data["edt_valor"] = None
            actual = (
                s.precio_neto_adulto if campo == "neto_adulto" else s.precio_neto_nino
            ) if s else None
            anterior_str = str(actual) if actual is not None else "—"
            teclado = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("✅ Confirmar", callback_data="edt_confirmar"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="edt_cancelar"),
                ]]
            )
            await update.effective_message.reply_text(
                obtener_mensaje("tour_confirmar_cambio").format(
                    anterior=anterior_str, nuevo="(vacío)"
                ),
                reply_markup=teclado,
                parse_mode="HTML",
            )
            return EDF_CONFIRMA
        try:
            valor = Decimal(texto.replace(".", "").replace(",", "."))
        except InvalidOperation:
            await update.effective_message.reply_text(
                obtener_mensaje("tour_neto_invalido")
            )
            return EDF_CAMPO
        if valor <= Decimal("0"):
            await update.effective_message.reply_text(
                obtener_mensaje("tour_neto_invalido")
            )
            return EDF_CAMPO
        actual_neto = (
            s.precio_neto_adulto if campo == "neto_adulto" else s.precio_neto_nino
        ) if s else None
        anterior_str = str(actual_neto) if actual_neto is not None else "—"
        if context.user_data is not None:
            context.user_data["edt_valor"] = valor
        teclado = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirmar", callback_data="edt_confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edt_cancelar"),
            ]]
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_confirmar_cambio").format(
                anterior=anterior_str, nuevo=str(valor)
            ),
            reply_markup=teclado,
            parse_mode="HTML",
        )
        return EDF_CONFIRMA

    # Fallback
    await update.effective_message.reply_text(obtener_mensaje("tour_neto_invalido"))
    return EDF_CAMPO


async def handle_edt_nueva_familia_texto(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle free-text new family name input."""
    if update.effective_message is None:
        return EDF_CAMPO
    texto = (update.effective_message.text or "").strip()
    if not texto:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_nueva_familia_prompt")
        )
        return EDF_CAMPO
    ud = context.user_data if context.user_data is not None else {}
    target_id_str = str(ud.get("edt_target_id", ""))
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None
    anterior = s.categoria if s else "—"
    if context.user_data is not None:
        context.user_data["edt_valor"] = texto
    teclado = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirmar", callback_data="edt_confirmar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="edt_cancelar"),
        ]]
    )
    await update.effective_message.reply_text(
        obtener_mensaje("tour_confirmar_cambio").format(
            anterior=anterior, nuevo=texto
        ),
        reply_markup=teclado,
        parse_mode="HTML",
    )
    return EDF_CONFIRMA


async def handle_edt_confirma(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle edt_confirmar or edt_cancelar — save mutation or abort."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None:
        return ConversationHandler.END

    accion = query.data if query else ""
    ud = context.user_data if context.user_data is not None else {}

    if accion in ("edt_cancelar", "edt_toggle_activo") and "edt_activo_nuevo" not in ud:
        # Pure cancel
        _limpiar_edt(context)
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END

    # Determine if this is a toggle-activo shortcut (callback from ficha directly)
    if accion == "edt_cancelar":
        _limpiar_edt(context)
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END

    target_id_str = str(ud.get("edt_target_id", ""))
    campo = str(ud.get("edt_campo", ""))

    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None

    if s is None:
        _limpiar_edt(context)
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END

    # Apply mutation
    if campo == "nombre":
        s.nombre = str(ud.get("edt_valor", s.nombre))
    elif campo == "neto_adulto":
        raw = ud.get("edt_valor")
        s.precio_neto_adulto = Decimal(str(raw)) if raw is not None else None
    elif campo == "neto_nino":
        raw = ud.get("edt_valor")
        s.precio_neto_nino = Decimal(str(raw)) if raw is not None else None
    elif campo in ("familia", "categoria"):
        s.categoria = str(ud.get("edt_valor", s.categoria))
    elif campo == "activo":
        new_val = ud.get("edt_activo_nuevo")
        if new_val is not None:
            s.activo = bool(new_val)

    if repo:
        repo.guardar(s)

    _refrescar_fsm(context)

    await update.effective_message.reply_text(obtener_mensaje("tour_guardado_ok"))
    await update.effective_message.reply_text(_render_ficha(s), parse_mode="HTML")

    # Clear field/value but KEEP target_id for multi-edit loop
    if context.user_data is not None:
        for key in ("edt_campo", "edt_valor", "edt_activo_nuevo"):
            context.user_data.pop(key, None)

    await update.effective_message.reply_text(
        obtener_mensaje("tour_editar_campo"),
        reply_markup=_teclado_campos(),
    )
    return EDF_FICHA


# ---------------------------------------------------------------------------
# /eliminar_tour
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_eliminar_tour(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point for /eliminar_tour — list all tours grouped by family."""
    if update.effective_message is None:
        return ConversationHandler.END
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    todos = repo.listar() if repo else []
    if not todos:
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END
    if context.user_data is not None:
        context.user_data["elt_servicios"] = todos
    teclado = _teclado_familias(todos, "elt_familia:")
    await update.effective_message.reply_text(
        obtener_mensaje("tour_selecciona_familia"), reply_markup=teclado
    )
    return ELT_FAMILIA


async def handle_elt_familia(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle family selection in /eliminar_tour."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return ELT_FAMILIA
    familia = query.data.removeprefix("elt_familia:")
    if context.user_data is not None:
        context.user_data["elt_familia"] = familia
    ud = context.user_data if context.user_data is not None else {}
    todos: list[Servicio] = list(ud.get("elt_servicios", []))
    teclado = _teclado_tours(todos, familia, "elt_tour:")
    await update.effective_message.reply_text(
        obtener_mensaje("tour_selecciona_tour"), reply_markup=teclado
    )
    return ELT_TOUR


async def handle_elt_tour(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle tour selection in /eliminar_tour — show confirmation screen."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return ELT_TOUR
    tour_id_str = query.data.removeprefix("elt_tour:")
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(tour_id_str)) if repo else None
    if s is None:
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END
    if context.user_data is not None:
        context.user_data["elt_target_id"] = tour_id_str
        context.user_data["elt_nombre"] = s.nombre
    teclado = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirmar", callback_data="elt_confirmar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="elt_cancelar"),
        ]]
    )
    await update.effective_message.reply_text(
        obtener_mensaje("tour_eliminar_confirmar").format(nombre=s.nombre),
        reply_markup=teclado,
        parse_mode="HTML",
    )
    return ELT_CONFIRMA


async def handle_elt_confirma(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle elt_confirmar or elt_cancelar — soft-delete or abort."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None:
        return ConversationHandler.END

    accion = query.data if query else ""
    nombre = (
        str(context.user_data.get("elt_nombre", ""))
        if context.user_data is not None
        else ""
    )

    if accion == "elt_cancelar":
        _limpiar_elt(context)
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END

    target_id_str = (
        str(context.user_data.get("elt_target_id", ""))
        if context.user_data is not None
        else ""
    )
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None

    if s is not None and repo is not None:
        s.activo = False
        repo.guardar(s)

    _refrescar_fsm(context)
    _limpiar_elt(context)
    await update.effective_message.reply_text(
        obtener_mensaje("tour_eliminado_ok").format(nombre=nombre), parse_mode="HTML"
    )
    return ConversationHandler.END
