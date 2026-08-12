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
        Idioma.ES: "¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO"
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
    "pregunta_fecha_salida_tour": {
        Idioma.ES: "¿Fecha del tour {tour}? (DD/MM, DD/MM/YY o DD/MM/YYYY HH:MM)"
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
    "cancelar_sin_operacion": {
        Idioma.ES: "No hay ninguna operación activa. Escribí /start para comenzar."
    },
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
            "Saldo pendiente: {saldo_pendiente}\n"
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
    "pregunta_familia": {Idioma.ES: "Elegí la familia de tours:"},
    "pregunta_servicio_en_familia": {Idioma.ES: "Elegí el tour:"},
    "opcion_otro_tour": {Idioma.ES: "+ Otro tour"},
    "opcion_confirmar_destinos": {Idioma.ES: "✅ Confirmar"},
    "opcion_quitar_tour": {Idioma.ES: "❌ {nombre}"},
    "error_sin_destinos": {
        Idioma.ES: (
            "Necesitás al menos un tour para continuar. "
            "Elegí una familia y agregá un tour."
        )
    },
    "pregunta_modalidad_venta": {
        Idioma.ES: "¿Qué modalidad de venta es?\nOpciones: Presencial, Digital"
    },
    "error_modalidad_invalida": {
        Idioma.ES: "Opción inválida. Elegí Presencial o Digital."
    },
    "error_tipo_reserva_invalido": {
        Idioma.ES: "Opción inválida. Elegí INTERNO o EXTERNO."
    },
    "error_adultos_invalido": {Idioma.ES: "Número inválido. Ingresá un entero mayor a 0."},
    "error_adultos_minimo": {Idioma.ES: "Debe haber al menos 1 adulto."},
    "error_ninos_invalido": {Idioma.ES: "Número inválido. Ingresá un entero >= 0."},
    "error_ninos_negativo": {Idioma.ES: "El número de niños no puede ser negativo."},
    "error_abono_invalido": {Idioma.ES: "Monto inválido. Ingresá 0 si no hubo abono."},
    "pregunta_rol_venta": {Idioma.ES: "¿Cuál fue tu rol en esta venta?"},
    "pregunta_neto_sin_precio": {
        Idioma.ES: (
            "No hay precio en el catálogo para: {tours}.\n"
            "Ingresá el monto neto TOTAL de la venta (todos los tours)."
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
    "info_destinos_acumulados": {
        Idioma.ES: (
            "Tours seleccionados: {seleccionados}\n"
            "Agregá otro tour o confirmá para continuar."
        )
    },
    "error_abono_supera_valor": {
        Idioma.ES: ("El abono ({abono}) no puede superar el valor de la venta ({valor}).")
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
    "reporte.tours.encabezado": {
        Idioma.ES: (
            "🏝️ *Tours — {mes} {año}*\n"
            "Bruto vendido: ${bruto}\n"
            "Costo operadores: -${neto}\n"
            "Margen: ${margen}\n"
            "Comisiones: -${comisiones}\n"
            "*Agencia (Garay): ${agencia}*"
        )
    },
    "reporte.tours.familia_item": {Idioma.ES: "• {familia}: {vendidos} vta · margen ${margen}"},
    "reporte.tours.conciliacion": {
        Idioma.ES: (
            "🏦 *Conciliación banco:*\n"
            "Agencia esperada: ${agencia}\n"
            "Ingresos banco: ${banco}\n"
            "Desviación: {desviacion}%"
        )
    },
    "reporte.nav_anterior": {Idioma.ES: "◀ {label}"},
    "reporte.nav_siguiente": {Idioma.ES: "{label} ▶"},
    # --- Freelancers ---
    "freelancer.pedir_nombre": {Idioma.ES: "¿Cuál es el nombre del freelancer?"},
    "freelancer.error_nombre_vacio": {Idioma.ES: "El nombre no puede estar vacío. Ingresá el nombre:"},  # noqa: E501
    "freelancer.pedir_telegram_id": {Idioma.ES: "¿ID de Telegram del freelancer? (número entero, ej: 123456789)"},  # noqa: E501
    "freelancer.error_telegram_id_invalido": {Idioma.ES: "El ID debe ser un número entero. Intentá de nuevo:"},  # noqa: E501
    "freelancer.error_telegram_id_duplicado": {Idioma.ES: "Ese ID ya está asignado a otro freelancer. Ingresá otro:"},  # noqa: E501
    # Identity fields — Slice A1
    "freelancer.pedir_nombre_completo": {Idioma.ES: "¿Cuál es el nombre completo del freelancer?"},
    "freelancer.error_nombre_completo_vacio": {Idioma.ES: "El nombre completo no puede estar vacío. Ingresá el nombre completo:"},  # noqa: E501
    "freelancer.pedir_cedula": {Idioma.ES: "¿Cuál es el número de cédula? (6 a 10 dígitos)"},
    "freelancer.error_cedula_invalida": {Idioma.ES: "Cédula inválida. Debe contener entre 6 y 10 dígitos numéricos. Intentá de nuevo:"},  # noqa: E501
    "freelancer.error_cedula_duplicada": {Idioma.ES: "Ya existe un freelancer con esa cédula. Ingresá otra:"},  # noqa: E501
    "freelancer.pedir_nombre_corto": {Idioma.ES: "¿Cuál es el nombre corto? (Enter para usar \"{prefill}\")"},  # noqa: E501
    "freelancer.pedir_display_override": {Idioma.ES: "El display automático es \"{display}\". ¿Querés usarlo? (Enter para confirmar, o escribí uno nuevo)"},  # noqa: E501
    "freelancer.telegram_id_opcional": {Idioma.ES: "¿ID de Telegram del freelancer? (número entero) — o presioná Omitir:"},  # noqa: E501
    "freelancer.telegram_omitido": {Idioma.ES: "Telegram omitido. El freelancer no tendrá ID de Telegram vinculado."},  # noqa: E501
    "freelancer.confirmacion_nuevo": {
        Idioma.ES: (
            "¿Confirmás crear este freelancer?\n\n"
            "Nombre: {nombre}\n"
            "Cédula: {cedula}\n"
            "Display: {display}\n"
            "Telegram ID: {telegram_id}"
        )
    },
    "freelancer.creado": {Idioma.ES: "✅ Freelancer {nombre} creado correctamente."},
    "freelancer.cancelado": {Idioma.ES: "Operación cancelada."},
    "freelancer.lista_encabezado": {Idioma.ES: "👥 <b>Freelancers registrados:</b>"},
    "freelancer.lista_vacia": {Idioma.ES: "No hay freelancers registrados."},
    "freelancer.seleccionar_eliminar": {Idioma.ES: "Seleccioná el freelancer a desactivar:"},
    "freelancer.sin_activos": {Idioma.ES: "No hay freelancers activos para desactivar."},
    "freelancer.confirmar_eliminar": {Idioma.ES: "¿Desactivar a <b>{nombre}</b>?"},
    "freelancer.eliminado": {Idioma.ES: "✅ {nombre} fue desactivado."},
    # --- Freelancer edit — Slice A2 ---
    "freelancer.editar_seleccionar": {Idioma.ES: "Seleccioná el freelancer a editar:"},
    "freelancer.editar_sin_freelancers": {Idioma.ES: "No hay freelancers registrados para editar."},
    "freelancer.editar_menu_campo": {Idioma.ES: "¿Qué campo querés editar?"},
    "freelancer.editar_pedir_nombre_completo": {Idioma.ES: "Ingresá el nuevo nombre completo:"},
    "freelancer.editar_pedir_cedula": {Idioma.ES: "Ingresá la nueva cédula (6 a 10 dígitos):"},
    "freelancer.editar_pedir_nombre_corto": {
        Idioma.ES: (
            "Ingresá el nuevo nombre corto (se usa para conciliar /mis_ventas).\n"
            "⚠️ Cambiar este campo afecta la coincidencia histórica hasta Slice C."
        )
    },
    "freelancer.editar_pedir_telegram_id": {
        Idioma.ES: (
            "Ingresá el nuevo ID de Telegram (número entero) — "
            "o presioná «Quitar» para desvincularlo:"
        )
    },
    "freelancer.editar_activo_estado": {Idioma.ES: "Estado actual: {estado}\n¿Qué querés hacer?"},
    "freelancer.editar_confirmar": {
        Idioma.ES: "¿Confirmás cambiar <b>{campo}</b>?\n\nAnterior: {anterior}\nNuevo: {nuevo}"
    },
    "freelancer.editado": {Idioma.ES: "✅ Cambio guardado correctamente."},
    "freelancer.editar_ficha": {
        Idioma.ES: (
            "👤 <b>{display}</b>\n"
            "• Nombre completo: {nombre_completo}\n"
            "• Nombre corto: {nombre}\n"
            "• Cédula: {cedula}\n"
            "• Estado: {estado}"
        )
    },
    "freelancer.error_cedula_duplicada_otro": {
        Idioma.ES: "Esa cédula ya pertenece a otro freelancer. Ingresá una diferente:"
    },
    "freelancer.error_telegram_duplicado_otro": {
        Idioma.ES: "Ese ID de Telegram ya es de {nombre}. Ingresá uno diferente:"
    },
    "freelancer.editar_listo": {Idioma.ES: "Listo"},
    # --- Movimientos recientes ---
    "movimientos.encabezado": {
        Idioma.ES: "📋 Movimientos — últimas {horas} h"
    },
    "movimientos.sin_movimientos": {
        Idioma.ES: "No hay movimientos en el período indicado."
    },
    "movimientos.seccion_ingresos": {
        Idioma.ES: "💰 Ingresos:"
    },
    "movimientos.seccion_egresos": {
        Idioma.ES: "💸 Egresos:"
    },
    "movimientos.linea": {
        Idioma.ES: "• {monto} — {detalle} ({hora})"
    },
    "movimientos.tag_reenvio": {
        Idioma.ES: "[fwd]"
    },
    # --- Facturas ---
    "factura.asunto_email": {Idioma.ES: "Factura de servicio - Garay Tours"},
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
    "error_seleccion_freelancer_invalida": {
        Idioma.ES: (
            "Selección inválida. Usá los botones para elegir un freelancer registrado."
        )
    },
    "pregunta_seleccionar_vendedor": {
        Idioma.ES: "Seleccioná el vendedor:"
    },
    "pregunta_seleccionar_cerrador": {
        Idioma.ES: "Seleccioná el cerrador:"
    },
    "tiquetera.sin_freelancers_activos": {
        Idioma.ES: (
            "No hay freelancers activos registrados. "
            "Registrá uno con /nuevo_freelancer y volvé a intentar."
        )
    },
    # --- Slice 2: otro tour para el mismo cliente ---
    "pregunta_otro_tour": {Idioma.ES: "¿Registrar otro tour para {cliente}?"},
    "boton_otro_tour": {Idioma.ES: "➕ Otro tour"},  # noqa: RUF001
    "boton_terminar": {Idioma.ES: "🏁 Terminar"},
    "resumen_reservas": {
        Idioma.ES: "Listo: {cantidad} reserva(s) registrada(s) para {cliente}."
    },
    # --- Gestión de ventas (B2) ---
    "gestion_ventas.seleccionar": {
        Idioma.ES: "Selecciona una venta para gestionar:"
    },
    "gestion_ventas.sin_ventas": {
        Idioma.ES: "No hay ventas registradas en los últimos 30 días."
    },
    "gestion_ventas.detalle": {
        Idioma.ES: (
            "<b>Detalle de la venta</b>\n"
            "Cliente: {cliente}\n"
            "Tours: {tours}\n"
            "Fecha: {fecha}\n"
            "Valor: ${valor:,.0f}"
        )
    },
    "gestion_ventas.boton_anular": {Idioma.ES: "Anular"},
    "gestion_ventas.boton_cancelar": {Idioma.ES: "Cancelar"},
    "gestion_ventas.pedir_motivo": {
        Idioma.ES: "Escribe el motivo de la anulación (obligatorio):"
    },
    "gestion_ventas.pedir_motivo_editar": {
        Idioma.ES: "Escribe el motivo del cambio de fecha (obligatorio):"
    },
    "gestion_ventas.motivo_vacio": {
        Idioma.ES: "El motivo no puede estar vacío. Escribe el motivo:"
    },
    "gestion_ventas.confirmar": {
        Idioma.ES: (
            "¿Confirmas la anulación?\n\n"
            "Motivo: <b>{motivo}</b>"
        )
    },
    "gestion_ventas.boton_confirmar": {Idioma.ES: "Confirmar"},
    "gestion_ventas.anulada": {
        Idioma.ES: "La venta fue anulada correctamente."
    },
    "gestion_ventas.cancelado": {Idioma.ES: "Operación cancelada."},
    "gestion_ventas.no_encontrada": {
        Idioma.ES: "No se encontró la venta. Es posible que haya sido eliminada."
    },
    "gestion_ventas.ya_anulada": {
        Idioma.ES: "Esta venta ya fue anulada anteriormente."
    },
    "gestion_ventas.error_generico": {
        Idioma.ES: "Ocurrió un error al procesar la solicitud. Intenta de nuevo."
    },
    # --- Gestión de ventas B3: editar fecha ---
    "gestion_ventas.boton_editar": {Idioma.ES: "✏️ Editar fecha"},
    "gestion_ventas.pedir_fecha": {
        Idioma.ES: (
            "Escribe la nueva fecha del tour.\n"
            "Formato: DD/MM/AAAA HH:MM (o DD/MM/AAAA si no hay hora específica)."
        )
    },
    "gestion_ventas.fecha_invalida": {
        Idioma.ES: (
            "Fecha inválida. Usa el formato DD/MM/AAAA HH:MM o DD/MM/AAAA."
        )
    },
    "gestion_ventas.confirmar_editar": {
        Idioma.ES: (
            "¿Confirmas el cambio de fecha?\n\n"
            "Nueva fecha: <b>{fecha}</b>\n"
            "Motivo: <b>{motivo}</b>"
        )
    },
    "gestion_ventas.editada": {
        Idioma.ES: "La fecha de la venta fue actualizada correctamente."
    },
    # --- Gestión de ventas C2: correction messages for the group ---
    "gestion_ventas.correccion_anulacion": {
        Idioma.ES: (
            "⚠️ <b>Venta anulada</b>\n"
            "Agencia Garay Tours\n\n"
            "👤 Cliente: {cliente}\n"
            "📍 Tour: {tours}\n"
            "📝 Motivo: {motivo}\n"
            "🙍 Por: {actor}"
        )
    },
    "gestion_ventas.correccion_edicion_fecha": {
        Idioma.ES: (
            "📅 <b>Fecha de venta modificada</b>\n"
            "Agencia Garay Tours\n\n"
            "👤 Cliente: {cliente}\n"
            "📍 Tour: {tours}\n"
            "🗓 Nueva fecha: <b>{fecha}</b>\n"
            "📝 Motivo: {motivo}\n"
            "🙍 Por: {actor}"
        )
    },
    # --- Gestión de ventas C3: invoice regeneration status ---
    "gestion_ventas.factura_reenviada": {
        Idioma.ES: "📄 Factura actualizada reenviada al cliente."
    },
    "gestion_ventas.factura_error": {
        Idioma.ES: "⚠️ La venta se editó pero no se pudo reenviar la factura."
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
