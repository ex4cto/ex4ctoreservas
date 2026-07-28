"""Catalogo centralizado de textos de usuario.

Todos los textos que ve el usuario viven aca, indexados por clave e idioma. Agregar un
idioma es agregar entradas: el codigo que consume mensajes no cambia (i18n-ready).
"""

from __future__ import annotations

from enum import StrEnum

from garay.dominio.comun.errores import ErrorDeConfiguracion


class Idioma(StrEnum):
    """Idiomas soportados por el catalogo de mensajes."""

    ES = "es"


_CATALOGO: dict[str, dict[Idioma, str]] = {
    "bienvenida": {Idioma.ES: "Bienvenido a Garay Tours."},
    "venta_registrada": {Idioma.ES: "Venta registrada correctamente."},
    "error_generico": {Idioma.ES: "Ocurrio un error. Intenta de nuevo."},
    "pregunta_tipo_reserva": {
        Idioma.ES: "¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO, DIGITAL"
    },
    "pregunta_punto_de_venta": {Idioma.ES: "¿Cuál es el punto de venta?"},
    "pregunta_destino": {Idioma.ES: "Seleccioná los destinos (podés elegir varios):"},
    "pregunta_cliente_nombre": {Idioma.ES: "¿Cuál es el nombre del cliente?"},
    "pregunta_cliente_telefono": {Idioma.ES: "¿Cuál es el teléfono del cliente?"},
    "pregunta_cliente_hotel": {
        Idioma.ES: "¿En qué hotel está hospedado el cliente? (escribí 'no' si no aplica)"
    },
    "pregunta_cliente_habitacion": {Idioma.ES: "¿Cuál es el número de habitación?"},
    "pregunta_fecha_salida": {
        Idioma.ES: "¿Cuál es la fecha de salida? (DD/MM, DD/MM/YY o DD/MM/YYYY)"
    },
    "pregunta_adultos": {Idioma.ES: "¿Cuántos adultos? (mínimo 1)"},
    "pregunta_ninos": {Idioma.ES: "¿Cuántos niños? (puede ser 0)"},
    "pregunta_numero_ticket": {Idioma.ES: "¿Cuál es el número de ticket?"},
    "pregunta_valor": {Idioma.ES: "¿Cuál es el valor total de la venta?"},
    "pregunta_abono": {Idioma.ES: "¿Cuánto abonó el cliente? (0 si no hubo abono)"},
    "pregunta_neto": {Idioma.ES: "¿Cuál es el monto neto?"},
    "pregunta_participante_nombre": {Idioma.ES: "¿Cuál es tu nombre (quien registra la venta)?"},
    "pregunta_rol": {
        Idioma.ES: "¿Cuál es tu rol en esta venta?\nOpciones: Solo vendedor, Solo cerrador, Ambos"
    },
    "pregunta_participante_otro_vendedor": {Idioma.ES: "¿Cuál es el nombre del vendedor?"},
    "pregunta_participante_otro_cerrador": {Idioma.ES: "¿Cuál es el nombre del cerrador?"},
    "error_fecha_invalida": {
        Idioma.ES: "Fecha inválida. Usá el formato DD/MM, DD/MM/YY o DD/MM/YYYY."
    },
    "pregunta_enviar_foto": {
        Idioma.ES: "Enviá la foto del tiquet para extraer los datos automáticamente."
    },
    "error_metodo_invalido": {Idioma.ES: "Opción inválida. Elegí Manual o Foto."},
    "error_esperando_foto_texto": {
        Idioma.ES: "Necesito la foto del tiquet, no texto. Enviá la imagen para continuar."
    },
    "error_numero_invalido": {Idioma.ES: "Número inválido. Ingresá un entero positivo."},
    "error_monto_invalido": {
        Idioma.ES: "Monto inválido. Ingresá un valor positivo (ej: 500000 o 500.000)."
    },
    "error_neto_supera_valor": {Idioma.ES: "El neto no puede superar el valor total de la venta."},
    "error_sin_destino": {Idioma.ES: "Tenés que seleccionar al menos un destino."},
    "venta_cancelada": {Idioma.ES: "Operación cancelada. Escribí /start para comenzar de nuevo."},
    "confirmacion_resumen": {
        Idioma.ES: (
            "📋 *Resumen de la venta:*\n"
            "Tipo: {tipo}\n"
            "Punto de venta: {punto_de_venta}\n"
            "Destinos: {destinos}\n"
            "Cliente: {cliente_nombre}\n"
            "Teléfono: {cliente_telefono}\n"
            "Hotel: {cliente_hotel}\n"
            "Habitación: {cliente_habitacion}\n"
            "Fecha salida: {fecha_salida}\n"
            "Adultos: {adultos} | Niños: {ninos}\n"
            "Ticket #: {numero_ticket}\n"
            "Valor: {valor}\n"
            "Abono: {abono}\n"
            "Neto: {neto}\n"
            "Registrado por: {participante_nombre} ({participante_rol})\n"
            "Otro participante: {participante_otro}\n\n"
            "¿Confirmamos?"
        )
    },
    "pregunta_metodo_input": {
        Idioma.ES: (
            "¿Cómo querés registrar la venta?\n\n"
            "_Podés modificar cualquier dato en el resumen antes de confirmar._"
        )
    },
    "pregunta_destino_numero": {
        Idioma.ES: (
            "Ingresá el número del tour "
            "(podés poner varios separados por coma, ej: *15* o *15, 23*)."
        )
    },
    "info_sin_tours_seleccionados": {
        Idioma.ES: "Aún no seleccionaste ningún tour."
    },
    "error_tipo_reserva_invalido": {
        Idioma.ES: "Opción inválida. Elegí INTERNO, EXTERNO o DIGITAL."
    },
    "error_sin_destino_numero": {
        Idioma.ES: "Tenés que ingresar al menos un número de tour."
    },
    "error_adultos_invalido": {
        Idioma.ES: "Número inválido. Ingresá un entero mayor a 0."
    },
    "error_adultos_minimo": {Idioma.ES: "Debe haber al menos 1 adulto."},
    "error_ninos_invalido": {
        Idioma.ES: "Número inválido. Ingresá un entero >= 0."
    },
    "error_ninos_negativo": {
        Idioma.ES: "El número de niños no puede ser negativo."
    },
    "error_abono_invalido": {
        Idioma.ES: "Monto inválido. Ingresá 0 si no hubo abono."
    },
    "pregunta_rol_venta": {Idioma.ES: "¿Cuál fue tu rol en esta venta?"},
    "pregunta_neto_sin_precio": {
        Idioma.ES: (
            "¿Cuál es el monto neto? "
            "(no se encontró precio en el catálogo para algún tour seleccionado)"
        )
    },
    "error_neto_invalido": {
        Idioma.ES: "Monto inválido. Ingresá un número >= 0."
    },
    "error_rol_invalido": {
        Idioma.ES: "Opción inválida. Elegí: Ambos, Solo vendedor, o Solo cerrador."
    },
    "error_interno_rol_no_definido": {
        Idioma.ES: (
            "Error interno: rol no definido. Escribí /cancelar y comenzá de nuevo."
        )
    },
    "confirmacion_venta_exitosa": {Idioma.ES: "¡Venta registrada con éxito!"},
    "pregunta_campo_editar": {Idioma.ES: "¿Qué campo querés modificar?"},
    "error_campo_editar_invalido": {
        Idioma.ES: "Opción inválida. Elegí uno de los campos."
    },
    "error_estado_no_manejable": {Idioma.ES: "Estado no manejable."},
}


def obtener_mensaje(clave: str, idioma: Idioma = Idioma.ES) -> str:
    """Devuelve el texto para ``clave`` en ``idioma``.

    Lanza :class:`ErrorDeConfiguracion` si la combinacion no existe.
    """
    try:
        return _CATALOGO[clave][idioma]
    except KeyError as exc:
        raise ErrorDeConfiguracion(
            f"Mensaje no encontrado: clave={clave!r}, idioma={idioma.value!r}."
        ) from exc
