"""Mapping from FSM states to PTB integer constants."""
from __future__ import annotations

from garay.aplicacion.tiquetera.fsm import EstadoFSM

# PTB ConversationHandler requires integer states
ESTADO_PTB: dict[EstadoFSM, int] = {
    EstadoFSM.TIPO_RESERVA: 0,
    EstadoFSM.PUNTO_DE_VENTA: 1,
    EstadoFSM.DESTINO: 2,
    EstadoFSM.CLIENTE_NOMBRE: 3,
    EstadoFSM.CLIENTE_TELEFONO: 4,
    EstadoFSM.CLIENTE_HOTEL: 5,
    EstadoFSM.CLIENTE_HABITACION: 6,
    EstadoFSM.FECHA_SALIDA: 7,
    EstadoFSM.PAX_ADULTOS: 8,
    EstadoFSM.PAX_NINOS: 9,
    EstadoFSM.NUMERO_TICKET: 10,
    EstadoFSM.MONTO_VALOR: 11,
    EstadoFSM.MONTO_ABONO: 12,
    EstadoFSM.MONTO_NETO: 13,
    EstadoFSM.PARTICIPANTE_ROL: 15,
    EstadoFSM.PARTICIPANTE_OTRO: 16,
    EstadoFSM.CONFIRMACION: 17,
    EstadoFSM.TERMINADO: 18,
    EstadoFSM.CANCELADO: 19,
}
