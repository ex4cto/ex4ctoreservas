"""Build and return the PTB Application."""

from __future__ import annotations

import asyncio
import logging

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
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.tiquetera.fsm import EstadoFSM
from garay.config.settings import obtener_settings
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.telegram import handlers_reportes
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.infraestructura.telegram.handlers import (
    _foto_en_conversacion,
    cmd_cancelar,
    cmd_cancelar_sin_conv,
    cmd_foto,
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
    handle_familia,
    handle_fecha_salida,
    handle_iniciar_venta,
    handle_metodo_input,
    handle_monto_abono,
    handle_monto_neto,
    handle_monto_valor,
    handle_participante_otro,
    handle_participante_rol,
    handle_pax_adultos,
    handle_pax_ninos,
    handle_punto_de_venta,
    handle_servicio_en_familia,
    handle_tipo_reserva,
)
from garay.infraestructura.telegram.handlers_egresos import (
    EGRESO_CATEGORIA,
    EGRESO_CONFIRMACION,
    EGRESO_DESCRIPCION,
    EGRESO_FECHA,
    EGRESO_MONTO,
    GF_CATEGORIA,
    GF_CONFIRMACION,
    GF_DIA,
    GF_MONTO,
    GF_NOMBRE,
    cmd_gastos_fijos,
    cmd_generar_mes,
    cmd_nuevo_egreso,
    handle_egreso_categoria,
    handle_egreso_confirmacion,
    handle_egreso_descripcion,
    handle_egreso_fecha,
    handle_egreso_monto,
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

_TEXT = filters.TEXT & ~filters.COMMAND
_CB = CallbackQueryHandler


logger = logging.getLogger(__name__)


# Baseline menu every user sees (BotCommandScopeDefault).
_COMANDOS_FREELANCER = [
    BotCommand("nueva_venta", "Registrar una venta"),
    BotCommand("mis_ventas", "Mis ventas del período"),
    BotCommand("verificar_pago", "Pagos recibidos (últimos 5 min)"),
    BotCommand("cancelar", "Cancelar operación actual"),
]

# Admin menu = freelancer + admin-only commands.
_COMANDOS_ADMIN = [
    *_COMANDOS_FREELANCER,
    BotCommand("dashboard_ventas", "Dashboard de ventas (solo admin)"),
    BotCommand("listar_freelancers", "Ver freelancers registrados (solo admin)"),
    BotCommand("nuevo_freelancer", "Registrar un nuevo freelancer (solo admin)"),
    BotCommand("eliminar_freelancer", "Desactivar un freelancer (solo admin)"),
    BotCommand("editar_freelancer", "Editar un freelancer (solo admin)"),
    BotCommand("nuevo_egreso", "Registrar un egreso manual"),
    BotCommand("gastos_fijos", "Ver y gestionar gastos fijos"),
    BotCommand("generar_mes", "Generar gastos fijos del mes actual"),
]

# Propietario menu = admin + owner-only commands.
_COMANDOS_PROPIETARIO = [
    *_COMANDOS_ADMIN,
    BotCommand("flujo_caja", "Flujo de caja mensual (solo propietario)"),
    BotCommand("movimientos", "Movimientos recientes (solo propietario)"),
    BotCommand("tours", "Reporte de tours (solo propietario)"),
]

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
            MessageHandler(filters.PHOTO | filters.Document.IMAGE, _foto_en_conversacion),
        ],
    )

    # /nuevo_egreso conversation handler
    egreso_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nuevo_egreso", cmd_nuevo_egreso)],
        states={
            EGRESO_MONTO: [MessageHandler(_TEXT, handle_egreso_monto)],
            EGRESO_DESCRIPCION: [MessageHandler(_TEXT, handle_egreso_descripcion)],
            EGRESO_CATEGORIA: [
                _CB(handle_egreso_categoria),
                MessageHandler(_TEXT, handle_egreso_categoria),
            ],
            EGRESO_FECHA: [MessageHandler(_TEXT, handle_egreso_fecha)],
            EGRESO_CONFIRMACION: [_CB(handle_egreso_confirmacion)],
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
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
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
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
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
    )

    eliminar_freelancer_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("eliminar_freelancer", cmd_eliminar_freelancer)],
        states={
            EF_SELECCIONAR: [_CB(handle_ef_seleccionar)],
            EF_CONFIRMAR: [_CB(handle_ef_confirmar)],
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
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
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
    )

    app.add_handler(conv_handler)
    app.add_handler(egreso_conv_handler, group=2)
    app.add_handler(gastos_fijos_conv_handler, group=3)
    app.add_handler(nuevo_freelancer_conv_handler, group=5)
    app.add_handler(eliminar_freelancer_conv_handler, group=5)
    app.add_handler(editar_freelancer_conv_handler, group=6)
    app.add_handler(CommandHandler("listar_freelancers", cmd_listar_freelancers), group=1)
    app.add_handler(CommandHandler("mis_ventas", cmd_mis_ventas), group=1)
    app.add_handler(CommandHandler("verificar_pago", cmd_verificar_pago), group=1)
    app.add_handler(CommandHandler("gastos_fijos", cmd_gastos_fijos), group=1)
    app.add_handler(CommandHandler("generar_mes", cmd_generar_mes), group=1)
    app.add_handler(CommandHandler("cancelar", cmd_cancelar_sin_conv), group=99)
    handlers_reportes.registrar_handlers(app)
    return app
