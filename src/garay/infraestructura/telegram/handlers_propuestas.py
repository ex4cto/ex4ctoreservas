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
from garay.dominio.propuestas.contexto import PropuestaContexto
from garay.infraestructura.telegram.auth import requiere_dev_conv
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# ConversationHandler states — own state space, no collision with other convs.
GEN_SELECCION = 400
GEN_EMPRESA = 401

# Key under which the selected-document set lives in user_data.
_SEL_KEY = "gen_docs"


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
    """Generate the selected (available) documents for the given company."""
    mensaje = update.effective_message
    nombre = (mensaje.text or "").strip() if mensaje else ""
    if not nombre:
        if mensaje:
            await mensaje.reply_text(obtener_mensaje("propuestas.empresa_vacia"))
        return GEN_EMPRESA

    seleccionados: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    ctx = PropuestaContexto(empresa_nombre=nombre)

    if Documento.PROPUESTA_AUDIOVISUAL.value in seleccionados and mensaje:
        service: GenerarPropuestaAudiovisualService = context.bot_data[
            "propuesta_audiovisual_service"
        ]
        html = service.generar(ctx)
        archivo = BytesIO(html.encode("utf-8"))
        archivo.name = f"propuesta-audiovisual-{_slug(nombre)}.html"
        await mensaje.reply_document(
            document=archivo,
            filename=archivo.name,
            caption=obtener_mensaje("propuestas.enviada").format(empresa=nombre),
        )
    return ConversationHandler.END
