"""FastAPI router for the Forward Email webhook endpoint.

Single-tenant design: one route handles all forwarded bank emails.
Always returns 200 OK so Forward Email does not retry on domain errors.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from garay.aplicacion.webhook.servicio import guardar_egreso, guardar_ingreso
from garay.config.settings import obtener_settings
from garay.dominio.conciliacion.entidades import CorreoNoParseado
from garay.dominio.conciliacion.reenvio import detectar_reenvio
from garay.dominio.puertos.repositorios import (
    CorreoNoParseadoRepository,
    EgresoRepository,
    IngresoRepository,
)
from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.infraestructura.telegram.errores import NotificadorError, NotificadorNoDisponible
from garay.infraestructura.webhook.alertas import (
    construir_alerta_dev,
    construir_alerta_freelancer,
)
from garay.infraestructura.webhook.parser.base import (
    DIRECCION_EGRESO,
    ErrorParseoBanco,
    detectar_banco,
    detectar_direccion,
)
from garay.infraestructura.webhook.parser.fabrica import obtener_parser, obtener_parser_egreso
from garay.infraestructura.webhook.schemas import PayloadEmail
from garay.infraestructura.webhook.validador import ErrorSecretInvalido, validar_secret

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_moneda() -> str:
    return obtener_settings().moneda_predeterminada


def _parse_dev_ids(ids_str: str) -> list[str]:
    """Parse a comma-separated string of Telegram IDs into a list of stripped strings.

    Returns an empty list when the input is blank.  Mirrors the split/strip/filter
    pattern used in garay.infraestructura.telegram.auth.
    """
    return [x.strip() for x in ids_str.split(",") if x.strip()]


def _quarantine_and_alert(
    *,
    payload: PayloadEmail,
    banco: str,
    direccion: str,
    exc: ErrorParseoBanco,
    correo_repo: CorreoNoParseadoRepository,
    notificador: NotificadorGrupo,
) -> None:
    """Persist an unparseable email and send best-effort alerts.

    Persistence happens first.  Each Telegram call is individually wrapped so
    a network or API failure never prevents the other alerts from being sent,
    and never causes the route to return non-200.
    """
    # --- 1. Persist ---
    correo = CorreoNoParseado(
        id=uuid.uuid4(),
        banco=banco,
        direccion=direccion,
        referencia=payload.message_id,
        asunto=payload.asunto,
        correo_origen=payload.remitente_email,
        cuerpo_texto=payload.cuerpo_texto,
        cuerpo_html=payload.cuerpo_html,
        error_parseo=str(exc),
        fecha_recibido=datetime.now(UTC),
        procesado=False,
    )
    try:
        correo_repo.guardar(correo)
    except IntegrityError:
        # Duplicate referencia — already quarantined; no-op.
        logger.warning(
            "DIAG quarantine duplicate: referencia=%r already quarantined — skipping insert",
            payload.message_id,
        )

    # --- 2. Best-effort dev alerts ---
    settings = obtener_settings()
    cuerpo_snippet = payload.cuerpo_texto or payload.cuerpo_html
    dev_msg = construir_alerta_dev(
        banco=banco,
        direccion=direccion,
        referencia=payload.message_id,
        correo_origen=payload.remitente_email,
        error_parseo=str(exc),
        cuerpo_snippet=cuerpo_snippet,
    )
    dev_ids = _parse_dev_ids(settings.dev_telegram_ids)
    for dev_id in dev_ids:
        try:
            notificador.notificar(dev_msg, dev_id)
        except (NotificadorError, NotificadorNoDisponible):
            logger.warning(
                "DIAG alert: failed to notify dev_id=%s — continuing", dev_id
            )

    # --- 3. Best-effort freelancer group alert ---
    grupo_id = settings.grupo_id.strip()
    if grupo_id:
        freelancer_msg = construir_alerta_freelancer(banco=banco)
        try:
            notificador.notificar(freelancer_msg, grupo_id)
        except (NotificadorError, NotificadorNoDisponible):
            logger.warning(
                "DIAG alert: failed to notify grupo_id=%s — continuing", grupo_id
            )


@router.post("/webhook/email")
def recibir_email(
    payload: PayloadEmail,
    secret: str = Query(...),
    ingreso_repo: IngresoRepository = Depends(),  # noqa: B008
    egreso_repo: EgresoRepository = Depends(),  # noqa: B008
    correo_repo: CorreoNoParseadoRepository = Depends(),  # noqa: B008
    notificador: NotificadorGrupo = Depends(),  # noqa: B008
    moneda: str = Depends(_get_moneda),
) -> dict[str, str]:
    """Receive a forwarded bank email notification from Forward Email.

    Steps:
    1. Validate HMAC secret.
    2. Skip if message_id is empty (safety guard).
    3. Detect bank from sender email.
    4. Detect direction (ingreso or egreso) from email body keywords.
    5. Skip if message_id already stored (idempotency check per direction).
    6. Parse email body.
    7. On parse error: quarantine + dual-alert, then return 200.
    8. Persist Ingreso or Egreso.
    """
    try:
        validar_secret(secret, expected=obtener_settings().forward_email_secret)
    except ErrorSecretInvalido:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    # Observability: log every inbound email's key fields so no email is ever
    # dropped silently (the endpoint always returns 200 by design).
    logger.warning(
        "DIAG inbound: msgid=%r from=%r len_txt=%d len_html=%d",
        payload.message_id[:60],
        payload.remitente_email[:100],
        len(payload.cuerpo_texto),
        len(payload.cuerpo_html),
    )

    if not payload.message_id.strip():
        logger.warning("DIAG skip: empty message_id — dropping email")
        return {"estado": "ok"}

    cuerpo = payload.cuerpo_texto or payload.cuerpo_html
    banco = detectar_banco(payload.remitente_email, cuerpo)
    if banco is None:
        logger.warning("Unknown bank sender: %s — skipping", payload.remitente_email)
        return {"estado": "ok"}

    direccion = detectar_direccion(cuerpo)
    logger.warning("DIAG route: banco=%s direccion=%s", banco, direccion)

    if direccion == DIRECCION_EGRESO:
        if egreso_repo.existe_referencia(payload.message_id):
            logger.info("Duplicate egreso message_id=%s — skipping", payload.message_id)
            return {"estado": "ok"}
        try:
            parser = obtener_parser_egreso(banco)
            pago = parser.parsear(payload.cuerpo_html, payload.cuerpo_texto)
        except ErrorParseoBanco as exc:
            logger.warning("Parse error (egreso) for %s: %s — quarantining", banco, exc)
            _quarantine_and_alert(
                payload=payload,
                banco=banco,
                direccion=direccion,
                exc=exc,
                correo_repo=correo_repo,
                notificador=notificador,
            )
            return {"estado": "ok"}
        guardar_egreso(
            pago,
            payload.message_id,
            egreso_repo,
            moneda=moneda,
            correo_origen=payload.remitente_email,
            reenviado=detectar_reenvio(payload.asunto, cuerpo),
        )
    else:
        if ingreso_repo.existe_referencia(payload.message_id):
            logger.info("Duplicate ingreso message_id=%s — skipping", payload.message_id)
            return {"estado": "ok"}
        try:
            parser_ingreso = obtener_parser(banco)
            pago_ingreso = parser_ingreso.parsear(payload.cuerpo_html, payload.cuerpo_texto)
        except ErrorParseoBanco as exc:
            logger.warning("Parse error (ingreso) for %s: %s — quarantining", banco, exc)
            _quarantine_and_alert(
                payload=payload,
                banco=banco,
                direccion=direccion,
                exc=exc,
                correo_repo=correo_repo,
                notificador=notificador,
            )
            return {"estado": "ok"}
        guardar_ingreso(
            pago_ingreso,
            payload.message_id,
            ingreso_repo,
            moneda=moneda,
            correo_origen=payload.remitente_email,
            reenviado=detectar_reenvio(payload.asunto, cuerpo),
        )

    return {"estado": "ok"}
