"""Adapter: ExtractorReserva that uses an ExtractorIA port to map DatosExtraidos → ContextoVenta."""

from __future__ import annotations

import contextlib
import os
import tempfile

from garay.dominio.puertos.servicios_externos import ExtractorIA, ExtractorReserva
from garay.dominio.ventas.contexto import ContextoVenta


class ExtractorReservaFoto(ExtractorReserva):
    """Maps photo bytes → ContextoVenta by delegating to an ExtractorIA port.

    Depends on the abstract ExtractorIA port — never on a concrete implementation.
    Follows dependency inversion.
    """

    def __init__(self, extractor_ia: ExtractorIA) -> None:
        self._extractor_ia = extractor_ia

    def extraer_de_foto(self, foto_bytes: bytes) -> ContextoVenta:
        fd, ruta = tempfile.mkstemp(suffix=".jpg")
        try:
            os.write(fd, foto_bytes)
            os.close(fd)
            datos = self._extractor_ia.extraer_de_foto(ruta)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(ruta)

        return ContextoVenta(
            valor=datos.valor_venta.monto if datos.valor_venta else None,
            neto=datos.neto.monto if datos.neto else None,
            abono=datos.abono.monto if datos.abono else None,
            cliente_nombre=datos.nombre_cliente,
            cliente_telefono=datos.telefono,
            cliente_hotel=datos.cliente_hotel,
            cliente_habitacion=datos.numero_habitacion,
            vendedor_nombre=datos.servicio_nombre,
            destinos_nombres=list(datos.destinos),
            fecha_salida=datos.fecha_salida,
            adultos=datos.adultos,
            ninos=datos.ninos,
            numero_fisico=datos.numero_ticket,
        )
