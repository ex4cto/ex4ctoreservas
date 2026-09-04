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
from garay.aplicacion.propuestas.servicio_software import GenerarPropuestaSoftwareService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.propuestas.contexto import (
    EJEMPLOS_SERVICIOS_DEFAULT,
    PRECIOS_AUDIOVISUAL_DEFAULT,
    PRECIOS_SOFTWARE_DEFAULT,
    PreciosAudiovisual,
    PreciosSoftware,
    PropuestaContexto,
)
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
GEN_EJEMPLOS = 407
GEN_PRECIOS_SW = 408
GEN_SW_DESARROLLO = 409
GEN_SW_IMPLEMENTACION = 410
GEN_SW_MENSUAL = 411
GEN_SW_ANUAL = 412

# user_data keys.
_SEL_KEY = "gen_docs"
_EMPRESA_KEY = "gen_empresa"
_EJEMPLOS_KEY = "gen_ejemplos"
_P_COMPLETO = "gen_precio_completo"
_P_MEDIO = "gen_precio_medio"
_P_COMMUNITY = "gen_precio_community"
_AV_PRECIOS_KEY = "gen_av_precios"
_SW_DESARROLLO = "gen_sw_desarrollo"
_SW_IMPL = "gen_sw_impl"
_SW_MENSUAL = "gen_sw_mensual"
_SW_PRECIOS_KEY = "gen_sw_precios"


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
_IMPLEMENTADOS: frozenset[str] = frozenset(
    {Documento.PROPUESTA_AUDIOVISUAL.value, Documento.PROPUESTA_SOFTWARE.value}
)


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


async def _enviar_html(mensaje: object, html: str, filename: str, caption: str) -> None:
    """Send an HTML string as a Telegram document."""
    archivo = BytesIO(html.encode("utf-8"))
    archivo.name = filename
    await mensaje.reply_document(  # type: ignore[attr-defined]
        document=archivo, filename=filename, caption=caption
    )


def _construir_contexto(context: ContextTypes.DEFAULT_TYPE) -> PropuestaContexto:
    """Build the PropuestaContexto from whatever the conversation collected.

    Fields not overridden fall back to their domain defaults.
    """
    ud = context.user_data if context.user_data is not None else {}
    return PropuestaContexto(
        empresa_nombre=ud.get(_EMPRESA_KEY, ""),
        precios=ud.get(_AV_PRECIOS_KEY, PRECIOS_AUDIOVISUAL_DEFAULT),
        ejemplos_servicios=ud.get(_EJEMPLOS_KEY, EJEMPLOS_SERVICIOS_DEFAULT),
        precios_software=ud.get(_SW_PRECIOS_KEY, PRECIOS_SOFTWARE_DEFAULT),
    )


async def _generar_documentos(
    mensaje: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Generate and send every selected (implemented) document."""
    ctx = _construir_contexto(context)
    seleccion: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    slug = _slug(ctx.empresa_nombre)
    if Documento.PROPUESTA_AUDIOVISUAL.value in seleccion:
        svc_av: GenerarPropuestaAudiovisualService = context.bot_data[
            "propuesta_audiovisual_service"
        ]
        await _enviar_html(
            mensaje,
            svc_av.generar(ctx),
            f"propuesta-audiovisual-{slug}.html",
            obtener_mensaje("propuestas.enviada").format(empresa=ctx.empresa_nombre),
        )
    if Documento.PROPUESTA_SOFTWARE.value in seleccion:
        svc_sw: GenerarPropuestaSoftwareService = context.bot_data[
            "propuesta_software_service"
        ]
        await _enviar_html(
            mensaje,
            svc_sw.generar(ctx),
            f"propuesta-software-{slug}.html",
            obtener_mensaje("propuestas.software_enviada").format(empresa=ctx.empresa_nombre),
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
    # If software is selected, first ask the business's service examples (copy).
    if Documento.PROPUESTA_SOFTWARE.value in seleccionados and mensaje:
        await mensaje.reply_text(obtener_mensaje("generar.pedir_ejemplos"))
        return GEN_EJEMPLOS
    return await _iniciar_pricing(update, context)


async def handle_ejemplos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the service examples for the software copy, then start pricing."""
    mensaje = update.effective_message
    texto = (mensaje.text or "").strip() if mensaje else ""
    if texto and context.user_data is not None:
        context.user_data[_EJEMPLOS_KEY] = texto
    return await _iniciar_pricing(update, context)


async def _iniciar_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask audiovisual prices, else software prices, else generate."""
    seleccion: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    mensaje = update.effective_message
    if Documento.PROPUESTA_AUDIOVISUAL.value in seleccion and mensaje:
        await mensaje.reply_text(
            obtener_mensaje("generar.precios_pregunta"),
            reply_markup=construir_teclado_precios(),
        )
        return GEN_PRECIOS
    return await _despues_av_pricing(update, context)


async def _despues_av_pricing(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """After audiovisual pricing: ask software prices if selected, else generate."""
    seleccion: set[str] = (
        context.user_data.get(_SEL_KEY, set()) if context.user_data is not None else set()
    )
    mensaje = update.effective_message
    if Documento.PROPUESTA_SOFTWARE.value in seleccion and mensaje:
        await mensaje.reply_text(
            obtener_mensaje("generar.precios_sw_pregunta"),
            reply_markup=construir_teclado_precios(),
        )
        return GEN_PRECIOS_SW
    if mensaje:
        await _generar_documentos(mensaje, context)
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

    if opcion == "default":
        # keep audiovisual defaults; continue to software pricing (or generate)
        return await _despues_av_pricing(update, context)

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

    if context.user_data is not None:
        ud = context.user_data
        context.user_data[_AV_PRECIOS_KEY] = PreciosAudiovisual(
            completo=ud[_P_COMPLETO],
            medio=ud[_P_MEDIO],
            community=ud[_P_COMMUNITY],
            trafficker=precio,
        )
    return await _despues_av_pricing(update, context)


async def handle_gen_precios_sw(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Default → generate with default software prices; Edit → ask them."""
    query = update.callback_query
    if query is None:
        return GEN_PRECIOS_SW
    await query.answer()
    data = query.data or ""
    opcion = data.split(":", 1)[1] if ":" in data else ""

    if opcion == "default":
        if update.effective_message:
            await _generar_documentos(update.effective_message, context)
        return ConversationHandler.END

    if update.effective_message:
        await update.effective_message.reply_text(obtener_mensaje("generar.sw_desarrollo"))
    return GEN_SW_DESARROLLO


async def handle_sw_desarrollo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await _capturar_precio(
        update, context, _SW_DESARROLLO, "generar.sw_implementacion",
        GEN_SW_DESARROLLO, GEN_SW_IMPLEMENTACION,
    )


async def handle_sw_implementacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await _capturar_precio(
        update, context, _SW_IMPL, "generar.sw_mensual",
        GEN_SW_IMPLEMENTACION, GEN_SW_MENSUAL,
    )


async def handle_sw_mensual(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await _capturar_precio(
        update, context, _SW_MENSUAL, "generar.sw_anual",
        GEN_SW_MENSUAL, GEN_SW_ANUAL,
    )


async def handle_sw_anual(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Capture the annual price, build software prices and generate."""
    mensaje = update.effective_message
    precio = parsear_precio(mensaje.text or "") if mensaje else None
    if precio is None:
        if mensaje:
            await mensaje.reply_text(obtener_mensaje("generar.precio_invalido"))
        return GEN_SW_ANUAL

    if context.user_data is not None:
        ud = context.user_data
        context.user_data[_SW_PRECIOS_KEY] = PreciosSoftware(
            desarrollo=ud[_SW_DESARROLLO],
            implementacion=ud[_SW_IMPL],
            mensual=ud[_SW_MENSUAL],
            anual=precio,
        )
    if mensaje:
        await _generar_documentos(mensaje, context)
    return ConversationHandler.END
