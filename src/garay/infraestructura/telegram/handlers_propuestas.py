"""Dev-only /generar_documento command — multi-select document generator.

Slice 2: menu multi-select de documentos (propuesta/contrato, audiovisual/software).
Solo la propuesta audiovisual está implementada; el resto se muestra como
"próximamente" (bloqueado). Tras elegir, pide el nombre de la empresa y genera
los documentos seleccionados que estén disponibles, enviándolos como HTML.
"""

from __future__ import annotations

import logging
import re
from enum import StrEnum
from io import BytesIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.propuestas.servicio import GenerarPropuestaAudiovisualService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.propuestas.contexto import PreciosAudiovisual, PropuestaContexto
from garay.infraestructura.telegram.auth import requiere_dev_conv
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# ConversationHandler states — own state space, no collision with other convs.
GEN_SELECCION = 400
GEN_EMPRESA = 401
GEN_PRECIOS = 402
GEN_PRECIO_COMPLETO = 403
GEN_PRECIO_MEDIO = 404
GEN_PRECIO_COMMUNITY = 405
GEN_PRECIO_TRAFFICKER = 406

# user_data keys.
_SEL_KEY = "gen_docs"
_EMPRESA_KEY = "gen_empresa"
_P_COMPLETO = "gen_precio_completo"
_P_MEDIO = "gen_precio_medio"
_P_COMMUNITY = "gen_precio_community"


class Documento(StrEnum):
    """Documents the command can generate."""

    PROPUESTA_AUDIOVISUAL = "propuesta_audiovisual"
    PROPUESTA_SOFTWARE = "propuesta_software"
    CONTRATO_AUDIOVISUAL = "contrato_audiovisual"
    CONTRATO_SOFTWARE = "contrato_software"


# Display order in the menu.
_ORDEN: tuple[Documento, ...] = (
    Documento.PROPUESTA_AUDIOVISUAL,
    Documento.PROPUESTA_SOFTWARE,
    Documento.CONTRATO_AUDIOVISUAL,
    Documento.CONTRATO_SOFTWARE,
)

# Documents already implemented (selectable). The rest render as "próximamente".
_IMPLEMENTADOS: frozenset[str] = frozenset({Documento.PROPUESTA_AUDIOVISUAL.value})


def _slug(texto: str) -> str:
    """Turn a company name into a filename-safe slug."""
    limpio = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return limpio or "empresa"


def alternar_seleccion(seleccionados: set[str], doc: str) -> set[str]:
    """Return a new set with ``doc`` toggled (pure)."""
    nuevo = set(seleccionados)
    if doc in nuevo:
        nuevo.discard(doc)
    else:
        nuevo.add(doc)
    return nuevo


def construir_teclado(seleccionados: set[str]) -> InlineKeyboardMarkup:
    """Build the multi-select document keyboard (pure).

    Implemented docs show ▢/✅; not-yet-available docs show 🔒. A Continuar
    button closes the menu.
    """
    filas: list[list[InlineKeyboardButton]] = []
    for doc in _ORDEN:
        etiqueta = obtener_mensaje(f"generar.doc.{doc.value}")
        if doc.value in _IMPLEMENTADOS:
            marca = "✅" if doc.value in seleccionados else "▢"
            texto = f"{marca} {etiqueta}"
        else:
            texto = f"🔒 {etiqueta}"
        filas.append(
            [InlineKeyboardButton(texto, callback_data=f"gen_toggle:{doc.value}")]
        )
    filas.append(
        [InlineKeyboardButton(obtener_mensaje("generar.continuar"), callback_data="gen_continuar")]
    )
    return InlineKeyboardMarkup(filas)


def parsear_precio(texto: str) -> Dinero | None:
    """Parse a user-typed price into ``Dinero``; return None if invalid (pure).

    Accepts thousands separators and currency symbols: '3.000.000', '$3.000.000',
    '3 000 000' → Dinero(3000000). Rejects anything with non-digit remainder.
    """
    limpio = re.sub(r"[.\s$,]", "", texto.strip())
    if not limpio.isdigit():
        return None
    return Dinero(int(limpio))


def construir_teclado_precios() -> InlineKeyboardMarkup:
    """Keyboard to choose default prices or edit them (pure)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    obtener_mensaje("generar.precios_default"),
                    callback_data="gen_precios:default",
                )
            ],
            [
                InlineKeyboardButton(
                    obtener_mensaje("generar.precios_editar"),
                    callback_data="gen_precios:editar",
                )
            ],
        ]
    )


async def _enviar_audiovisual(
    mensaje: object, context: ContextTypes.DEFAULT_TYPE, ctx: PropuestaContexto
) -> None:
    """Generate the audiovisual proposal HTML and send it as a document."""
    service: GenerarPropuestaAudiovisualService = context.bot_data[
        "propuesta_audiovisual_service"
    ]
    html = service.generar(ctx)
    archivo = BytesIO(html.encode("utf-8"))
    archivo.name = f"propuesta-audiovisual-{_slug(ctx.empresa_nombre)}.html"
    await mensaje.reply_document(  # type: ignore[attr-defined]
        document=archivo,
        filename=archivo.name,
        caption=obtener_mensaje("propuestas.enviada").format(empresa=ctx.empresa_nombre),
    )


@requiere_dev_conv
async def cmd_generar_documento(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point: show the multi-select document menu."""
    if context.user_data is not None:
        context.user_data[_SEL_KEY] = set()
    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("generar.elegir_documentos"),
            reply_markup=construir_teclado(set()),
        )
    return GEN_SELECCION


async def handle_gen_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Toggle a document in the selection, or reject unavailable ones."""
    query = update.callback_query
    if query is None:
        return GEN_SELECCION
    doc = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else ""

    if doc not in _IMPLEMENTADOS:
        await query.answer(obtener_mensaje("generar.proximamente"), show_alert=True)
        return GEN_SELECCION

    seleccionados: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    seleccionados = alternar_seleccion(seleccionados, doc)
    if context.user_data is not None:
        context.user_data[_SEL_KEY] = seleccionados

    await query.answer()
    await query.edit_message_reply_markup(reply_markup=construir_teclado(seleccionados))
    return GEN_SELECCION


async def handle_gen_continuar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Close the menu and ask for the company name (if at least one available doc)."""
    query = update.callback_query
    if query is None:
        return GEN_SELECCION
    seleccionados: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    disponibles = seleccionados & _IMPLEMENTADOS
    if not disponibles:
        await query.answer(
            obtener_mensaje("generar.nada_seleccionado"), show_alert=True
        )
        return GEN_SELECCION

    await query.answer()
    if update.effective_message:
        await update.effective_message.reply_text(
            obtener_mensaje("propuestas.pedir_empresa")
        )
    return GEN_EMPRESA


async def handle_gen_empresa(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Store the company name and ask whether to use default or custom prices."""
    mensaje = update.effective_message
    nombre = (mensaje.text or "").strip() if mensaje else ""
    if not nombre:
        if mensaje:
            await mensaje.reply_text(obtener_mensaje("propuestas.empresa_vacia"))
        return GEN_EMPRESA

    if context.user_data is not None:
        context.user_data[_EMPRESA_KEY] = nombre

    seleccionados: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    if Documento.PROPUESTA_AUDIOVISUAL.value in seleccionados and mensaje:
        await mensaje.reply_text(
            obtener_mensaje("generar.precios_pregunta"),
            reply_markup=construir_teclado_precios(),
        )
        return GEN_PRECIOS
    return ConversationHandler.END


async def handle_gen_precios(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Default → generate with default prices; Edit → start asking prices."""
    query = update.callback_query
    if query is None:
        return GEN_PRECIOS
    await query.answer()
    data = query.data or ""
    opcion = data.split(":", 1)[1] if ":" in data else ""
    nombre = context.user_data.get(_EMPRESA_KEY, "") if context.user_data is not None else ""

    if opcion == "default":
        if update.effective_message:
            await _enviar_audiovisual(
                update.effective_message, context, PropuestaContexto(empresa_nombre=nombre)
            )
        return ConversationHandler.END

    if update.effective_message:
        await update.effective_message.reply_text(obtener_mensaje("generar.precio_completo"))
    return GEN_PRECIO_COMPLETO


async def _capturar_precio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    dest_key: str,
    siguiente_msg: str,
    este_estado: int,
    siguiente_estado: int,
) -> int:
    """Parse a price, store it and advance; re-prompt on invalid input."""
    mensaje = update.effective_message
    precio = parsear_precio(mensaje.text or "") if mensaje else None
    if precio is None:
        if mensaje:
            await mensaje.reply_text(obtener_mensaje("generar.precio_invalido"))
        return este_estado
    if context.user_data is not None:
        context.user_data[dest_key] = precio
    if mensaje:
        await mensaje.reply_text(obtener_mensaje(siguiente_msg))
    return siguiente_estado


async def handle_precio_completo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await _capturar_precio(
        update, context, _P_COMPLETO, "generar.precio_medio",
        GEN_PRECIO_COMPLETO, GEN_PRECIO_MEDIO,
    )


async def handle_precio_medio(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await _capturar_precio(
        update, context, _P_MEDIO, "generar.precio_community",
        GEN_PRECIO_MEDIO, GEN_PRECIO_COMMUNITY,
    )


async def handle_precio_community(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await _capturar_precio(
        update, context, _P_COMMUNITY, "generar.precio_trafficker",
        GEN_PRECIO_COMMUNITY, GEN_PRECIO_TRAFFICKER,
    )


async def handle_precio_trafficker(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Capture the last price, build the custom prices and generate."""
    mensaje = update.effective_message
    precio = parsear_precio(mensaje.text or "") if mensaje else None
    if precio is None:
        if mensaje:
            await mensaje.reply_text(obtener_mensaje("generar.precio_invalido"))
        return GEN_PRECIO_TRAFFICKER

    ud = context.user_data if context.user_data is not None else {}
    precios = PreciosAudiovisual(
        completo=ud[_P_COMPLETO],
        medio=ud[_P_MEDIO],
        community=ud[_P_COMMUNITY],
        trafficker=precio,
    )
    ctx = PropuestaContexto(empresa_nombre=ud.get(_EMPRESA_KEY, ""), precios=precios)
    if mensaje:
        await _enviar_audiovisual(mensaje, context, ctx)
    return ConversationHandler.END
