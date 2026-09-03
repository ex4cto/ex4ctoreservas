"""Dev-only /nueva_propuesta command — generates the audiovisual proposal (MVP).

Walking skeleton: asks for the company name, fills the audiovisual proposal
template via GenerarPropuestaAudiovisualService, and sends the resulting HTML
back to the developer as a Telegram document.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.propuestas.servicio import GenerarPropuestaAudiovisualService
from garay.infraestructura.telegram.auth import requiere_dev_conv

logger = logging.getLogger(__name__)

# ConversationHandler state — its own state space, no collision with other convs.
PROP_EMPRESA = 400


def _slug(texto: str) -> str:
    """Turn a company name into a filename-safe slug."""
    limpio = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return limpio or "empresa"


@requiere_dev_conv
async def cmd_nueva_propuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: ask for the company name."""
    if update.effective_message:
        await update.effective_message.reply_text("¿Cuál es el nombre de la empresa?")
    return PROP_EMPRESA


async def handle_prop_empresa(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Generate the audiovisual proposal for the given company and send it."""
    mensaje = update.effective_message
    nombre = (mensaje.text or "").strip() if mensaje else ""
    if not nombre:
        if mensaje:
            await mensaje.reply_text("Escribe el nombre de la empresa.")
        return PROP_EMPRESA

    service: GenerarPropuestaAudiovisualService = context.bot_data[
        "propuesta_audiovisual_service"
    ]
    html = service.generar(nombre)

    archivo = BytesIO(html.encode("utf-8"))
    archivo.name = f"propuesta-audiovisual-{_slug(nombre)}.html"
    if mensaje:
        await mensaje.reply_document(
            document=archivo,
            filename=archivo.name,
            caption=f"Propuesta audiovisual — {nombre}",
        )
    return ConversationHandler.END
