"""Reprocess service: re-parse quarantined emails after a parser fix.

Reads pending rows from correos_no_parseados, retries parsing, and persists the
recovered Ingreso/Egreso entities.  Designed to run as a CLI script or be called
from any infrastructure entrypoint.

Architecture note: this module lives in infraestructura because it coordinates
infra parsers (fabrica) with application services (guardar_ingreso/guardar_egreso).
infra → aplicacion imports are allowed; aplicacion → infra are not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from garay.aplicacion.webhook.servicio import guardar_egreso, guardar_ingreso
from garay.dominio.conciliacion.entidades import CorreoNoParseado
from garay.dominio.conciliacion.reenvio import detectar_reenvio
from garay.dominio.puertos.repositorios import (
    CorreoNoParseadoRepository,
    EgresoRepository,
    IngresoRepository,
)
from garay.infraestructura.webhook.parser.base import DIRECCION_EGRESO, ErrorParseoBanco
from garay.infraestructura.webhook.parser.fabrica import obtener_parser, obtener_parser_egreso

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoReproceso:
    """Summary returned by reprocesar_pendientes."""

    recuperados: int = field(default=0)
    ya_existian: int = field(default=0)
    fallidos: int = field(default=0)


def reprocesar_pendientes(
    *,
    correo_repo: CorreoNoParseadoRepository,
    ingreso_repo: IngresoRepository,
    egreso_repo: EgresoRepository,
    moneda: str,
    max_intentos: int,
) -> ResultadoReproceso:
    """Re-parse quarantined emails and persist any that now succeed.

    For each pending CorreoNoParseado row (procesado=False, intentos < max_intentos):

    1. Route by the stored correo.direccion (ingreso vs egreso).
    2. Re-parse using the appropriate parser factory.
    3. On ErrorParseoBanco: register the failed attempt; do NOT mark processed.
    4. On success, check for existing reference (idempotency).
       - If the reference already exists: mark processed; count as ya_existian.
       - Otherwise: persist via guardar_ingreso/guardar_egreso; mark processed;
         count as recuperado.
    5. Any other unexpected exception is caught per-row so one bad row never
       aborts the whole batch.  The row is counted as fallido.
    """
    pendientes = correo_repo.listar_pendientes(max_intentos)

    recuperados = 0
    ya_existian = 0
    fallidos = 0

    for correo in pendientes:
        try:
            _procesar_fila(
                correo=correo,
                correo_repo=correo_repo,
                ingreso_repo=ingreso_repo,
                egreso_repo=egreso_repo,
                moneda=moneda,
            )
        except _Recuperado:
            recuperados += 1
        except _YaExistia:
            ya_existian += 1
        except _Fallido:
            fallidos += 1
        except Exception:
            # Unexpected error — count as fallido so the batch continues.
            logger.exception(
                "Unexpected error reprocessing correo id=%s referencia=%r — skipping",
                correo.id,
                correo.referencia,
            )
            fallidos += 1

    return ResultadoReproceso(
        recuperados=recuperados,
        ya_existian=ya_existian,
        fallidos=fallidos,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


class _Recuperado(Exception):
    """Signal: row was re-parsed and persisted."""


class _YaExistia(Exception):
    """Signal: row was re-parsed but reference already exists; marked processed."""


class _Fallido(Exception):
    """Signal: parser still raised ErrorParseoBanco; attempt registered."""


def _procesar_fila(
    *,
    correo: CorreoNoParseado,
    correo_repo: CorreoNoParseadoRepository,
    ingreso_repo: IngresoRepository,
    egreso_repo: EgresoRepository,
    moneda: str,
) -> None:
    """Process a single pending row.  Raises _Recuperado, _YaExistia, or _Fallido."""
    reenviado = detectar_reenvio(
        correo.asunto,
        correo.cuerpo_texto or correo.cuerpo_html,
    )

    if correo.direccion == DIRECCION_EGRESO:
        _procesar_egreso(
            correo=correo,
            correo_repo=correo_repo,
            egreso_repo=egreso_repo,
            moneda=moneda,
            reenviado=reenviado,
        )
    else:
        _procesar_ingreso(
            correo=correo,
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            moneda=moneda,
            reenviado=reenviado,
        )


def _procesar_ingreso(
    *,
    correo: CorreoNoParseado,
    correo_repo: CorreoNoParseadoRepository,
    ingreso_repo: IngresoRepository,
    moneda: str,
    reenviado: bool,
) -> None:
    try:
        parser = obtener_parser(correo.banco)
        pago = parser.parsear(correo.cuerpo_html, correo.cuerpo_texto)
    except ErrorParseoBanco as exc:
        logger.warning(
            "Reprocess parse error (ingreso) banco=%s referencia=%r: %s",
            correo.banco,
            correo.referencia,
            exc,
        )
        correo_repo.registrar_intento_fallido(correo.id, str(exc))
        raise _Fallido from exc

    if ingreso_repo.existe_referencia(correo.referencia):
        logger.info(
            "Reprocess: ingreso referencia=%r already exists — marking processed",
            correo.referencia,
        )
        correo_repo.marcar_procesado(correo.id)
        raise _YaExistia

    guardar_ingreso(
        pago,
        correo.referencia,
        ingreso_repo,
        moneda=moneda,
        correo_origen=correo.correo_origen,
        reenviado=reenviado,
    )
    correo_repo.marcar_procesado(correo.id)
    logger.info(
        "Reprocess: recovered ingreso referencia=%r banco=%s",
        correo.referencia,
        correo.banco,
    )
    raise _Recuperado


def _procesar_egreso(
    *,
    correo: CorreoNoParseado,
    correo_repo: CorreoNoParseadoRepository,
    egreso_repo: EgresoRepository,
    moneda: str,
    reenviado: bool,
) -> None:
    try:
        parser = obtener_parser_egreso(correo.banco)
        pago = parser.parsear(correo.cuerpo_html, correo.cuerpo_texto)
    except ErrorParseoBanco as exc:
        logger.warning(
            "Reprocess parse error (egreso) banco=%s referencia=%r: %s",
            correo.banco,
            correo.referencia,
            exc,
        )
        correo_repo.registrar_intento_fallido(correo.id, str(exc))
        raise _Fallido from exc

    if egreso_repo.existe_referencia(correo.referencia):
        logger.info(
            "Reprocess: egreso referencia=%r already exists — marking processed",
            correo.referencia,
        )
        correo_repo.marcar_procesado(correo.id)
        raise _YaExistia

    guardar_egreso(
        pago,
        correo.referencia,
        egreso_repo,
        moneda=moneda,
        correo_origen=correo.correo_origen,
        reenviado=reenviado,
    )
    correo_repo.marcar_procesado(correo.id)
    logger.info(
        "Reprocess: recovered egreso referencia=%r banco=%s",
        correo.referencia,
        correo.banco,
    )
    raise _Recuperado
