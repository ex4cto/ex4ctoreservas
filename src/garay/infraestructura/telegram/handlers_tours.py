"""PTB handlers for tour management commands (/editar_tour, /eliminar_tour, /nuevo_tour)."""

from __future__ import annotations

import contextlib
import logging
import uuid
from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.dominio.puertos.repositorios import ServicioRepository
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.servicios.errores import HorarioDuplicado, HorarioInvalido
from garay.dominio.servicios.horarios import agregar_horario, formato_display, quitar_horario
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

EDF_NUEVA_FAMILIA: int = 228  # Dedicated state for free-text new family name input

ELT_FAMILIA: int = 225
ELT_TOUR: int = 226
ELT_CONFIRMA: int = 227

# ---------------------------------------------------------------------------
# State constants — /nuevo_tour, range 230-236
# (EDF: 220-224+228, ELT: 225-227; 229 left as buffer)
# ---------------------------------------------------------------------------

NVT_FAMILIA: int = 230         # callback: choose existing family or "Nueva familia"
NVT_NUEVA_FAMILIA: int = 231   # text: new free-text family name
NVT_NOMBRE: int = 232          # text: tour name
NVT_NETO_ADULTO: int = 233     # text or skip: net adult price
NVT_NETO_NINO: int = 234       # text or skip: net child price
NVT_CONFIRMA: int = 235        # callback: create / cancel / edit-field
NVT_DUP_CONFIRMA: int = 236    # callback: duplicate name detected → use anyway / change

# ---------------------------------------------------------------------------
# State constants — schedule editor (EDH) range 237-239
# (EDF: 220-224+228, ELT: 225-227, 229 buffer, NVT: 230-236)
# ---------------------------------------------------------------------------

EDH_LISTA: int = 237    # schedule list: X-buttons per horario + agregar + listo
EDH_AGREGAR: int = 238  # dedicated text state for free-text horario input
# 239 = buffer

# ---------------------------------------------------------------------------
# State constants — /nuevo_tour schedule editor range 240-241
# ---------------------------------------------------------------------------

NVT_HOR_LISTA: int = 240    # NVT schedule list editor (operates on user_data)
NVT_HOR_AGREGAR: int = 241  # NVT dedicated text state for horario input

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_CAMPOS_EDITABLES: list[tuple[str, str]] = [
    ("nombre", "Nombre"),
    ("neto_adulto", "Neto adulto"),
    ("neto_nino", "Neto niño"),
    ("familia", "Familia"),
    ("horarios", "Horarios"),
    ("activo", "Activar / Desactivar"),
]


def _render_ficha(s: Servicio) -> str:
    """Render a tour detail card."""
    neto_adulto = str(s.precio_neto_adulto) if s.precio_neto_adulto is not None else "—"
    neto_nino = str(s.precio_neto_nino) if s.precio_neto_nino is not None else "—"
    estado = "Activo" if s.activo else "Inactivo"
    horarios_str = (
        ", ".join(formato_display(h) for h in s.horarios) if s.horarios else "—"
    )
    return obtener_mensaje("tour_ficha").format(
        nombre=s.nombre,
        familia=s.categoria or "—",
        neto_adulto=neto_adulto,
        neto_nino=neto_nino,
        estado=estado,
        horarios=horarios_str,
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


def _teclado_horarios(horarios: list[str], prefix: str) -> InlineKeyboardMarkup:
    """Build a schedule editor keyboard.

    Each horario → one row with a X button (callback: {prefix}quitar:{canonical}).
    Then a row for agregar ({prefix}agregar) and a row for listo ({prefix}listo).
    Works for both EDH (editar_tour) and NVT-HOR (nuevo_tour) by parameterising prefix.
    """
    botones: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(f"✕ {formato_display(h)}", callback_data=f"{prefix}quitar:{h}")]
        for h in horarios
    ]
    botones.append(
        [InlineKeyboardButton("➕ Agregar horario", callback_data=f"{prefix}agregar")]  # noqa: RUF001
    )
    botones.append(
        [InlineKeyboardButton("✅ Listo", callback_data=f"{prefix}listo")]
    )
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
        return EDF_NUEVA_FAMILIA

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

    if campo == "horarios":
        # Open the schedule list editor
        ud_hor = context.user_data if context.user_data is not None else {}
        target_id_hor = str(ud_hor.get("edt_target_id", ""))
        repo_hor: ServicioRepository | None = context.bot_data.get("servicio_repo")
        s_hor: Servicio | None = None
        with contextlib.suppress(ValueError, AttributeError):
            s_hor = repo_hor.buscar_por_id(uuid.UUID(target_id_hor)) if repo_hor else None
        horarios_hor = s_hor.horarios if s_hor is not None else []
        teclado_h = _teclado_horarios(horarios_hor, prefix="edh_")
        horarios_texto_hor = (
            ", ".join(formato_display(h) for h in horarios_hor) if horarios_hor else "—"
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_lista").format(horarios=horarios_texto_hor),
            reply_markup=teclado_h,
        )
        return EDH_LISTA

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
    """Handle free-text new family name input (active in state EDF_NUEVA_FAMILIA)."""
    if update.effective_message is None:
        return EDF_NUEVA_FAMILIA
    texto = (update.effective_message.text or "").strip()
    if not texto:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_nueva_familia_prompt")
        )
        return EDF_NUEVA_FAMILIA
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
# /editar_tour — schedule editor (EDH states 237-238)
# ---------------------------------------------------------------------------


async def handle_edh_lista(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Route EDH_LISTA callbacks: edh_agregar / edh_quitar:{canonical} / edh_listo."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return EDH_LISTA

    data: str = query.data
    ud = context.user_data if context.user_data is not None else {}
    target_id_str = str(ud.get("edt_target_id", ""))
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None

    if data == "edh_agregar":
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_pide")
        )
        return EDH_AGREGAR

    if data.startswith("edh_quitar:"):
        canonico = data.removeprefix("edh_quitar:")
        if s is not None:
            s.horarios = quitar_horario(s.horarios, canonico)
            if repo:
                repo.guardar(s)
            _refrescar_fsm(context)
        # Re-render schedule list
        horarios = s.horarios if s is not None else []
        teclado = _teclado_horarios(horarios, prefix="edh_")
        horarios_texto = (
            ", ".join(formato_display(h) for h in horarios) if horarios else "—"
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_lista").format(horarios=horarios_texto),
            reply_markup=teclado,
        )
        return EDH_LISTA

    if data == "edh_listo":
        # Return to field selection screen
        if s is not None:
            await update.effective_message.reply_text(_render_ficha(s), parse_mode="HTML")
        await update.effective_message.reply_text(
            obtener_mensaje("tour_editar_campo"), reply_markup=_teclado_campos()
        )
        return EDF_FICHA

    return EDH_LISTA


async def handle_edh_agregar_texto(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle free-text horario input in EDH_AGREGAR state.

    Validates, deduplicates, persists, refreshes FSM, re-renders list.
    One MessageHandler(_TEXT) only — Fase 1 lesson.
    """
    if update.effective_message is None:
        return EDH_AGREGAR

    texto = (update.effective_message.text or "").strip()
    ud = context.user_data if context.user_data is not None else {}
    target_id_str = str(ud.get("edt_target_id", ""))
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    s: Servicio | None = None
    with contextlib.suppress(ValueError, AttributeError):
        s = repo.buscar_por_id(uuid.UUID(target_id_str)) if repo else None

    if s is None:
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
        return ConversationHandler.END

    try:
        nueva_lista = agregar_horario(s.horarios, texto)
    except HorarioInvalido:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_invalido")
        )
        return EDH_AGREGAR
    except HorarioDuplicado:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_duplicado")
        )
        return EDH_AGREGAR

    s.horarios = nueva_lista
    if repo:
        repo.guardar(s)
    _refrescar_fsm(context)

    # Re-render schedule list
    teclado = _teclado_horarios(s.horarios, prefix="edh_")
    horarios_texto = (
        ", ".join(formato_display(h) for h in s.horarios) if s.horarios else "—"
    )
    await update.effective_message.reply_text(
        obtener_mensaje("tour_horarios_lista").format(horarios=horarios_texto),
        reply_markup=teclado,
    )
    return EDH_LISTA


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


# ---------------------------------------------------------------------------
# /nuevo_tour — pure helpers
# ---------------------------------------------------------------------------


def _normalizar_familia(texto: str) -> str:
    """Normalize a family name: trim, uppercase, collapse internal spaces."""
    return " ".join(texto.strip().upper().split())


def _reusar_familia(normalizada: str, servicios: list[Servicio]) -> str:
    """Return existing casing when a case-insensitive match exists, else return normalizada."""
    seen: set[str] = set()
    for s in servicios:
        cat = s.categoria or ""
        if cat and cat not in seen:
            seen.add(cat)
            if _normalizar_familia(cat) == normalizada:
                return cat
    return normalizada


def _limpiar_nvt(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pop all nvt_* keys from user_data."""
    if context.user_data is not None:
        for key in (
            "nvt_servicios",
            "nvt_familia",
            "nvt_nombre",
            "nvt_nombre_pendiente",
            "nvt_neto_adulto",
            "nvt_neto_nino",
            "nvt_editando",
            "nvt_horarios",
        ):
            context.user_data.pop(key, None)


def _render_ficha_nuevo(ud: dict[str, object]) -> str:
    """Render the draft tour confirmation sheet from user_data."""
    familia = str(ud.get("nvt_familia") or "—")
    nombre = str(ud.get("nvt_nombre") or "—")
    neto_adulto_raw = ud.get("nvt_neto_adulto")
    neto_nino_raw = ud.get("nvt_neto_nino")
    neto_adulto = str(neto_adulto_raw) if neto_adulto_raw is not None else "—"
    neto_nino = str(neto_nino_raw) if neto_nino_raw is not None else "—"
    _raw_h = ud.get("nvt_horarios")
    nvt_horarios: list[str] = list(_raw_h) if isinstance(_raw_h, list) else []
    horarios_str = (
        ", ".join(formato_display(h) for h in nvt_horarios) if nvt_horarios else "—"
    )
    return obtener_mensaje("tour_nuevo_ficha").format(
        familia=familia,
        nombre=nombre,
        neto_adulto=neto_adulto,
        neto_nino=neto_nino,
        horarios=horarios_str,
    )


def _teclado_ficha_nuevo() -> InlineKeyboardMarkup:
    """Build the confirmation screen keyboard for /nuevo_tour."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Familia", callback_data="nvt_edit:familia"),
            InlineKeyboardButton("✏️ Nombre", callback_data="nvt_edit:nombre"),
        ],
        [
            InlineKeyboardButton("✏️ Neto adulto", callback_data="nvt_edit:neto_adulto"),
            InlineKeyboardButton("✏️ Neto niño", callback_data="nvt_edit:neto_nino"),
        ],
        [
            InlineKeyboardButton("🕐 Horarios", callback_data="nvt_edit:horarios"),
        ],
        [
            InlineKeyboardButton("✅ Crear", callback_data="nvt_crear"),
            InlineKeyboardButton("❌ Cancelar", callback_data="nvt_cancelar"),
        ],
    ])


def _teclado_familias_nvt(servicios: list[Servicio]) -> InlineKeyboardMarkup:
    """Build a family selection keyboard for /nuevo_tour, including a new-family button."""
    familias: list[str] = []
    seen: set[str] = set()
    for s in servicios:
        fam = s.categoria or ""
        if fam and fam not in seen:
            familias.append(fam)
            seen.add(fam)
    botones = [
        [InlineKeyboardButton(fam, callback_data=f"nvt_familia:{fam}")]
        for fam in familias
    ]
    botones.append(
        [InlineKeyboardButton("➕ Nueva familia", callback_data="nvt_familia_nueva_libre")]  # noqa: RUF001
    )
    return InlineKeyboardMarkup(botones)


def _teclado_saltar(callback_data: str) -> InlineKeyboardMarkup:
    """Single-button keyboard with a skip option."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("Saltar", callback_data=callback_data)]])


# ---------------------------------------------------------------------------
# /nuevo_tour — conversation handlers
# ---------------------------------------------------------------------------


@requiere_admin_conv
async def cmd_nuevo_tour(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point for /nuevo_tour — load active services, display family buttons."""
    if update.effective_message is None:
        return ConversationHandler.END
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    servicios = repo.listar_activos() if repo else []
    if context.user_data is not None:
        context.user_data["nvt_servicios"] = servicios
    teclado = _teclado_familias_nvt(servicios)
    await update.effective_message.reply_text(
        obtener_mensaje("tour_selecciona_familia"), reply_markup=teclado
    )
    return NVT_FAMILIA


async def handle_nvt_familia(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle family selection in /nuevo_tour.

    - callback "nvt_familia:{name}" → store family, advance to NVT_NOMBRE.
    - callback "nvt_familia_nueva_libre" → prompt for free-text, advance to NVT_NUEVA_FAMILIA.
    """
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return NVT_FAMILIA

    data: str = query.data

    if data == "nvt_familia_nueva_libre":
        await update.effective_message.reply_text(
            obtener_mensaje("tour_nueva_familia_prompt")
        )
        return NVT_NUEVA_FAMILIA

    # "nvt_familia:{name}" — existing family selected
    familia = data.removeprefix("nvt_familia:")
    if context.user_data is not None:
        context.user_data["nvt_familia"] = familia

    await update.effective_message.reply_text(obtener_mensaje("tour_pide_nombre"))
    return NVT_NOMBRE


async def handle_nvt_nueva_familia(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle free-text new family name input in NVT_NUEVA_FAMILIA state."""
    if update.effective_message is None:
        return NVT_NUEVA_FAMILIA

    texto = (update.effective_message.text or "").strip()
    if not texto:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_nueva_familia_prompt")
        )
        return NVT_NUEVA_FAMILIA

    ud = context.user_data if context.user_data is not None else {}
    servicios: list[Servicio] = list(ud.get("nvt_servicios", []))
    normalizada = _normalizar_familia(texto)
    familia = _reusar_familia(normalizada, servicios)

    if context.user_data is not None:
        context.user_data["nvt_familia"] = familia

    await update.effective_message.reply_text(obtener_mensaje("tour_pide_nombre"))
    return NVT_NOMBRE


async def handle_nvt_nombre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle tour name input in NVT_NOMBRE state.

    Validates non-empty, checks for duplicates via buscar_por_nombre, and:
    - Unique name → store, advance to NVT_NETO_ADULTO (or NVT_CONFIRMA if re-editing).
    - Duplicate name → store pending name, advance to NVT_DUP_CONFIRMA.
    - Empty → reject, stay in NVT_NOMBRE.
    """
    if update.effective_message is None:
        return NVT_NOMBRE

    texto = (update.effective_message.text or "").strip()
    if not texto:
        await update.effective_message.reply_text(obtener_mensaje("tour_nombre_vacio"))
        return NVT_NOMBRE

    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")
    # Case-insensitive duplicate detection: compare normalised (trim+lower) input
    # against all existing tour names.  buscar_por_nombre() is exact-match only;
    # using listar() + client-side fold satisfies the owner's requirement.
    nombre_lower = texto.lower()
    todos = repo.listar() if repo else []
    dup_ci = any(s.nombre.strip().lower() == nombre_lower for s in todos)

    if dup_ci:
        # Store the pending name; let NVT_DUP_CONFIRMA decide
        if context.user_data is not None:
            context.user_data["nvt_nombre_pendiente"] = texto
        teclado = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Usar igual", callback_data="nvt_dup:usar"),
                InlineKeyboardButton("Cambiar nombre", callback_data="nvt_dup:cambiar"),
            ]
        ])
        await update.effective_message.reply_text(
            obtener_mensaje("tour_nombre_duplicado").format(nombre=texto),
            reply_markup=teclado,
        )
        return NVT_DUP_CONFIRMA

    # Unique name — store and advance
    ud = context.user_data if context.user_data is not None else {}
    editando = bool(ud.get("nvt_editando"))
    if context.user_data is not None:
        context.user_data["nvt_nombre"] = texto
        context.user_data.pop("nvt_editando", None)

    if editando:
        # Re-edit path: return to confirmation screen
        ficha = _render_ficha_nuevo(context.user_data or {})
        await update.effective_message.reply_text(
            ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
        )
        return NVT_CONFIRMA

    await update.effective_message.reply_text(
        obtener_mensaje("tour_pide_neto_adulto"),
        reply_markup=_teclado_saltar("nvt_saltar_neto_adulto"),
    )
    return NVT_NETO_ADULTO


async def handle_nvt_dup(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle NVT_DUP_CONFIRMA: usar → store and advance; cambiar → back to NVT_NOMBRE."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return NVT_DUP_CONFIRMA

    accion = query.data.removeprefix("nvt_dup:")
    ud = context.user_data if context.user_data is not None else {}
    editando = bool(ud.get("nvt_editando"))

    if accion == "cambiar":
        await update.effective_message.reply_text(obtener_mensaje("tour_pide_nombre"))
        return NVT_NOMBRE

    # "usar" — commit the pending name
    nombre_pendiente = str(ud.get("nvt_nombre_pendiente", ""))
    if context.user_data is not None:
        context.user_data["nvt_nombre"] = nombre_pendiente
        context.user_data.pop("nvt_nombre_pendiente", None)
        context.user_data.pop("nvt_editando", None)

    if editando:
        ficha = _render_ficha_nuevo(context.user_data or {})
        await update.effective_message.reply_text(
            ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
        )
        return NVT_CONFIRMA

    await update.effective_message.reply_text(
        obtener_mensaje("tour_pide_neto_adulto"),
        reply_markup=_teclado_saltar("nvt_saltar_neto_adulto"),
    )
    return NVT_NETO_ADULTO


def _parse_neto(texto: str) -> Decimal | None:
    """Parse a neto text input. Returns Decimal if valid and > 0, else None (signals error)."""
    try:
        return Decimal(texto.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


async def handle_nvt_neto_adulto(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle NVT_NETO_ADULTO: empty/skip → None; valid > 0 → Decimal; invalid/<=0 → error."""
    # Skip via callback button
    if update.callback_query is not None:
        await update.callback_query.answer()
        if context.user_data is not None:
            context.user_data["nvt_neto_adulto"] = None
        if update.effective_message is None:
            return NVT_NETO_NINO
        ud = context.user_data if context.user_data is not None else {}
        editando = bool(ud.get("nvt_editando"))
        if context.user_data is not None:
            context.user_data.pop("nvt_editando", None)
        if editando:
            ficha = _render_ficha_nuevo(context.user_data or {})
            await update.effective_message.reply_text(
                ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
            )
            return NVT_CONFIRMA
        await update.effective_message.reply_text(
            obtener_mensaje("tour_pide_neto_nino"),
            reply_markup=_teclado_saltar("nvt_saltar_neto_nino"),
        )
        return NVT_NETO_NINO

    if update.effective_message is None:
        return NVT_NETO_ADULTO

    texto = (update.effective_message.text or "").strip()
    ud = context.user_data if context.user_data is not None else {}
    editando = bool(ud.get("nvt_editando"))

    if texto == "":
        # Empty text = skip
        if context.user_data is not None:
            context.user_data["nvt_neto_adulto"] = None
            context.user_data.pop("nvt_editando", None)
        if editando:
            ficha = _render_ficha_nuevo(context.user_data or {})
            await update.effective_message.reply_text(
                ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
            )
            return NVT_CONFIRMA
        await update.effective_message.reply_text(
            obtener_mensaje("tour_pide_neto_nino"),
            reply_markup=_teclado_saltar("nvt_saltar_neto_nino"),
        )
        return NVT_NETO_NINO

    valor = _parse_neto(texto)
    if valor is None or valor <= Decimal("0"):
        await update.effective_message.reply_text(obtener_mensaje("tour_neto_invalido"))
        return NVT_NETO_ADULTO

    if context.user_data is not None:
        context.user_data["nvt_neto_adulto"] = valor
        context.user_data.pop("nvt_editando", None)

    if editando:
        ficha = _render_ficha_nuevo(context.user_data or {})
        await update.effective_message.reply_text(
            ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
        )
        return NVT_CONFIRMA

    await update.effective_message.reply_text(
        obtener_mensaje("tour_pide_neto_nino"),
        reply_markup=_teclado_saltar("nvt_saltar_neto_nino"),
    )
    return NVT_NETO_NINO


async def handle_nvt_neto_nino(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle NVT_NETO_NINO: empty/skip → None → NVT_CONFIRMA; valid > 0 → Decimal."""
    # Skip via callback button
    if update.callback_query is not None:
        await update.callback_query.answer()
        if context.user_data is not None:
            context.user_data["nvt_neto_nino"] = None
            context.user_data.pop("nvt_editando", None)
        if update.effective_message is None:
            return NVT_CONFIRMA
        ud = context.user_data if context.user_data is not None else {}
        ficha = _render_ficha_nuevo(ud)
        await update.effective_message.reply_text(
            ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
        )
        return NVT_CONFIRMA

    if update.effective_message is None:
        return NVT_NETO_NINO

    texto = (update.effective_message.text or "").strip()

    if texto == "":
        if context.user_data is not None:
            context.user_data["nvt_neto_nino"] = None
            context.user_data.pop("nvt_editando", None)
        ficha = _render_ficha_nuevo(context.user_data or {})
        await update.effective_message.reply_text(
            ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
        )
        return NVT_CONFIRMA

    valor = _parse_neto(texto)
    if valor is None or valor <= Decimal("0"):
        await update.effective_message.reply_text(obtener_mensaje("tour_neto_invalido"))
        return NVT_NETO_NINO

    if context.user_data is not None:
        context.user_data["nvt_neto_nino"] = valor
        context.user_data.pop("nvt_editando", None)

    ficha = _render_ficha_nuevo(context.user_data or {})
    await update.effective_message.reply_text(
        ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
    )
    return NVT_CONFIRMA


async def handle_nvt_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle 'nvt_edit:{campo}' callbacks from NVT_CONFIRMA or NVT_FAMILIA.

    Sets nvt_editando=True and re-enters the target field's capture state.
    Does NOT clear other nvt_* fields — only the re-entered field will be overwritten.
    """
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return NVT_CONFIRMA

    campo = query.data.removeprefix("nvt_edit:")
    if context.user_data is not None:
        context.user_data["nvt_editando"] = True

    if campo == "familia":
        ud = context.user_data if context.user_data is not None else {}
        servicios: list[Servicio] = list(ud.get("nvt_servicios", []))
        teclado = _teclado_familias_nvt(servicios)
        await update.effective_message.reply_text(
            obtener_mensaje("tour_selecciona_familia"), reply_markup=teclado
        )
        return NVT_FAMILIA

    if campo == "nombre":
        await update.effective_message.reply_text(obtener_mensaje("tour_pide_nombre"))
        return NVT_NOMBRE

    if campo == "neto_adulto":
        await update.effective_message.reply_text(
            obtener_mensaje("tour_pide_neto_adulto"),
            reply_markup=_teclado_saltar("nvt_saltar_neto_adulto"),
        )
        return NVT_NETO_ADULTO

    if campo == "neto_nino":
        await update.effective_message.reply_text(
            obtener_mensaje("tour_pide_neto_nino"),
            reply_markup=_teclado_saltar("nvt_saltar_neto_nino"),
        )
        return NVT_NETO_NINO

    if campo == "horarios":
        # Open NVT schedule editor; ensure nvt_horarios exists in user_data
        ud2 = context.user_data if context.user_data is not None else {}
        if "nvt_horarios" not in ud2 and context.user_data is not None:
            context.user_data["nvt_horarios"] = []
        _raw_h2 = ud2.get("nvt_horarios")
        nvt_horarios: list[str] = list(_raw_h2) if isinstance(_raw_h2, list) else []
        teclado_h = _teclado_horarios(nvt_horarios, prefix="nvt_hor_")
        horarios_texto = (
            ", ".join(formato_display(h) for h in nvt_horarios) if nvt_horarios else "—"
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_lista").format(horarios=horarios_texto),
            reply_markup=teclado_h,
        )
        return NVT_HOR_LISTA

    # Unknown campo — stay in confirma
    return NVT_CONFIRMA


async def handle_nvt_cancelar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle 'nvt_cancelar' — clear all draft data and end the conversation."""
    query = update.callback_query
    if query:
        await query.answer()
    _limpiar_nvt(context)
    if update.effective_message is not None:
        await update.effective_message.reply_text(obtener_mensaje("tour_cancelado"))
    return ConversationHandler.END


async def handle_nvt_crear(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle 'nvt_crear' — build Servicio, persist, refresh FSM, reply with success."""
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None:
        return ConversationHandler.END

    ud = context.user_data if context.user_data is not None else {}
    repo: ServicioRepository | None = context.bot_data.get("servicio_repo")

    numero = repo.siguiente_numero() if repo else 1
    nuevo = Servicio(
        id=uuid.uuid4(),
        numero=numero,
        nombre=str(ud.get("nvt_nombre", "")),
        descripcion="",
        activo=True,
        precio_neto_adulto=ud.get("nvt_neto_adulto"),  # Decimal | None stored by handlers
        precio_neto_nino=ud.get("nvt_neto_nino"),       # Decimal | None stored by handlers
        categoria=str(ud.get("nvt_familia", "")),
        horarios=[h for h in ud.get("nvt_horarios") or [] if isinstance(h, str)],
    )

    if repo:
        repo.guardar(nuevo)

    _refrescar_fsm(context)
    _limpiar_nvt(context)

    await update.effective_message.reply_text(
        obtener_mensaje("tour_creado_ok").format(nombre=nuevo.nombre)
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /nuevo_tour -- schedule editor (NVT-HOR states 240-241)
# ---------------------------------------------------------------------------


async def handle_nvt_hor_lista(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Route NVT_HOR_LISTA callbacks: nvt_hor_agregar / nvt_hor_quitar:{canonical} / nvt_hor_listo.

    Operates on ud[nvt_horarios] (draft list, no repo — tour not yet created).
    """
    query = update.callback_query
    if query:
        await query.answer()
    if update.effective_message is None or query is None or query.data is None:
        return NVT_HOR_LISTA

    data: str = query.data
    ud = context.user_data if context.user_data is not None else {}
    _raw_nvt = ud.get("nvt_horarios")
    nvt_horarios: list[str] = list(_raw_nvt) if isinstance(_raw_nvt, list) else []

    if data == "nvt_hor_agregar":
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_pide")
        )
        return NVT_HOR_AGREGAR

    if data.startswith("nvt_hor_quitar:"):
        canonico = data.removeprefix("nvt_hor_quitar:")
        nvt_horarios = quitar_horario(nvt_horarios, canonico)
        if context.user_data is not None:
            context.user_data["nvt_horarios"] = nvt_horarios
        # Re-render
        teclado = _teclado_horarios(nvt_horarios, prefix="nvt_hor_")
        horarios_texto = (
            ", ".join(formato_display(h) for h in nvt_horarios) if nvt_horarios else "—"
        )
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_lista").format(horarios=horarios_texto),
            reply_markup=teclado,
        )
        return NVT_HOR_LISTA

    if data == "nvt_hor_listo":
        # Clear edit flag for consistency with other edit paths (nombre, neto_adulto, neto_nino)
        if context.user_data is not None:
            context.user_data.pop("nvt_editando", None)
        # Return to NVT confirmation screen
        ficha = _render_ficha_nuevo(ud)
        await update.effective_message.reply_text(
            ficha, reply_markup=_teclado_ficha_nuevo(), parse_mode="HTML"
        )
        return NVT_CONFIRMA

    return NVT_HOR_LISTA


async def handle_nvt_hor_agregar_texto(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle free-text horario input in NVT_HOR_AGREGAR state.

    Validates, deduplicates, stores in ud[nvt_horarios], re-renders list.
    One MessageHandler(_TEXT) only -- Fase 1 lesson.
    """
    if update.effective_message is None:
        return NVT_HOR_AGREGAR

    texto = (update.effective_message.text or "").strip()
    ud = context.user_data if context.user_data is not None else {}
    _raw_nvt2 = ud.get("nvt_horarios")
    nvt_horarios: list[str] = list(_raw_nvt2) if isinstance(_raw_nvt2, list) else []

    try:
        nueva_lista = agregar_horario(nvt_horarios, texto)
    except HorarioInvalido:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_invalido")
        )
        return NVT_HOR_AGREGAR
    except HorarioDuplicado:
        await update.effective_message.reply_text(
            obtener_mensaje("tour_horarios_duplicado")
        )
        return NVT_HOR_AGREGAR

    if context.user_data is not None:
        context.user_data["nvt_horarios"] = nueva_lista

    # Re-render schedule list
    teclado = _teclado_horarios(nueva_lista, prefix="nvt_hor_")
    horarios_texto = (
        ", ".join(formato_display(h) for h in nueva_lista) if nueva_lista else "—"
    )
    await update.effective_message.reply_text(
        obtener_mensaje("tour_horarios_lista").format(horarios=horarios_texto),
        reply_markup=teclado,
    )
    return NVT_HOR_LISTA
