"""Mapping from FSM states to PTB integer constants."""

from __future__ import annotations

from garay.aplicacion.tiquetera.fsm import EstadoFSM

# PTB ConversationHandler requires integer states
ESTADO_PTB: dict[EstadoFSM, int] = {
    EstadoFSM.METODO_INPUT: 20,
    EstadoFSM.ESPERANDO_FOTO: 22,
    EstadoFSM.TIPO_RESERVA: 0,
    EstadoFSM.CANAL_ORIGEN: 28,
    EstadoFSM.PUNTO_DE_VENTA: 1,
    EstadoFSM.FAMILIA: 10,
    EstadoFSM.SERVICIO_EN_FAMILIA: 14,
    EstadoFSM.DESTINO: 2,
    EstadoFSM.CLIENTE_NOMBRE: 3,
    EstadoFSM.CLIENTE_TELEFONO: 4,
    EstadoFSM.CLIENTE_HOTEL: 5,
    EstadoFSM.CLIENTE_HABITACION: 6,
    EstadoFSM.FECHA_SALIDA: 7,
    EstadoFSM.PAX_ADULTOS: 8,
    EstadoFSM.PAX_NINOS: 9,
    EstadoFSM.MONTO_VALOR: 11,
    EstadoFSM.MONTO_ABONO: 12,
    EstadoFSM.MONTO_NETO: 13,
    EstadoFSM.PARTICIPANTE_ROL: 15,
    EstadoFSM.PARTICIPANTE_OTRO: 16,
    EstadoFSM.CONFIRMACION: 17,
    EstadoFSM.EDITAR_SELECTOR: 21,
    EstadoFSM.EDITAR_VENDEDOR: 23,
    EstadoFSM.EDITAR_CERRADOR: 24,
    EstadoFSM.CLIENTE_EMAIL: 25,
    EstadoFSM.CLIENTE_TIPO_ID: 26,
    EstadoFSM.CLIENTE_IDENTIFICACION: 27,
    EstadoFSM.TERMINADO: 18,
    EstadoFSM.CANCELADO: 19,
}
