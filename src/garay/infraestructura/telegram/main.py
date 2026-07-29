"""Entry point for the Telegram bot."""

from __future__ import annotations

import logging

from telegram import Update

from garay.aplicacion.egresos.generar_gastos_recurrentes import GenerarGastosRecurrentesService
from garay.aplicacion.egresos.registrar_egreso_manual import RegistrarEgresoManualService
from garay.aplicacion.reportes.flujo_caja import FlujoCajaService
from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService
from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.config.settings import obtener_settings
from garay.dominio.comisiones.motor import MotorComisiones
from garay.infraestructura.ia.extractor_claude import ExtractorClaude
from garay.infraestructura.ia.extractor_reserva import ExtractorReservaFoto
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.categorias_egreso import (
    SQLACategoriaEgresoRepository,
)
from garay.infraestructura.persistencia.repositorios.clientes import SQLAClienteRepository
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.conciliaciones import (
    SQLAConciliacionRepository,
)
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository
from garay.infraestructura.persistencia.repositorios.freelancers import SQLAFreelancerRepository
from garay.infraestructura.persistencia.repositorios.gastos_recurrentes import (
    SQLAGastoRecurrenteRepository,
)
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository
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


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = obtener_settings()

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
    conciliacion_repo = SQLAConciliacionRepository(sf)
    ingreso_repo = SQLAIngresoRepository(sf)
    egreso_repo = SQLAEgresoRepository(sf)
    categoria_egreso_repo = SQLACategoriaEgresoRepository(sf)
    gasto_recurrente_repo = SQLAGastoRecurrenteRepository(sf)

    egreso_service = RegistrarEgresoManualService(
        egreso_repo=egreso_repo,
        categoria_repo=categoria_egreso_repo,
    )
    generar_gastos_service = GenerarGastosRecurrentesService(
        recurrentes_repo=gasto_recurrente_repo,
        egreso_repo=egreso_repo,
    )

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

    extractor_ia = ExtractorClaude(
        api_key=settings.anthropic_api_key,
        modelo=settings.claude_modelo,
    )
    _logger.info("Using Claude vision extractor (model: %s)", settings.claude_modelo)
    extractor_reserva = ExtractorReservaFoto(extractor_ia)

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
    resumen_ventas_service = ResumenVentasService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
    )
    flujo_caja_service = FlujoCajaService(
        ingresos=ingreso_repo,
        egresos=egreso_repo,
        conciliaciones=conciliacion_repo,
    )

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
            "ingreso_repo": ingreso_repo,
            "egreso_repo": egreso_repo,
            "egreso_service": egreso_service,
            "recurrente_service": gasto_recurrente_repo,
            "generar_gastos_service": generar_gastos_service,
            "conciliacion_repo": conciliacion_repo,
            "resumen_ventas_service": resumen_ventas_service,
            "flujo_caja_service": flujo_caja_service,
        }
    )

    try:
        app.run_polling(allowed_updates=list(Update.ALL_TYPES))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
