"""Build and return the PTB Application."""

from __future__ import annotations

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from garay.aplicacion.tiquetera.fsm import EstadoFSM
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.infraestructura.telegram.handlers import (
    _foto_en_conversacion,
    cmd_cancelar,
    cmd_foto,
    cmd_mis_ventas,
    cmd_resumen_empresa,
    cmd_start,
    cmd_verificar_pago,
    handle_cliente_habitacion,
    handle_cliente_hotel,
    handle_cliente_nombre,
    handle_cliente_telefono,
    handle_confirmacion,
    handle_destino,
    handle_editar_cerrador,
    handle_editar_selector,
    handle_editar_vendedor,
    handle_esperando_foto,
    handle_fecha_salida,
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

_TEXT = filters.TEXT & ~filters.COMMAND
_CB = CallbackQueryHandler


def crear_aplicacion(token: str) -> Application:  # type: ignore[type-arg]
    """Build and return the configured PTB Application."""
    app = Application.builder().token(token).build()

    estados = ESTADO_PTB

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
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

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("mis_ventas", cmd_mis_ventas), group=1)
    app.add_handler(CommandHandler("resumen_empresa", cmd_resumen_empresa), group=1)
    app.add_handler(CommandHandler("verificar_pago", cmd_verificar_pago), group=1)
    return app
