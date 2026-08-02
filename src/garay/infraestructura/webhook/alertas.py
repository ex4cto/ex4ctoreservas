"""Pure alert-message builders for the webhook quarantine flow.

Both functions are side-effect-free and unit-testable in isolation.
All dynamic values are HTML-escaped because Telegram uses parse_mode=HTML
and email bodies are attacker-controlled.
"""

from __future__ import annotations

import html

# Maximum snippet length (in characters) BEFORE html.escape().
_MAX_SNIPPET = 500


def construir_alerta_dev(
    *,
    banco: str,
    direccion: str,
    referencia: str,
    correo_origen: str | None,
    error_parseo: str,
    cuerpo_snippet: str,
) -> str:
    """Build a technical HTML alert message for developer/admin Telegram users.

    Every dynamic value is passed through html.escape() to prevent injection
    into the Telegram HTML parse tree.  The body snippet is capped at
    _MAX_SNIPPET characters BEFORE escaping so the final message stays readable.
    """
    snippet = cuerpo_snippet[:_MAX_SNIPPET]

    return (
        "<b>⚠️ Correo no parseado</b>\n"
        f"<b>Banco:</b> {html.escape(banco)}\n"
        f"<b>Dirección:</b> {html.escape(direccion)}\n"
        f"<b>Referencia:</b> {html.escape(referencia)}\n"
        f"<b>Origen:</b> {html.escape(correo_origen or '(desconocido)')}\n"
        f"<b>Error:</b> <code>{html.escape(error_parseo)}</code>\n\n"
        f"<b>Snippet del cuerpo:</b>\n<pre>{html.escape(snippet)}</pre>"
    )


def construir_alerta_freelancer(*, banco: str) -> str:
    """Build a plain-language Spanish alert for the freelancer group chat.

    No raw error details are included — only a user-facing notice to act manually.
    The bank name is still escaped because it comes from email sender detection.
    """
    banco_safe = html.escape(banco)
    return (
        f"⚠️ Entró un correo de {banco_safe} con un movimiento que no se pudo "
        "registrar automáticamente. Ya avisamos al equipo técnico; si es urgente, "
        "cargalo a mano."
    )
