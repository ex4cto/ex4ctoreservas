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
    "pregunta_participante_nombre": {Idioma.ES: "¿Cuál es tu nombre (quien registra la venta)?"},
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
    "venta_cancelada": {Idioma.ES: "Operación cancelada. Escribí /start para comenzar de nuevo."},
    "pregunta_canal_origen": {Idioma.ES: "¿De qué canal digital llegó el cliente?"},
    "error_canal_invalido": {Idioma.ES: "Opción inválida. Elegí uno de los canales disponibles."},
    "pregunta_editar_canal": {Idioma.ES: "Canal actual: {actual}\n¿Nuevo canal de origen?"},
    "confirmacion_resumen": {
        Idioma.ES: (
            "📋 *Resumen de la venta:*\n"
            "Tipo: {tipo}\n"
            "Canal: {canal}\n"
            "Punto de venta: {punto_de_venta}\n"
            "Destinos: {destinos}\n"
            "Cliente: {cliente_nombre}\n"
            "Teléfono: {cliente_telefono}\n"
            "Correo: {cliente_email}\n"
            "Identificación: {cliente_identificacion}\n"
            "Hotel: {cliente_hotel}\n"
            "Habitación: {cliente_habitacion}\n"
            "Fecha salida: {fecha_salida}\n"
            "Adultos: {adultos} | Niños: {ninos}\n"
            "Valor: {valor}\n"
            "Abono: {abono}\n"
            "Neto: {neto}\n"
            "Vendedor: {vendedor}\n"
            "Cerrador: {cerrador}\n\n"
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
    "info_sin_tours_seleccionados": {Idioma.ES: "Aún no seleccionaste ningún tour."},
    "error_tipo_reserva_invalido": {
        Idioma.ES: "Opción inválida. Elegí INTERNO, EXTERNO o DIGITAL."
    },
    "error_sin_destino_numero": {Idioma.ES: "Tenés que ingresar al menos un número de tour."},
    "error_adultos_invalido": {Idioma.ES: "Número inválido. Ingresá un entero mayor a 0."},
    "error_adultos_minimo": {Idioma.ES: "Debe haber al menos 1 adulto."},
    "error_ninos_invalido": {Idioma.ES: "Número inválido. Ingresá un entero >= 0."},
    "error_ninos_negativo": {Idioma.ES: "El número de niños no puede ser negativo."},
    "error_abono_invalido": {Idioma.ES: "Monto inválido. Ingresá 0 si no hubo abono."},
    "pregunta_rol_venta": {Idioma.ES: "¿Cuál fue tu rol en esta venta?"},
    "pregunta_neto_sin_precio": {
        Idioma.ES: (
            "¿Cuál es el monto neto? "
            "(no se encontró precio en el catálogo para algún tour seleccionado)"
        )
    },
    "error_neto_invalido": {Idioma.ES: "Monto inválido. Ingresá un número >= 0."},
    "error_rol_invalido": {
        Idioma.ES: "Opción inválida. Elegí: Ambos, Solo vendedor, o Solo cerrador."
    },
    "error_interno_rol_no_definido": {
        Idioma.ES: ("Error interno: rol no definido. Escribí /cancelar y comenzá de nuevo.")
    },
    "confirmacion_venta_exitosa": {Idioma.ES: "¡Venta registrada con éxito!"},
    "pregunta_campo_editar": {Idioma.ES: "¿Qué campo querés modificar?"},
    "error_campo_editar_invalido": {Idioma.ES: "Opción inválida. Elegí uno de los campos."},
    "error_estado_no_manejable": {Idioma.ES: "Estado no manejable."},
    "info_destinos_seleccionados": {
        Idioma.ES: (
            "Seleccionados: {seleccionados}\n"
            "Agregá más números o escribí *confirmar* para continuar."
        )
    },
    "info_ia_detecto_destinos": {
        Idioma.ES: ("La IA detectó: {nombres} (ingresá los números correspondientes).")
    },
    "error_destino_no_encontrado": {
        Idioma.ES: (
            "Número(s) no encontrado(s): {invalidos}. Revisá el catálogo.\n{destinos_mensaje}"
        )
    },
    "error_abono_supera_neto": {
        Idioma.ES: ("El abono ({abono}) no puede superar el neto calculado ({neto}).")
    },
    "error_neto_supera_valor_detalle": {
        Idioma.ES: (
            "El neto calculado ({neto}) supera el valor de la venta ({valor}). "
            "Ingresá un valor mayor o igual a {neto}."
        )
    },
    "error_neto_supera_valor_monto_neto": {
        Idioma.ES: "El neto ({neto}) no puede superar el valor ({valor})."
    },
    "titulo_datos_extraidos_foto": {Idioma.ES: "*Datos extraidos de la foto:*"},
    "completar_datos_faltantes": {Idioma.ES: "\nCompletemos lo que falta:"},
    "dato_extraido_nombre": {Idioma.ES: "Nombre: {valor}"},
    "dato_extraido_telefono": {Idioma.ES: "Teléfono: {valor}"},
    "dato_extraido_fecha": {Idioma.ES: "Fecha: {valor}"},
    "dato_extraido_destinos": {Idioma.ES: "Destinos: {valor}"},
    "dato_extraido_adultos": {Idioma.ES: "Adultos: {valor}"},
    "dato_extraido_ninos": {Idioma.ES: "Niños: {valor}"},
    "dato_extraido_valor": {Idioma.ES: "Valor: {valor}"},
    "dato_extraido_abono": {Idioma.ES: "Abono: {valor}"},
    "dato_extraido_ticket": {Idioma.ES: "N° ticket: {valor}"},
    "dato_extraido_hotel": {Idioma.ES: "Hotel: {valor}"},
    "dato_extraido_habitacion": {Idioma.ES: "Habitación: {valor}"},
    "dato_extraido_vendedor": {Idioma.ES: "Vendedor: {valor}"},
    "error_extraccion_no_disponible": {
        Idioma.ES: (
            "La extracción automática no está disponible. "
            "Usa /start para ingresar los datos manualmente."
        )
    },
    "error_extraccion_timeout": {
        Idioma.ES: (
            "La IA tardó demasiado en procesar la foto. "
            "Intenta de nuevo o usa /start."
        )
    },
    "error_extraccion_fallo": {
        Idioma.ES: (
            "Ocurrió un error al procesar la foto. "
            "Intenta de nuevo o usa /start."
        )
    },
    "error_datos_incompletos": {
        Idioma.ES: (
            "⚠️ Faltan datos para confirmar:\n• {campos}\n\n"
            "Edita los campos faltantes antes de confirmar."
        )
    },
    "pregunta_editar_vendedor": {
        Idioma.ES: "Vendedor actual: {actual}\n¿Nuevo nombre?"
    },
    "pregunta_editar_cerrador": {
        Idioma.ES: "Cerrador actual: {actual}\n¿Nuevo nombre?"
    },
    "pregunta_editar_cliente_nombre": {
        Idioma.ES: "Nombre actual: {actual}\n¿Nuevo nombre del cliente?"
    },
    "pregunta_editar_cliente_telefono": {
        Idioma.ES: "Teléfono actual: {actual}\n¿Nuevo teléfono?"
    },
    "pregunta_editar_cliente_hotel": {
        Idioma.ES: "Hotel actual: {actual}\n¿Nuevo hotel? (o 'sin hotel')"
    },
    "pregunta_editar_cliente_habitacion": {
        Idioma.ES: "Habitación actual: {actual}\n¿Nuevo número de habitación?"
    },
    "pregunta_editar_fecha_salida": {
        Idioma.ES: "Fecha actual: {actual}\n¿Nueva fecha? (DD/MM o DD/MM/YYYY HH:MM)"
    },
    "pregunta_editar_adultos_ninos": {
        Idioma.ES: "Adultos: {adultos} · Niños: {ninos}\n¿Cuántos adultos? (mínimo 1)"
    },
    "pregunta_editar_monto_valor": {
        Idioma.ES: "Valor actual: {actual}\n¿Nuevo valor total?"
    },
    "pregunta_editar_monto_abono": {
        Idioma.ES: "Abono actual: {actual}\n¿Nuevo abono? (0 si no hubo)"
    },
    "pregunta_cliente_email": {Idioma.ES: "¿Cuál es el correo electrónico del cliente?"},
    "pregunta_cliente_tipo_id": {Idioma.ES: "¿Tipo de identificación del cliente?"},
    "pregunta_cliente_identificacion": {Idioma.ES: "¿Número de identificación del cliente?"},
    "error_email_invalido": {Idioma.ES: "Correo inválido. Debe contener '@'."},
    "error_tipo_id_invalido": {Idioma.ES: "Opción inválida. Seleccioná CC o NIT."},
    "error_identificacion_vacia": {Idioma.ES: "La identificación no puede estar vacía."},
    "pregunta_editar_cliente_email": {
        Idioma.ES: "Correo actual: {actual}\n¿Cuál es el nuevo correo?"
    },
    "pregunta_editar_cliente_identificacion": {
        Idioma.ES: "Identificación actual: {actual}\n¿Cuál es la nueva identificación?"
    },
    # --- Egresos manuales ---
    "egreso.pedir_monto": {Idioma.ES: "¿Cuál es el monto del egreso?"},
    "egreso.pedir_descripcion": {Idioma.ES: "¿Qué descripción le das a este egreso?"},
    "egreso.pedir_categoria": {Idioma.ES: "¿Cuál es la categoría?"},
    "egreso.pedir_fecha": {
        Idioma.ES: "¿En qué fecha fue? (DD/MM o DD/MM/YYYY, o escribe *hoy*)"
    },
    "egreso.confirmar_resumen": {
        Idioma.ES: (
            "💸 *Nuevo egreso:*\n"
            "Monto: {monto}\n"
            "Descripción: {descripcion}\n"
            "Categoría: {categoria}\n"
            "Fecha: {fecha}\n\n"
            "¿Confirmamos?"
        )
    },
    "egreso.registrado": {Idioma.ES: "✅ Egreso registrado correctamente."},
    "egreso.error_monto": {
        Idioma.ES: "Monto inválido. Ingresa un valor positivo (ej: 50000 o 50.000)."
    },
    "egreso.error_fecha": {
        Idioma.ES: "Fecha inválida. Usa DD/MM, DD/MM/YYYY o escribe *hoy*."
    },
    "egreso.error_categoria": {
        Idioma.ES: "Categoría inválida. Elige una de las opciones."
    },
    # --- Gastos fijos ---
    "gastos_fijos.lista": {Idioma.ES: "📋 *Gastos fijos activos:*\n{lista}"},
    "gastos_fijos.vacio": {
        Idioma.ES: "No hay gastos fijos configurados. Usa el botón para agregar."
    },
    "gastos_fijos.pedir_nombre": {
        Idioma.ES: "¿Cuál es el nombre del gasto fijo? (ej: Arriendo oficina)"
    },
    "gastos_fijos.pedir_monto": {Idioma.ES: "¿Cuál es el monto mensual?"},
    "gastos_fijos.pedir_categoria": {Idioma.ES: "¿Cuál es la categoría?"},
    "gastos_fijos.pedir_dia": {
        Idioma.ES: "¿Qué día del mes se genera este gasto? (1 al 28)"
    },
    "gastos_fijos.creado": {
        Idioma.ES: "✅ Gasto fijo creado: *{nombre}* — {monto} el día {dia} de cada mes."
    },
    "gastos_fijos.desactivado": {Idioma.ES: "✅ *{nombre}* desactivado."},
    "gastos_fijos.confirmacion": {
        Idioma.ES: (
            "📋 *Nuevo gasto fijo:*\n"
            "Nombre: {nombre}\n"
            "Monto: {monto}\n"
            "Categoría: {categoria}\n"
            "Día del mes: {dia}\n\n"
            "¿Confirmamos?"
        )
    },
    # --- Conciliacion ---
    "conciliacion.sin_acceso": {Idioma.ES: "Este comando es solo para el propietario."},
    "conciliacion.sin_pendientes": {Idioma.ES: "No hay ingresos pendientes de conciliar."},
    "conciliacion.resumen": {
        Idioma.ES: (
            "Conciliación completada:\n"
            "✅ Matcheados: {matcheados}\n"
            "❌ Sin match: {sin_match}\n"
            "⏳ Pendientes: {pendientes}"
        )
    },
    "conciliacion.item_pendiente": {
        Idioma.ES: "💰 ${monto} de {banco} — {fecha}\nSugerencia: {sugerencia}"
    },
    "conciliacion.confirmado": {Idioma.ES: "✅ Ingreso marcado como matcheado."},
    "conciliacion.marcado_personal": {Idioma.ES: "👤 Ingreso marcado como personal."},
    "conciliacion.marcado_sin_match": {Idioma.ES: "❓ Ingreso marcado como sin match."},
    # --- Reportes / Dashboards ---
    "reporte.sin_datos": {Idioma.ES: "No hay datos para este período."},
    "reporte.ventas.encabezado": {
        Idioma.ES: (
            "📊 *Ventas — {mes} {año}*\n"
            "{total_ventas} ventas · ${total_valor}\n"
            "Ganancia agencia: ${ganancia}"
        )
    },
    "reporte.ventas.vendedor_item": {
        Idioma.ES: "• {nombre}: {ventas} ventas · comisión ${comision}"
    },
    "reporte.caja.encabezado": {
        Idioma.ES: (
            "💰 *Flujo de Caja — {mes} {año}*\n"
            "Ingresos: ${ingresos}\n"
            "Egresos: ${egresos}\n"
            "Balance: {signo}${balance}\n"
            "✅ Conciliados: {conciliados} · ⏳ Pendientes: {pendientes}"
        )
    },
    "reporte.caja.categoria_item": {Idioma.ES: "• {categoria}: ${monto}"},
    "reporte.nav_anterior": {Idioma.ES: "◀ {label}"},
    "reporte.nav_siguiente": {Idioma.ES: "{label} ▶"},
    # --- Generar mes ---
    "generar_mes.sin_activos": {
        Idioma.ES: "No hay gastos fijos activos para generar."
    },
    "generar_mes.resultado": {
        Idioma.ES: "✅ Generados {cantidad} egreso(s) para {mes}/{año}."
    },
    "generar_mes.ya_generados": {
        Idioma.ES: "Los gastos de {mes}/{año} ya fueron generados anteriormente."
    },
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
