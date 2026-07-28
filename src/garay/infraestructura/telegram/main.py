"""Entry point for the Telegram bot."""

from __future__ import annotations

import logging
import subprocess

from telegram import Update

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.config.settings import obtener_settings
from garay.dominio.comisiones.motor import MotorComisiones
from garay.infraestructura.ia.extractor_ollama import ExtractorOllama
from garay.infraestructura.ia.extractor_reserva_ollama import ExtractorReservaOllama
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.clientes import SQLAClienteRepository
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.freelancers import SQLAFreelancerRepository
from garay.infraestructura.persistencia.repositorios.puntos_de_venta import (
    SQLAPuntoDeVentaRepository,
)
from garay.infraestructura.persistencia.repositorios.reglas_comision import (
    SQLAReglasComisionRepository,
)
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository
from garay.infraestructura.persistencia.repositorios.tiqueteras import SQLATiqueteraRepository
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository
from garay.infraestructura.telegram.bot import crear_aplicacion
from garay.infraestructura.telegram.notificador import NotificadorGrupoTelegram

_logger = logging.getLogger(__name__)


def _ensure_ollama_running(bin_path: str) -> None:
    """Start ollama serve in the background if it is not already running."""
    try:
        subprocess.Popen(
            [bin_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        _logger.warning("ollama binary not found at %r — photo extraction will fail", bin_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = obtener_settings()
    _ensure_ollama_running(settings.ollama_bin)

    if not settings.grupo_id:
        raise RuntimeError(
            "GARAY_GRUPO_ID is not configured — set it in the environment before starting"
        )

    engine = crear_engine(settings.database_url)
    sf = crear_fabrica_sesiones(engine)

    freelancer_repo = SQLAFreelancerRepository(sf)
    servicio_repo = SQLAServicioRepository(sf)
    pdv_repo = SQLAPuntoDeVentaRepository(sf)
    cliente_repo = SQLAClienteRepository(sf)
    ventas_repo = SQLAVentaRepository(sf)
    reglas_repo = SQLAReglasComisionRepository(sf)
    tiqueteras_repo = SQLATiqueteraRepository(sf)
    comisiones_repo = SQLAComisionRegistradaRepository(sf)

    servicios = [
        (s.numero, s.nombre, s.precio_neto_adulto, s.precio_neto_nino)
        for s in servicio_repo.listar()
    ]
    puntos_venta = [p.nombre for p in pdv_repo.listar()]

    if not servicios:
        raise RuntimeError("No services found in DB — seed the database before starting the bot")
    if not puntos_venta:
        raise RuntimeError(
            "No puntos_de_venta found in DB — seed the database before starting the bot"
        )

    fsm = FSMTiquetera(servicios=servicios, puntos_venta=puntos_venta)

    extractor_ia = ExtractorOllama(
        url=settings.ollama_url,
        modelo=settings.ollama_modelo,
        timeout=settings.ollama_timeout,
    )
    extractor_reserva = ExtractorReservaOllama(extractor_ia)

    notificador = NotificadorGrupoTelegram(settings.telegram_bot_token)
    servicio = RegistrarVentaService(
        ventas=ventas_repo,
        reglas_repo=reglas_repo,
        tiqueteras=tiqueteras_repo,
        puntos_repo=pdv_repo,
        motor=MotorComisiones(),
        notificador=notificador,
        grupo_id=settings.grupo_id,
        comisiones_repo=comisiones_repo,
    )

    app = crear_aplicacion(settings.telegram_bot_token)
    app.bot_data.update(
        {
            "fsm": fsm,
            "freelancer_repo": freelancer_repo,
            "servicio_repo": servicio_repo,
            "pdv_repo": pdv_repo,
            "cliente_repo": cliente_repo,
            "venta_repo": ventas_repo,
            "comision_registrada_repo": comisiones_repo,
            "registrar_venta_service": servicio,
            "extractor_reserva": extractor_reserva,
            "ollama_timeout": settings.ollama_timeout,
        }
    )

    try:
        app.run_polling(allowed_updates=list(Update.ALL_TYPES))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
