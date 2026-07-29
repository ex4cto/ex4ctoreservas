"""Build and return the PTB Application."""

from __future__ import annotations

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.tiquetera.fsm import EstadoFSM
from garay.infraestructura.telegram import handlers_reportes
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.infraestructura.telegram.handlers import (
    _foto_en_conversacion,
    cmd_cancelar,
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

_TEXT = filters.TEXT & ~filters.COMMAND
_CB = CallbackQueryHandler


_COMANDOS = [
    BotCommand("nueva_venta", "Registrar una venta"),
    BotCommand("verificar_pago", "Pagos recibidos (últimos 5 min)"),
    BotCommand("mis_ventas", "Mis ventas del período"),
    BotCommand("dashboard_ventas", "Dashboard de ventas (solo admin)"),
    BotCommand("flujo_caja", "Flujo de caja mensual (solo propietario)"),
    BotCommand("nuevo_egreso", "Registrar un egreso manual"),
    BotCommand("gastos_fijos", "Ver y gestionar gastos fijos"),
    BotCommand("generar_mes", "Generar gastos fijos del mes actual"),
    BotCommand("cancelar", "Cancelar operación actual"),
]


async def _post_init(app: Application) -> None:  # type: ignore[type-arg]
    await app.bot.set_my_commands(_COMANDOS)


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
                MessageHandler(_TEXT, handle_editar_vendedor),
            ],
            estados[EstadoFSM.EDITAR_CERRADOR]: [
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

    app.add_handler(conv_handler)
    app.add_handler(egreso_conv_handler, group=2)
    app.add_handler(gastos_fijos_conv_handler, group=3)
    app.add_handler(CommandHandler("mis_ventas", cmd_mis_ventas), group=1)
    app.add_handler(CommandHandler("verificar_pago", cmd_verificar_pago), group=1)
    app.add_handler(CommandHandler("gastos_fijos", cmd_gastos_fijos), group=1)
    app.add_handler(CommandHandler("generar_mes", cmd_generar_mes), group=1)
    handlers_reportes.registrar_handlers(app)
    return app
