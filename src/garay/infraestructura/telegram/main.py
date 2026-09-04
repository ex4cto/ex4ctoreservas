"""Entry point for the Telegram bot."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from telegram import Update

from garay.aplicacion.conciliacion.conciliar_ingresos import ConciliarIngresosService
from garay.aplicacion.egresos.registrar_egreso_manual import RegistrarEgresoManualService
from garay.aplicacion.factura.generar_y_guardar import GenerarYGuardarFacturaService
from garay.aplicacion.factura.regenerar_factura import RegenerarFacturaService
from garay.aplicacion.factura.servicio import GenerarFacturaService
from garay.aplicacion.infraestructura_monitor.costo_railway import MonitorCostoRailwayService
from garay.aplicacion.infraestructura_monitor.cuota_resend import MonitorCuotaResendService
from garay.aplicacion.infraestructura_monitor.servicio import (
    MonitorServiciosInfraestructuraService,
)
from garay.aplicacion.propuestas.servicio import GenerarPropuestaAudiovisualService
from garay.aplicacion.propuestas.servicio_software import GenerarPropuestaSoftwareService
from garay.aplicacion.reportes.flujo_caja import FlujoCajaService
from garay.aplicacion.reportes.mis_ventas import MisVentasService
from garay.aplicacion.reportes.movimientos_recientes import MovimientosRecientesService
from garay.aplicacion.reportes.ranking_tour import RankingTourService
from garay.aplicacion.reportes.reconciliacion_ventas_ingresos import (
    ReconciliacionVentasIngresosService,
)
from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService
from garay.aplicacion.reportes.waterfall_ventas import WaterfallVentasService
from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.aplicacion.ventas.anular_venta import AnularVentaService
from garay.aplicacion.ventas.editar_fecha_venta import EditarFechaVentaService
from garay.config.settings import obtener_settings
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.conciliacion.motor import MotorConciliacion
from garay.dominio.infraestructura_monitor.costo_railway import PreciosRailway
from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura
from garay.dominio.puertos.servicios_externos import NotificadorEmail
from garay.infraestructura.email.adaptador_resend import ResendAdapter
from garay.infraestructura.ia.extractor_claude import ExtractorClaude
from garay.infraestructura.ia.extractor_reserva import ExtractorReservaFoto
from garay.infraestructura.monitor.proveedor_uso_railway_http import ProveedorUsoRailwayHTTP
from garay.infraestructura.persistencia.contador_facturas_sql import ContadorFacturasSQLAlchemy
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.auditoria_ventas import (
    SQLAAuditoriaVentaRepository,
)
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
from garay.infraestructura.persistencia.repositorios.facturas import SQLAFacturaRepository
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
    factura_repo = SQLAFacturaRepository(sf)

    auditoria_venta_repo = SQLAAuditoriaVentaRepository(sf)
    anular_venta_service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_venta_repo)
    editar_fecha_venta_service = EditarFechaVentaService(
        ventas=ventas_repo, auditoria=auditoria_venta_repo
    )

    egreso_service = RegistrarEgresoManualService(
        egreso_repo=egreso_repo,
        categoria_repo=categoria_egreso_repo,
    )

    servicios = [
        (s.numero, s.nombre, s.precio_neto_adulto, s.precio_neto_nino, s.categoria, s.horarios)
        for s in servicio_repo.listar_activos()
    ]
    puntos_venta = [p.nombre for p in pdv_repo.listar()]

    if not servicios:
        raise RuntimeError("No services found in DB — seed the database before starting the bot")
    if not puntos_venta:
        raise RuntimeError(
            "No puntos_de_venta found in DB — seed the database before starting the bot"
        )

    fsm = FSMTiquetera(
        servicios=servicios,
        puntos_venta=puntos_venta,
        freelancers=[(f.id, f.nombre, f.activo) for f in freelancer_repo.listar_todos()],
        multi_tour_habilitado=settings.multi_tour_habilitado,
    )

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

    logo_url = settings.factura_logo_url
    if not logo_url:
        logo_path = Path(__file__).parents[4] / "assets" / "logo.png"
        if logo_path.exists():
            logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
            logo_url = f"data:image/png;base64,{logo_b64}"

    # Proposal generator (MVP): load the audiovisual template + embed Ryan's logo
    # as a base64 data URI so the sent HTML is self-contained.
    _repo_root = Path(__file__).parents[4]
    _plantilla_path = _repo_root / "assets" / "propuestas" / "audiovisual.html"
    _plantilla_audiovisual = (
        _plantilla_path.read_text(encoding="utf-8") if _plantilla_path.exists() else ""
    )
    _logo_ryan_path = _repo_root / "assets" / "logo-ryan.png"
    _logo_ryan_uri = ""
    if _logo_ryan_path.exists():
        _logo_ryan_b64 = base64.b64encode(_logo_ryan_path.read_bytes()).decode()
        _logo_ryan_uri = f"data:image/png;base64,{_logo_ryan_b64}"
    propuesta_audiovisual_service = GenerarPropuestaAudiovisualService(
        plantilla=_plantilla_audiovisual,
        logo_data_uri=_logo_ryan_uri,
    )
    _plantilla_software_path = _repo_root / "assets" / "propuestas" / "software.html"
    _plantilla_software = (
        _plantilla_software_path.read_text(encoding="utf-8")
        if _plantilla_software_path.exists()
        else ""
    )
    propuesta_software_service = GenerarPropuestaSoftwareService(
        plantilla=_plantilla_software,
        logo_data_uri=_logo_ryan_uri,
    )

    generar_factura_service = GenerarFacturaService(logo_url=logo_url)
    notificador_email: NotificadorEmail | None = None
    if settings.resend_api_key and settings.resend_from:
        notificador_email = ResendAdapter(
            api_key=settings.resend_api_key,
            from_address=settings.resend_from,
        )
    factura_service = GenerarYGuardarFacturaService(
        generador=generar_factura_service,
        facturas=factura_repo,
        notificador=notificador_email,
    )
    regenerar_factura_service: RegenerarFacturaService | None = None
    if notificador_email is not None:
        regenerar_factura_service = RegenerarFacturaService(
            ventas=ventas_repo,
            clientes=cliente_repo,
            servicios=servicio_repo,
            facturas=factura_repo,
            generador=generar_factura_service,
            email=notificador_email,
        )

    # Build the infrastructure services monitor (stateless, config-only).
    servicios_infra: list[ServicioInfraestructura] = []
    if settings.dominio_renovacion is not None:
        servicios_infra.append(
            ServicioInfraestructura(
                nombre="Dominio",
                fecha_renovacion=settings.dominio_renovacion,
                bandas_aviso=settings.dominio_bandas_aviso,
            )
        )
    monitor_infra_service = MonitorServiciosInfraestructuraService(servicios=servicios_infra)

    # Build the Resend quota monitor (uses the same session factory as other repos).
    contador_facturas = ContadorFacturasSQLAlchemy(sf)
    monitor_cuota_resend_service = MonitorCuotaResendService(
        contador=contador_facturas,
        cap_mensual=settings.resend_cap_mensual,
        cap_diario=settings.resend_cap_diario,
        bandas_mensual=settings.resend_bandas_mensual,
        umbral_diario=settings.resend_umbral_diario,
    )

    # Build the Railway cost monitor (optional — only when token and project id are set).
    monitor_costo_railway_service: MonitorCostoRailwayService | None = None
    if settings.railway_api_token and settings.railway_project_id:
        precios_railway = PreciosRailway(
            precio_memoria_gb_min=settings.railway_precio_memoria_gb_min,
            precio_cpu_vcpu_min=settings.railway_precio_cpu_vcpu_min,
            precio_egress_gb=settings.railway_precio_egress_gb,
            precio_volumen_gb_min=settings.railway_precio_volumen_gb_min,
        )
        proveedor_railway = ProveedorUsoRailwayHTTP(
            api_token=settings.railway_api_token,
            project_id=settings.railway_project_id,
        )
        monitor_costo_railway_service = MonitorCostoRailwayService(
            proveedor=proveedor_railway,
            precios=precios_railway,
            umbral=settings.railway_umbral_costo,
            plan_fee=settings.railway_plan_fee,
        )

    app = crear_aplicacion(settings.telegram_bot_token)
    resumen_ventas_service = ResumenVentasService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
        freelancers=freelancer_repo,
    )
    mis_ventas_service = MisVentasService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
    )
    flujo_caja_service = FlujoCajaService(
        ingresos=ingreso_repo,
        egresos=egreso_repo,
        conciliaciones=conciliacion_repo,
    )
    movimientos_service = MovimientosRecientesService(
        ingresos_repo=ingreso_repo,
        egresos_repo=egreso_repo,
    )
    waterfall_service = WaterfallVentasService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
    )
    ranking_tour_service = RankingTourService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
        servicios=servicio_repo,
    )
    reconciliacion_service = ReconciliacionVentasIngresosService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
        ingresos=ingreso_repo,
    )
    motor_conciliacion = MotorConciliacion(
        tolerancia_pct=settings.conciliacion_tolerancia_pct,
        ventana_dias=settings.conciliacion_ventana_dias,
        confianza_auto=settings.conciliacion_confianza_auto,
        peso_monto=settings.conciliacion_peso_monto,
        peso_fecha=settings.conciliacion_peso_fecha,
    )
    conciliar_service = ConciliarIngresosService(
        ingresos=ingreso_repo,
        ventas=ventas_repo,
        conciliaciones=conciliacion_repo,
        motor=motor_conciliacion,
        ventana_dias=settings.conciliacion_ventana_dias,
    )

    app.bot_data.update(
        {
            "monitor_infra_service": monitor_infra_service,
            "monitor_cuota_resend_service": monitor_cuota_resend_service,
            "monitor_costo_railway_service": monitor_costo_railway_service,
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
            "conciliacion_repo": conciliacion_repo,
            "resumen_ventas_service": resumen_ventas_service,
            "mis_ventas_service": mis_ventas_service,
            "flujo_caja_service": flujo_caja_service,
            "movimientos_service": movimientos_service,
            "waterfall_service": waterfall_service,
            "ranking_tour_service": ranking_tour_service,
            "reconciliacion_service": reconciliacion_service,
            "conciliar_service": conciliar_service,
            "factura_service": factura_service,
            "propuesta_audiovisual_service": propuesta_audiovisual_service,
            "propuesta_software_service": propuesta_software_service,
            "factura_repo": factura_repo,
            "auditoria_venta_repo": auditoria_venta_repo,
            "anular_venta_service": anular_venta_service,
            "editar_fecha_venta_service": editar_fecha_venta_service,
            "regenerar_factura_service": regenerar_factura_service,
            "notificador": notificador,
            "grupo_id": settings.grupo_id,
            "propietario_telegram_ids": settings.propietario_telegram_ids,
            "monitor_infra_telegram_ids": settings.dev_telegram_ids,
        }
    )

    try:
        app.run_polling(allowed_updates=list(Update.ALL_TYPES))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
