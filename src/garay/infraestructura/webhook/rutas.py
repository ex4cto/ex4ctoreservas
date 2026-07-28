"""FastAPI router for the Forward Email webhook endpoint.

Single-tenant design: one route handles all forwarded bank emails.
Always returns 200 OK so Forward Email does not retry on domain errors.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from garay.aplicacion.webhook.servicio import guardar_ingreso
from garay.config.settings import obtener_settings
from garay.dominio.puertos.repositorios import IngresoRepository
from garay.infraestructura.webhook.parser.base import ErrorParseoBanco, detectar_banco
from garay.infraestructura.webhook.parser.fabrica import obtener_parser
from garay.infraestructura.webhook.schemas import PayloadEmail
from garay.infraestructura.webhook.validador import ErrorSecretInvalido, validar_secret

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_moneda() -> str:
    return obtener_settings().moneda_predeterminada


@router.post("/webhook/email")
def recibir_email(
    payload: PayloadEmail,
    secret: str = Query(...),
    repo: IngresoRepository = Depends(),  # noqa: B008
    moneda: str = Depends(_get_moneda),
) -> dict[str, str]:
    """Receive a forwarded bank email notification from Forward Email.

    Steps:
    1. Validate HMAC secret.
    2. Skip if message_id is empty (safety guard).
    3. Skip if message_id already stored (idempotency).
    4. Detect bank from sender email.
    5. Parse email body into PagoExtraido.
    6. Persist Ingreso.
    """
    try:
        validar_secret(secret, expected=obtener_settings().forward_email_secret)
    except ErrorSecretInvalido:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    if not payload.message_id.strip():
        logger.debug("Skipping email with empty message_id")
        return {"estado": "ok"}

    if repo.existe_referencia(payload.message_id):
        logger.info("Duplicate message_id=%s — skipping", payload.message_id)
        return {"estado": "ok"}

    banco = detectar_banco(payload.remitente_email)
    if banco is None:
        logger.warning("Unknown bank sender: %s — skipping", payload.remitente_email)
        return {"estado": "ok"}

    try:
        parser = obtener_parser(banco)
        pago = parser.parsear(payload.cuerpo_html, payload.cuerpo_texto)
    except ErrorParseoBanco as exc:
        logger.warning("Parse error for %s: %s — skipping", banco, exc)
        return {"estado": "ok"}

    guardar_ingreso(pago, payload.message_id, repo, moneda=moneda)
    return {"estado": "ok"}
