"""Build and return the PTB Application."""

from __future__ import annotations

import asyncio
import datetime
import logging
import zoneinfo

from telegram import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.infraestructura_monitor.costo_railway import (
    AvisoCostoRailway,
    MonitorCostoRailwayService,
)
from garay.aplicacion.infraestructura_monitor.cuota_resend import (
    AvisoCuota,
    MonitorCuotaResendService,
)
from garay.aplicacion.infraestructura_monitor.servicio import (
    MonitorServiciosInfraestructuraService,
)
from garay.aplicacion.tiquetera.fsm import EstadoFSM
from garay.config.settings import obtener_settings
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.telegram import handlers_conciliacion, handlers_reportes
from garay.infraestructura.telegram.alertas_monitor import (
    construir_alerta_costo_railway,
    construir_alerta_cuota,
    construir_alerta_renovacion,
)
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.infraestructura.telegram.handlers import (
    _foto_en_conversacion,
    cmd_cancelar,
    cmd_cancelar_sin_conv,
    cmd_foto,
    cmd_help,
    cmd_mis_ventas,
    cmd_start,
    cmd_verificar_pago,
    handle_canal_origen,
    handle_cliente_email,
    handle_cliente_habitacion,
    handle_cliente_hotel,
    handle_cliente_identificacion,
    handle_cliente_nombre,
    handle_cliente_telefono,
    handle_cliente_tipo_id,
    handle_confirmacion,
    handle_destino,
    handle_editar_cerrador,
    handle_editar_selector,
    handle_editar_vendedor,
    handle_esperando_foto,
    handle_factura_idioma,
    handle_familia,
    handle_fecha_salida,
    handle_horario_salida,
    handle_iniciar_venta,
    handle_metodo_input,
    handle_modalidad_venta,
    handle_monto_abono,
    handle_monto_neto,
    handle_monto_valor,
    handle_otro_tour,
    handle_participante_otro,
    handle_participante_rol,
    handle_pax_adultos,
    handle_pax_ninos,
    handle_punto_de_venta,
    handle_servicio_en_familia,
    handle_tipo_reserva,
)
from garay.infraestructura.telegram.handlers_egresos import (
    CB_EDIT_CATEGORIA,
    CB_EDIT_DESCRIPCION,
    CB_EDIT_FECHA,
    CB_EDIT_MONTO,
    CB_EDIT_VOLVER,
    CB_HOY,
    CB_USAR_SUGERIDO,
    EGRESO_CATEGORIA,
    EGRESO_CONFIRMACION,
    EGRESO_DESCRIPCION,
    EGRESO_EDIT_MENU,
    EGRESO_FECHA,
    EGRESO_MONTO,
    EGRESO_REC_CONFIRM,
    EGRESO_REC_EDIT_MENU,
    EGRESO_REC_FECHA,
    EGRESO_REC_MONTO,
    EGRESO_SELECCION,
    GF_CATEGORIA,
    GF_CONFIRMACION,
    GF_DIA,
    GF_MONTO,
    GF_NOMBRE,
    cmd_gastos_fijos,
    cmd_nuevo_egreso,
    handle_egreso_categoria,
    handle_egreso_confirmacion,
    handle_egreso_descripcion,
    handle_egreso_edit_menu,
    handle_egreso_fecha,
    handle_egreso_monto,
    handle_egreso_rec_confirmacion,
    handle_egreso_rec_edit_menu,
    handle_egreso_rec_fecha,
    handle_egreso_rec_monto,
    handle_egreso_seleccion,
    handle_gf_categoria,
    handle_gf_confirmacion,
    handle_gf_dia,
    handle_gf_monto,
    handle_gf_nombre,
)
from garay.infraestructura.telegram.handlers_freelancers import (
    EDITAR_CAMPO,
    EDITAR_CONFIRMAR,
    EDITAR_SELECCIONAR,
    EDITAR_VALOR,
    EF_CONFIRMAR,
    EF_SELECCIONAR,
    FL_CEDULA,
    FL_CONFIRMACION,
    FL_DISPLAY_OVERRIDE,
    FL_NOMBRE_COMPLETO,
    FL_NOMBRE_CORTO,
    FL_TELEGRAM_ID,
    cmd_editar_freelancer,
    cmd_eliminar_freelancer,
    cmd_listar_freelancers,
    cmd_nuevo_freelancer,
    handle_edf_activo_toggle,
    handle_edf_campo,
    handle_edf_confirmar,
    handle_edf_seleccionar,
    handle_edf_valor,
    handle_ef_confirmar,
    handle_ef_seleccionar,
    handle_fl_cedula,
    handle_fl_confirmacion,
    handle_fl_display_override,
    handle_fl_nombre_completo,
    handle_fl_nombre_corto,
    handle_fl_skip_tg,
    handle_fl_telegram_id,
)
from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_CONFIRMAR,
    GV_DETALLE,
    GV_EDIT_FECHA,
    GV_MOTIVO,
    GV_SELECCIONAR,
    cmd_gestionar_ventas,
    handle_gv_confirmar,
    handle_gv_detalle,
    handle_gv_edit_fecha,
    handle_gv_motivo,
    handle_gv_seleccionar,
)
from garay.infraestructura.telegram.handlers_propuestas import (
    GEN_EJEMPLOS,
    GEN_EMPRESA,
    GEN_PRECIO_COMMUNITY,
    GEN_PRECIO_COMPLETO,
    GEN_PRECIO_MEDIO,
    GEN_PRECIO_TRAFFICKER,
    GEN_PRECIOS,
    GEN_PRECIOS_SW,
    GEN_SELECCION,
    GEN_SW_ANUAL,
    GEN_SW_DESARROLLO,
    GEN_SW_IMPLEMENTACION,
    GEN_SW_MENSUAL,
    cmd_generar_documento,
    handle_ejemplos,
    handle_gen_continuar,
    handle_gen_empresa,
    handle_gen_precios,
    handle_gen_precios_sw,
    handle_gen_toggle,
    handle_precio_community,
    handle_precio_completo,
    handle_precio_medio,
    handle_precio_trafficker,
    handle_sw_anual,
    handle_sw_desarrollo,
    handle_sw_implementacion,
    handle_sw_mensual,
)
from garay.infraestructura.telegram.handlers_tours import (
    EDF_CAMPO,
    EDF_CONFIRMA,
    EDF_FAMILIA,
    EDF_FICHA,
    EDF_NUEVA_FAMILIA,
    EDF_TOUR,
    EDH_AGREGAR,
    EDH_LISTA,
    ELT_CONFIRMA,
    ELT_FAMILIA,
    ELT_TOUR,
    NVT_CONFIRMA,
    NVT_DUP_CONFIRMA,
    NVT_FAMILIA,
    NVT_HOR_AGREGAR,
    NVT_HOR_LISTA,
    NVT_NETO_ADULTO,
    NVT_NETO_NINO,
    NVT_NOMBRE,
    NVT_NUEVA_FAMILIA,
    cmd_editar_tour,
    cmd_eliminar_tour,
    cmd_nuevo_tour,
    handle_edh_agregar_texto,
    handle_edh_lista,
    handle_edt_confirma,
    handle_edt_familia,
    handle_edt_ficha,
    handle_edt_nueva_familia_texto,
    handle_edt_tour,
    handle_edt_valor,
    handle_elt_confirma,
    handle_elt_familia,
    handle_elt_tour,
    handle_nvt_cancelar,
    handle_nvt_crear,
    handle_nvt_dup,
    handle_nvt_edit,
    handle_nvt_familia,
    handle_nvt_hor_agregar_texto,
    handle_nvt_hor_lista,
    handle_nvt_neto_adulto,
    handle_nvt_neto_nino,
    handle_nvt_nombre,
    handle_nvt_nueva_familia,
)
from garay.infraestructura.telegram.menu import TierComando, comandos_bot

_TEXT = filters.TEXT & ~filters.COMMAND
_CB = CallbackQueryHandler


logger = logging.getLogger(__name__)

# Colombia is UTC-5, no DST — stable year-round.
ZONA_HORARIA_OWNER = zoneinfo.ZoneInfo("America/Bogota")


def _obtener_hoy_bogota() -> datetime.date:
    """Return the current calendar date in the owner's local timezone (Bogota).

    Extracted as a named function so tests can monkeypatch it without touching
    the real time or zoneinfo machinery.
    """
    return datetime.datetime.now(ZONA_HORARIA_OWNER).date()


# Baseline menu every user sees (BotCommandScopeDefault).
# Derived from CATALOGO_COMANDOS in menu.py — the single source of truth.
_COMANDOS_FREELANCER = comandos_bot(TierComando.FREELANCER)

# Admin menu — all commands accessible to ADMIN tier.
_COMANDOS_ADMIN = comandos_bot(TierComando.ADMIN)

# Propietario menu — all 16 commands.
_COMANDOS_PROPIETARIO = comandos_bot(TierComando.PROPIETARIO)

_MENUS: dict[str, list[BotCommand]] = {
    "propietario": _COMANDOS_PROPIETARIO,
    "admin": _COMANDOS_ADMIN,
}


def _parsear_ids(ids_str: str) -> set[int]:
    """Parse a comma-separated string of Telegram ids into a set of ints.

    Non-numeric tokens are skipped so a misconfigured env var never crashes startup.
    """
    ids: set[int] = set()
    for token in ids_str.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            logger.warning("ID de Telegram inválido en config, ignorado: %r", token)
    return ids


def asignar_menus(
    propietario_ids: set[int],
    dev_ids: set[int],
    admin_ids: set[int],
) -> dict[int, str]:
    """Resolve which per-chat menu each Telegram id should receive.

    Pure function — takes/returns plain ints and strings, no PTB types.

    Propietario and dev both get the ``"propietario"`` menu and OVERRIDE
    ``"admin"`` (an id that is propietario/dev AND admin stays propietario).
    Admins that are neither propietario nor dev get the ``"admin"`` menu.
    Everyone else is absent (they see the default freelancer menu).
    """
    full = propietario_ids | dev_ids
    resultado: dict[int, str] = {uid: "propietario" for uid in full}
    for uid in admin_ids - full:
        resultado[uid] = "admin"
    return resultado


async def _job_monitor_infraestructura(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily job: check due alerts and notify each owner via DM.

    Handles two independent monitors:
    1. Domain-renewal monitor (``monitor_infra_service``) — existing behaviour.
    2. Resend quota monitor (``monitor_cuota_resend_service``) — optional; skipped
       silently when the key is absent from ``bot_data``.

    Reads ``notificador`` from ``bot_data``.
    Missing ``monitor_infra_service`` or ``notificador`` → log error and return.
    Per-recipient delivery errors are caught, logged, and do not abort remaining sends.
    """
    servicio: MonitorServiciosInfraestructuraService | None = context.bot_data.get(
        "monitor_infra_service"
    )
    notificador = context.bot_data.get("notificador")

    if servicio is None or notificador is None:
        logger.error(
            "monitor: monitor_infra_service or notificador missing from bot_data — skipping"
        )
        return

    hoy = _obtener_hoy_bogota()

    destinatario_ids_str: str = context.bot_data.get("monitor_infra_telegram_ids", "")
    destinatario_ids = _parsear_ids(destinatario_ids_str)

    # --- Domain-renewal alerts ---
    avisos = servicio.avisos_para(hoy)
    for aviso in avisos:
        mensaje = construir_alerta_renovacion(
            nombre=aviso.servicio.nombre,
            dias=aviso.banda,
            fecha=aviso.servicio.fecha_renovacion,
        )
        for uid in destinatario_ids:
            try:
                await asyncio.to_thread(notificador.notificar, mensaje, str(uid))
            except Exception:
                logger.exception(
                    "monitor: failed to send renewal alert for service %r to chat %s",
                    aviso.servicio.nombre,
                    uid,
                )

    # --- Resend quota alerts (optional) ---
    cuota_service: MonitorCuotaResendService | None = context.bot_data.get(
        "monitor_cuota_resend_service"
    )
    if cuota_service is not None:
        avisos_cuota: list[AvisoCuota] = []
        try:
            avisos_cuota = await asyncio.to_thread(cuota_service.avisos_para, hoy)
        except Exception:
            logger.exception(
                "monitor: failed to compute Resend quota alerts — skipping this run"
            )
        for aviso_cuota in avisos_cuota:
            mensaje_cuota = construir_alerta_cuota(
                tipo=aviso_cuota.tipo,
                conteo=aviso_cuota.conteo,
                cap=aviso_cuota.cap,
                umbral=aviso_cuota.umbral,
            )
            for uid in destinatario_ids:
                try:
                    await asyncio.to_thread(notificador.notificar, mensaje_cuota, str(uid))
                except Exception:
                    logger.exception(
                        "monitor: failed to send quota alert (tipo=%r) to chat %s",
                        aviso_cuota.tipo,
                        uid,
                    )

    # --- Railway cost alerts (optional) ---
    railway_service: MonitorCostoRailwayService | None = context.bot_data.get(
        "monitor_costo_railway_service"
    )
    if railway_service is not None:
        avisos_railway: list[AvisoCostoRailway] = []
        try:
            avisos_railway = await asyncio.to_thread(railway_service.avisos_para, hoy)
        except Exception:
            logger.exception(
                "monitor: failed to compute Railway cost alerts — skipping this run"
            )
        for aviso_railway in avisos_railway:
            mensaje_railway = construir_alerta_costo_railway(
                costo_actual=aviso_railway.costo_actual,
                umbral=aviso_railway.umbral,
                estimado_factura=aviso_railway.estimado_factura,
            )
            for uid in destinatario_ids:
                try:
                    await asyncio.to_thread(notificador.notificar, mensaje_railway, str(uid))
                except Exception:
                    logger.exception(
                        "monitor: failed to send railway cost alert to chat %s",
                        uid,
                    )


async def _post_init(app: Application) -> None:  # type: ignore[type-arg]
    settings = obtener_settings()
    propietario_ids = _parsear_ids(settings.propietario_telegram_ids)
    dev_ids = _parsear_ids(settings.dev_telegram_ids)

    admin_ids: set[int] = set()
    repo: FreelancerRepository | None = app.bot_data.get("freelancer_repo")
    if repo is not None:
        # Repo is synchronous — offload so the event loop is never blocked.
        activos = await asyncio.to_thread(repo.listar_activos)
        admin_ids = {
            f.telegram_user_id
            for f in activos
            if f.es_admin and f.telegram_user_id is not None
        }
    else:
        logger.error("freelancer_repo not found in bot_data — admin menus skipped")

    menus = asignar_menus(
        propietario_ids=propietario_ids,
        dev_ids=dev_ids,
        admin_ids=admin_ids,
    )

    # Baseline everyone sees.
    await app.bot.set_my_commands(_COMANDOS_FREELANCER, scope=BotCommandScopeDefault())

    for uid, menu in menus.items():
        try:
            await app.bot.set_my_commands(
                _MENUS.get(menu, _COMANDOS_FREELANCER),
                scope=BotCommandScopeChat(chat_id=uid),
            )
        except TelegramError as exc:
            # Expected: BadRequest "chat not found" for a configured user who never
            # started a chat with the bot. Not a crash — log a plain warning (no
            # traceback, so this expected condition never looks like a failure or
            # buries real errors) and continue.
            logger.warning(
                "No se pudo fijar el menú para chat %s (¿el usuario inició el bot?): %s",
                uid,
                exc,
            )

    # Register the daily monitor job when at least one monitor is active:
    # - domain-renewal monitor has services configured, OR
    # - Resend quota monitor is present (quota-only owners still need the job).
    monitor_service: MonitorServiciosInfraestructuraService | None = app.bot_data.get(
        "monitor_infra_service"
    )
    cuota_monitor: MonitorCuotaResendService | None = app.bot_data.get(
        "monitor_cuota_resend_service"
    )
    railway_monitor: MonitorCostoRailwayService | None = app.bot_data.get(
        "monitor_costo_railway_service"
    )
    domain_active = monitor_service is not None and monitor_service.has_services
    quota_active = cuota_monitor is not None
    railway_active = railway_monitor is not None
    if (domain_active or quota_active or railway_active) and app.job_queue is not None:
        app.job_queue.run_daily(
            _job_monitor_infraestructura,
            time=datetime.time(hour=8, minute=0, tzinfo=ZONA_HORARIA_OWNER),
            name="monitor_servicios_infra",
        )
    else:
        logger.info(
            "monitor: no monitors configured — daily job not registered"
        )


def crear_aplicacion(token: str) -> Application:  # type: ignore[type-arg]
    """Build and return the configured PTB Application."""
    app = Application.builder().token(token).post_init(_post_init).build()

    estados = ESTADO_PTB

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CommandHandler("nueva_venta", handle_iniciar_venta),
            CallbackQueryHandler(handle_iniciar_venta, pattern="^iniciar_venta$"),
        ],
        states={
            estados[EstadoFSM.METODO_INPUT]: [
                _CB(handle_metodo_input),
                MessageHandler(_TEXT, handle_metodo_input),
            ],
            estados[EstadoFSM.ESPERANDO_FOTO]: [
                MessageHandler(filters.PHOTO, cmd_foto),
                MessageHandler(filters.Document.IMAGE, cmd_foto),
                MessageHandler(_TEXT, handle_esperando_foto),
            ],
            estados[EstadoFSM.MODALIDAD_VENTA]: [
                _CB(handle_modalidad_venta),
                MessageHandler(_TEXT, handle_modalidad_venta),
            ],
            estados[EstadoFSM.TIPO_RESERVA]: [
                _CB(handle_tipo_reserva),
                MessageHandler(_TEXT, handle_tipo_reserva),
            ],
            estados[EstadoFSM.CANAL_ORIGEN]: [
                _CB(handle_canal_origen),
                MessageHandler(_TEXT, handle_canal_origen),
            ],
            estados[EstadoFSM.PUNTO_DE_VENTA]: [
                _CB(handle_punto_de_venta),
                MessageHandler(_TEXT, handle_punto_de_venta),
            ],
            estados[EstadoFSM.FAMILIA]: [
                _CB(handle_familia),
            ],
            estados[EstadoFSM.SERVICIO_EN_FAMILIA]: [
                _CB(handle_servicio_en_familia),
            ],
            estados[EstadoFSM.DESTINO]: [
                _CB(handle_destino),
                MessageHandler(_TEXT, handle_destino),
            ],
            estados[EstadoFSM.CLIENTE_NOMBRE]: [
                MessageHandler(_TEXT, handle_cliente_nombre),
            ],
            estados[EstadoFSM.CLIENTE_TELEFONO]: [
                MessageHandler(_TEXT, handle_cliente_telefono),
            ],
            estados[EstadoFSM.CLIENTE_EMAIL]: [
                MessageHandler(_TEXT, handle_cliente_email),
            ],
            estados[EstadoFSM.FACTURA_IDIOMA]: [
                _CB(handle_factura_idioma),
                MessageHandler(_TEXT, handle_factura_idioma),
            ],
            estados[EstadoFSM.CLIENTE_TIPO_ID]: [
                _CB(handle_cliente_tipo_id),
                MessageHandler(_TEXT, handle_cliente_tipo_id),
            ],
            estados[EstadoFSM.CLIENTE_IDENTIFICACION]: [
                MessageHandler(_TEXT, handle_cliente_identificacion),
            ],
            estados[EstadoFSM.CLIENTE_HOTEL]: [
                MessageHandler(_TEXT, handle_cliente_hotel),
            ],
            estados[EstadoFSM.CLIENTE_HABITACION]: [
                MessageHandler(_TEXT, handle_cliente_habitacion),
            ],
            estados[EstadoFSM.FECHA_SALIDA]: [
                MessageHandler(_TEXT, handle_fecha_salida),
            ],
            estados[EstadoFSM.HORARIO_SALIDA]: [
                CallbackQueryHandler(handle_horario_salida, pattern="^hor:"),
                MessageHandler(_TEXT, handle_horario_salida),
            ],
            estados[EstadoFSM.PAX_ADULTOS]: [
                MessageHandler(_TEXT, handle_pax_adultos),
            ],
            estados[EstadoFSM.PAX_NINOS]: [
                MessageHandler(_TEXT, handle_pax_ninos),
            ],
            estados[EstadoFSM.MONTO_VALOR]: [
                MessageHandler(_TEXT, handle_monto_valor),
            ],
            estados[EstadoFSM.MONTO_ABONO]: [
                MessageHandler(_TEXT, handle_monto_abono),
            ],
            estados[EstadoFSM.MONTO_NETO]: [
                MessageHandler(_TEXT, handle_monto_neto),
            ],
            estados[EstadoFSM.PARTICIPANTE_ROL]: [
                _CB(handle_participante_rol),
                MessageHandler(_TEXT, handle_participante_rol),
            ],
            estados[EstadoFSM.PARTICIPANTE_OTRO]: [
                CallbackQueryHandler(handle_participante_otro, pattern="^fl:"),
                MessageHandler(_TEXT, handle_participante_otro),
            ],
            estados[EstadoFSM.CONFIRMACION]: [
                _CB(handle_confirmacion),
                MessageHandler(_TEXT, handle_confirmacion),
            ],
            estados[EstadoFSM.OTRO_TOUR]: [
                _CB(handle_otro_tour),
                MessageHandler(_TEXT, handle_otro_tour),
            ],
            estados[EstadoFSM.EDITAR_SELECTOR]: [
                _CB(handle_editar_selector),
                MessageHandler(_TEXT, handle_editar_selector),
            ],
            estados[EstadoFSM.EDITAR_VENDEDOR]: [
                CallbackQueryHandler(handle_editar_vendedor, pattern="^fl:"),
                MessageHandler(_TEXT, handle_editar_vendedor),
            ],
            estados[EstadoFSM.EDITAR_CERRADOR]: [
                CallbackQueryHandler(handle_editar_cerrador, pattern="^fl:"),
                MessageHandler(_TEXT, handle_editar_cerrador),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
            MessageHandler(filters.PHOTO | filters.Document.IMAGE, _foto_en_conversacion),
        ],
        allow_reentry=True,
    )

    # /nuevo_egreso conversation handler
    egreso_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nuevo_egreso", cmd_nuevo_egreso)],
        states={
            EGRESO_SELECCION: [_CB(handle_egreso_seleccion)],
            EGRESO_MONTO: [MessageHandler(_TEXT, handle_egreso_monto)],
            EGRESO_DESCRIPCION: [MessageHandler(_TEXT, handle_egreso_descripcion)],
            EGRESO_CATEGORIA: [
                _CB(handle_egreso_categoria),
                MessageHandler(_TEXT, handle_egreso_categoria),
            ],
            EGRESO_FECHA: [
                _CB(handle_egreso_fecha, pattern=f"^{CB_HOY}$"),
                MessageHandler(_TEXT, handle_egreso_fecha),
            ],
            EGRESO_CONFIRMACION: [_CB(handle_egreso_confirmacion)],
            EGRESO_EDIT_MENU: [
                _CB(
                    handle_egreso_edit_menu,
                    pattern=f"^({CB_EDIT_MONTO}|{CB_EDIT_DESCRIPCION}|{CB_EDIT_CATEGORIA}|{CB_EDIT_FECHA}|{CB_EDIT_VOLVER})$",
                ),
            ],
            EGRESO_REC_MONTO: [
                _CB(handle_egreso_rec_monto, pattern=f"^{CB_USAR_SUGERIDO}$"),
                MessageHandler(_TEXT, handle_egreso_rec_monto),
            ],
            EGRESO_REC_FECHA: [
                _CB(handle_egreso_rec_fecha, pattern=f"^{CB_HOY}$"),
                MessageHandler(_TEXT, handle_egreso_rec_fecha),
            ],
            EGRESO_REC_CONFIRM: [_CB(handle_egreso_rec_confirmacion)],
            EGRESO_REC_EDIT_MENU: [
                _CB(
                    handle_egreso_rec_edit_menu,
                    pattern=f"^({CB_EDIT_MONTO}|{CB_EDIT_FECHA}|{CB_EDIT_VOLVER})$",
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    # /gastos_fijos (new gasto fijo) conversation handler
    gastos_fijos_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_gf_nombre, pattern="^nuevo_gasto_fijo$"),
        ],
        states={
            GF_NOMBRE: [MessageHandler(_TEXT, handle_gf_nombre)],
            GF_MONTO: [MessageHandler(_TEXT, handle_gf_monto)],
            GF_CATEGORIA: [
                _CB(handle_gf_categoria),
                MessageHandler(_TEXT, handle_gf_categoria),
            ],
            GF_DIA: [MessageHandler(_TEXT, handle_gf_dia)],
            GF_CONFIRMACION: [_CB(handle_gf_confirmacion)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    nuevo_freelancer_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nuevo_freelancer", cmd_nuevo_freelancer)],
        states={
            FL_NOMBRE_COMPLETO: [MessageHandler(_TEXT, handle_fl_nombre_completo)],
            FL_CEDULA: [MessageHandler(_TEXT, handle_fl_cedula)],
            FL_NOMBRE_CORTO: [MessageHandler(_TEXT, handle_fl_nombre_corto)],
            FL_DISPLAY_OVERRIDE: [MessageHandler(_TEXT, handle_fl_display_override)],
            FL_TELEGRAM_ID: [
                MessageHandler(_TEXT, handle_fl_telegram_id),
                _CB(handle_fl_skip_tg, pattern="^fl_skip_tg$"),
            ],
            FL_CONFIRMACION: [_CB(handle_fl_confirmacion)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    eliminar_freelancer_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("eliminar_freelancer", cmd_eliminar_freelancer)],
        states={
            EF_SELECCIONAR: [_CB(handle_ef_seleccionar)],
            EF_CONFIRMAR: [_CB(handle_ef_confirmar)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    editar_freelancer_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("editar_freelancer", cmd_editar_freelancer)],
        states={
            EDITAR_SELECCIONAR: [_CB(handle_edf_seleccionar, pattern="^edf_sel:")],
            EDITAR_CAMPO: [
                _CB(handle_edf_campo, pattern="^edf_campo:"),
                _CB(handle_edf_campo, pattern="^edf_listo$"),
            ],
            EDITAR_VALOR: [
                MessageHandler(_TEXT, handle_edf_valor),
                _CB(handle_edf_valor, pattern="^edf_tg_none$"),
            ],
            EDITAR_CONFIRMAR: [
                _CB(handle_edf_activo_toggle, pattern="^edf_activo:"),
                _CB(handle_edf_confirmar, pattern="^edf_(confirmar|cancelar)$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    gestionar_ventas_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("gestionar_ventas", cmd_gestionar_ventas)],
        states={
            GV_SELECCIONAR: [_CB(handle_gv_seleccionar, pattern="^gv_sel:")],
            GV_DETALLE: [_CB(handle_gv_detalle, pattern="^gv_(anular|editar|cancelar)$")],
            GV_MOTIVO: [MessageHandler(_TEXT, handle_gv_motivo)],
            GV_CONFIRMAR: [_CB(handle_gv_confirmar, pattern="^gv_(confirmar|cancelar)$")],
            GV_EDIT_FECHA: [MessageHandler(_TEXT, handle_gv_edit_fecha)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    editar_tour_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("editar_tour", cmd_editar_tour)],
        states={
            EDF_FAMILIA: [
                _CB(handle_edt_familia, pattern="^edt_familia:"),
                _CB(handle_edt_familia, pattern="^edt_familia_nueva:"),
                _CB(handle_edt_familia, pattern="^edt_familia_nueva_libre$"),
            ],
            EDF_TOUR: [_CB(handle_edt_tour, pattern="^edt_tour:")],
            EDF_FICHA: [
                _CB(handle_edt_ficha, pattern="^edt_campo:"),
                _CB(handle_edt_ficha, pattern="^edt_listo$"),
            ],
            EDF_CAMPO: [
                MessageHandler(_TEXT, handle_edt_valor),
            ],
            EDF_NUEVA_FAMILIA: [
                MessageHandler(_TEXT, handle_edt_nueva_familia_texto),
            ],
            EDF_CONFIRMA: [
                _CB(handle_edt_confirma, pattern="^edt_(confirmar|cancelar)$"),
            ],
            EDH_LISTA: [
                _CB(handle_edh_lista, pattern="^edh_agregar$"),
                _CB(handle_edh_lista, pattern="^edh_quitar:"),
                _CB(handle_edh_lista, pattern="^edh_listo$"),
            ],
            EDH_AGREGAR: [
                MessageHandler(_TEXT, handle_edh_agregar_texto),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    eliminar_tour_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("eliminar_tour", cmd_eliminar_tour)],
        states={
            ELT_FAMILIA: [_CB(handle_elt_familia, pattern="^elt_familia:")],
            ELT_TOUR: [_CB(handle_elt_tour, pattern="^elt_tour:")],
            ELT_CONFIRMA: [_CB(handle_elt_confirma, pattern="^elt_(confirmar|cancelar)$")],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    nuevo_tour_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nuevo_tour", cmd_nuevo_tour)],
        states={
            NVT_FAMILIA: [
                _CB(handle_nvt_familia, pattern="^nvt_familia:"),
                _CB(handle_nvt_familia, pattern="^nvt_familia_nueva_libre$"),
            ],
            NVT_NUEVA_FAMILIA: [
                MessageHandler(_TEXT, handle_nvt_nueva_familia),
            ],
            NVT_NOMBRE: [
                MessageHandler(_TEXT, handle_nvt_nombre),
            ],
            NVT_NETO_ADULTO: [
                MessageHandler(_TEXT, handle_nvt_neto_adulto),
                _CB(handle_nvt_neto_adulto, pattern="^nvt_saltar_neto_adulto$"),
            ],
            NVT_NETO_NINO: [
                MessageHandler(_TEXT, handle_nvt_neto_nino),
                _CB(handle_nvt_neto_nino, pattern="^nvt_saltar_neto_nino$"),
            ],
            NVT_CONFIRMA: [
                _CB(handle_nvt_edit, pattern="^nvt_edit:"),
                _CB(handle_nvt_crear, pattern="^nvt_crear$"),
                _CB(handle_nvt_cancelar, pattern="^nvt_cancelar$"),
            ],
            NVT_DUP_CONFIRMA: [
                _CB(handle_nvt_dup, pattern="^nvt_dup:(usar|cambiar)$"),
            ],
            NVT_HOR_LISTA: [
                _CB(handle_nvt_hor_lista, pattern="^nvt_hor_agregar$"),
                _CB(handle_nvt_hor_lista, pattern="^nvt_hor_quitar:"),
                _CB(handle_nvt_hor_lista, pattern="^nvt_hor_listo$"),
            ],
            NVT_HOR_AGREGAR: [
                MessageHandler(_TEXT, handle_nvt_hor_agregar_texto),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    # /generar_documento (dev-only) — multi-select proposal/contract generator
    propuesta_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("generar_documento", cmd_generar_documento)],
        states={
            GEN_SELECCION: [
                _CB(handle_gen_toggle, pattern="^gen_toggle:"),
                _CB(handle_gen_continuar, pattern="^gen_continuar$"),
            ],
            GEN_EMPRESA: [MessageHandler(_TEXT, handle_gen_empresa)],
            GEN_EJEMPLOS: [MessageHandler(_TEXT, handle_ejemplos)],
            GEN_PRECIOS: [_CB(handle_gen_precios, pattern="^gen_precios:")],
            GEN_PRECIO_COMPLETO: [MessageHandler(_TEXT, handle_precio_completo)],
            GEN_PRECIO_MEDIO: [MessageHandler(_TEXT, handle_precio_medio)],
            GEN_PRECIO_COMMUNITY: [MessageHandler(_TEXT, handle_precio_community)],
            GEN_PRECIO_TRAFFICKER: [MessageHandler(_TEXT, handle_precio_trafficker)],
            GEN_PRECIOS_SW: [_CB(handle_gen_precios_sw, pattern="^gen_precios:")],
            GEN_SW_DESARROLLO: [MessageHandler(_TEXT, handle_sw_desarrollo)],
            GEN_SW_IMPLEMENTACION: [MessageHandler(_TEXT, handle_sw_implementacion)],
            GEN_SW_MENSUAL: [MessageHandler(_TEXT, handle_sw_mensual)],
            GEN_SW_ANUAL: [MessageHandler(_TEXT, handle_sw_anual)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CommandHandler("start", cmd_start),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(egreso_conv_handler, group=2)
    app.add_handler(gastos_fijos_conv_handler, group=3)
    app.add_handler(nuevo_freelancer_conv_handler, group=5)
    app.add_handler(eliminar_freelancer_conv_handler, group=5)
    app.add_handler(editar_freelancer_conv_handler, group=6)
    app.add_handler(gestionar_ventas_conv_handler, group=7)
    app.add_handler(editar_tour_conv_handler, group=8)
    app.add_handler(eliminar_tour_conv_handler, group=8)
    app.add_handler(nuevo_tour_conv_handler, group=8)
    app.add_handler(propuesta_conv_handler, group=9)
    app.add_handler(CommandHandler("listar_freelancers", cmd_listar_freelancers), group=1)
    app.add_handler(CommandHandler("mis_ventas", cmd_mis_ventas), group=1)
    app.add_handler(CommandHandler("verificar_pago", cmd_verificar_pago), group=1)
    app.add_handler(CommandHandler("gastos_fijos", cmd_gastos_fijos), group=1)
    app.add_handler(CommandHandler("help", cmd_help), group=1)
    app.add_handler(CommandHandler("cancelar", cmd_cancelar_sin_conv), group=99)
    handlers_reportes.registrar_handlers(app)
    handlers_conciliacion.registrar_handlers(app)
    return app
