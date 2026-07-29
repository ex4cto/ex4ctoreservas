"""Tests for the centralized message catalog."""

from __future__ import annotations

from typing import ClassVar

import pytest

from garay.dominio.comun.errores import ErrorDeConfiguracion
from garay.mensajes.catalogo import obtener_mensaje


class TestObtenerMensaje:
    def test_clave_existente_retorna_string(self) -> None:
        msg = obtener_mensaje("bienvenida")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_clave_inexistente_lanza_error(self) -> None:
        with pytest.raises(ErrorDeConfiguracion):
            obtener_mensaje("clave_que_no_existe")


class TestClavesEsperandoFoto:
    def test_pregunta_enviar_foto_existe(self) -> None:
        msg = obtener_mensaje("pregunta_enviar_foto")
        assert "foto" in msg.lower()

    def test_error_metodo_invalido_existe(self) -> None:
        msg = obtener_mensaje("error_metodo_invalido")
        assert "Manual" in msg
        assert "Foto" in msg

    def test_error_esperando_foto_texto_existe(self) -> None:
        msg = obtener_mensaje("error_esperando_foto_texto")
        assert "foto" in msg.lower()


class TestClavesFormatoFecha:
    def test_pregunta_fecha_salida_incluye_formato_corto(self) -> None:
        msg = obtener_mensaje("pregunta_fecha_salida")
        assert "DD/MM/YY" in msg

    def test_error_fecha_invalida_incluye_formato_corto(self) -> None:
        msg = obtener_mensaje("error_fecha_invalida")
        assert "DD/MM/YY" in msg


class TestClavesUnificacionBatchA:
    def test_pregunta_cliente_hotel_incluye_sufijo_sin_hotel(self) -> None:
        msg = obtener_mensaje("pregunta_cliente_hotel")
        assert "escribí 'no'" in msg

    def test_pregunta_fecha_salida_no_tiene_prefijo_formato(self) -> None:
        msg = obtener_mensaje("pregunta_fecha_salida")
        assert "formato:" not in msg
        assert "DD/MM/YY" in msg


class TestClavesNuevasBatchB:
    def test_pregunta_metodo_input(self) -> None:
        msg = obtener_mensaje("pregunta_metodo_input")
        assert "registrar" in msg.lower()

    def test_pregunta_destino_numero(self) -> None:
        msg = obtener_mensaje("pregunta_destino_numero")
        assert "número" in msg.lower() or "numero" in msg.lower()

    def test_info_sin_tours_seleccionados(self) -> None:
        msg = obtener_mensaje("info_sin_tours_seleccionados")
        assert "seleccionaste" in msg.lower()

    def test_error_tipo_reserva_invalido(self) -> None:
        msg = obtener_mensaje("error_tipo_reserva_invalido")
        assert "INTERNO" in msg

    def test_error_sin_destino_numero(self) -> None:
        msg = obtener_mensaje("error_sin_destino_numero")
        assert "número" in msg.lower() or "numero" in msg.lower()

    def test_error_adultos_invalido(self) -> None:
        msg = obtener_mensaje("error_adultos_invalido")
        assert "entero" in msg.lower()

    def test_error_adultos_minimo(self) -> None:
        msg = obtener_mensaje("error_adultos_minimo")
        assert "adulto" in msg.lower()

    def test_error_ninos_invalido(self) -> None:
        msg = obtener_mensaje("error_ninos_invalido")
        assert "entero" in msg.lower()

    def test_error_ninos_negativo(self) -> None:
        msg = obtener_mensaje("error_ninos_negativo")
        assert "negativo" in msg.lower()

    def test_error_abono_invalido(self) -> None:
        msg = obtener_mensaje("error_abono_invalido")
        assert "abono" in msg.lower()

    def test_pregunta_rol_venta(self) -> None:
        msg = obtener_mensaje("pregunta_rol_venta")
        assert "rol" in msg.lower()

    def test_pregunta_neto_sin_precio(self) -> None:
        msg = obtener_mensaje("pregunta_neto_sin_precio")
        assert "neto" in msg.lower()

    def test_error_neto_invalido(self) -> None:
        msg = obtener_mensaje("error_neto_invalido")
        assert "neto" in msg.lower() or "monto" in msg.lower()

    def test_error_rol_invalido(self) -> None:
        msg = obtener_mensaje("error_rol_invalido")
        assert "Ambos" in msg

    def test_error_interno_rol_no_definido(self) -> None:
        msg = obtener_mensaje("error_interno_rol_no_definido")
        assert "rol" in msg.lower()

    def test_confirmacion_venta_exitosa(self) -> None:
        msg = obtener_mensaje("confirmacion_venta_exitosa")
        assert "éxito" in msg.lower() or "exitosa" in msg.lower() or "registrada" in msg.lower()

    def test_pregunta_campo_editar(self) -> None:
        msg = obtener_mensaje("pregunta_campo_editar")
        assert "campo" in msg.lower() or "modificar" in msg.lower()

    def test_error_campo_editar_invalido(self) -> None:
        msg = obtener_mensaje("error_campo_editar_invalido")
        assert "campo" in msg.lower() or "opción" in msg.lower() or "opcion" in msg.lower()

    def test_error_estado_no_manejable(self) -> None:
        msg = obtener_mensaje("error_estado_no_manejable")
        assert len(msg) > 0


class TestClavesTemplateBatchC:
    def test_info_destinos_seleccionados_format(self) -> None:
        template = obtener_mensaje("info_destinos_seleccionados")
        result = template.format(seleccionados="15 — Playa Blanca, 23 — Cartagena")
        assert "{" not in result
        assert "Seleccionados:" in result

    def test_info_ia_detecto_destinos_format(self) -> None:
        template = obtener_mensaje("info_ia_detecto_destinos")
        result = template.format(nombres="Playa Blanca")
        assert "{" not in result
        assert "IA" in result or "detectó" in result

    def test_error_destino_no_encontrado_format(self) -> None:
        template = obtener_mensaje("error_destino_no_encontrado")
        result = template.format(invalidos="99", destinos_mensaje="Ingresá el número...")
        assert "{" not in result
        assert "99" in result

    def test_error_abono_supera_neto_format(self) -> None:
        template = obtener_mensaje("error_abono_supera_neto")
        result = template.format(abono="$500.000", neto="$400.000")
        assert "{" not in result
        assert "$500.000" in result

    def test_error_neto_supera_valor_detalle_format(self) -> None:
        template = obtener_mensaje("error_neto_supera_valor_detalle")
        result = template.format(neto="$50.000", valor="$40.000")
        assert "{" not in result
        assert "$50.000" in result

    def test_error_neto_supera_valor_monto_neto_format(self) -> None:
        template = obtener_mensaje("error_neto_supera_valor_monto_neto")
        result = template.format(neto="$200.000", valor="$100.000")
        assert "{" not in result
        assert "$200.000" in result


class TestClavesFotoExtraccion:
    """Tests for new catalog keys added in foto-validate-catalog change."""

    CLAVES_NUEVAS: ClassVar[list[str]] = [
        "titulo_datos_extraidos_foto",
        "completar_datos_faltantes",
        "dato_extraido_nombre",
        "dato_extraido_telefono",
        "dato_extraido_fecha",
        "dato_extraido_destinos",
        "dato_extraido_adultos",
        "dato_extraido_ninos",
        "dato_extraido_valor",
        "dato_extraido_abono",
        "dato_extraido_ticket",
        "dato_extraido_hotel",
        "dato_extraido_habitacion",
        "dato_extraido_vendedor",
        "error_extraccion_no_disponible",
        "error_extraccion_timeout",
        "error_extraccion_fallo",
        "error_datos_incompletos",
    ]

    def test_todas_las_claves_nuevas_existen(self) -> None:
        """All 18 new keys must be present in the catalog."""
        for clave in self.CLAVES_NUEVAS:
            msg = obtener_mensaje(clave)
            assert isinstance(msg, str) and len(msg) > 0, f"Key missing or empty: {clave!r}"

    def test_error_datos_incompletos_tiene_placeholder_campos(self) -> None:
        template = obtener_mensaje("error_datos_incompletos")
        assert "{campos}" in template

    def test_ninguna_clave_nueva_tiene_voseo(self) -> None:
        voseo_palabras = ("usá", "intentá", "podés", "escribí", "elegí", "ingresá")
        for clave in self.CLAVES_NUEVAS:
            msg = obtener_mensaje(clave)
            for palabra in voseo_palabras:
                assert palabra not in msg, (
                    f"Key {clave!r} contains voseo {palabra!r}: {msg!r}"
                )

    def test_dato_extraido_nombre_tiene_placeholder_valor(self) -> None:
        template = obtener_mensaje("dato_extraido_nombre")
        result = template.format(valor="Ana García")
        assert "Ana García" in result
        assert "{" not in result

    def test_dato_extraido_valor_tiene_placeholder_valor(self) -> None:
        template = obtener_mensaje("dato_extraido_valor")
        result = template.format(valor="$260.000")
        assert "$260.000" in result
        assert "{" not in result

    def test_titulo_datos_extraidos_foto_tiene_markdown(self) -> None:
        msg = obtener_mensaje("titulo_datos_extraidos_foto")
        assert "*" in msg  # Markdown bold

    def test_error_extraccion_no_disponible_no_tiene_voseo(self) -> None:
        msg = obtener_mensaje("error_extraccion_no_disponible")
        assert "usá" not in msg
        assert "usa" in msg.lower() or "/start" in msg

    def test_error_datos_incompletos_format_completo(self) -> None:
        template = obtener_mensaje("error_datos_incompletos")
        result = template.format(campos="Nombre del cliente\n• Teléfono")
        assert "{" not in result
        assert "Nombre del cliente" in result


class TestClavesReportesDashboard:
    """Tests for dashboard report catalog keys — Etapa 8."""

    CLAVES_REPORTES: ClassVar[list[str]] = [
        "reporte.sin_datos",
        "reporte.ventas.encabezado",
        "reporte.ventas.vendedor_item",
        "reporte.caja.encabezado",
        "reporte.caja.categoria_item",
        "reporte.nav_anterior",
        "reporte.nav_siguiente",
    ]

    def test_todas_las_claves_de_reportes_existen(self) -> None:
        for clave in self.CLAVES_REPORTES:
            msg = obtener_mensaje(clave)
            assert isinstance(msg, str) and len(msg) > 0, f"Key missing: {clave!r}"

    def test_reporte_sin_datos_es_string(self) -> None:
        msg = obtener_mensaje("reporte.sin_datos")
        assert isinstance(msg, str)

    def test_reporte_ventas_encabezado_tiene_placeholders(self) -> None:
        template = obtener_mensaje("reporte.ventas.encabezado")
        result = template.format(
            mes="Julio", año=2026, total_ventas=10,
            total_valor="1.000.000", ganancia="200.000",
        )
        assert "{" not in result

    def test_reporte_caja_encabezado_tiene_placeholders(self) -> None:
        template = obtener_mensaje("reporte.caja.encabezado")
        result = template.format(
            mes="Julio", año=2026,
            ingresos="500.000", egresos="300.000",
            signo="+", balance="200.000",
            conciliados=3, pendientes=1,
        )
        assert "{" not in result

    def test_reporte_nav_anterior_tiene_placeholder_label(self) -> None:
        template = obtener_mensaje("reporte.nav_anterior")
        result = template.format(label="Junio 2026")
        assert "Junio 2026" in result
        assert "{" not in result

    def test_reporte_nav_siguiente_tiene_placeholder_label(self) -> None:
        template = obtener_mensaje("reporte.nav_siguiente")
        result = template.format(label="Agosto 2026")
        assert "Agosto 2026" in result
        assert "{" not in result


class TestConfirmacionResumenEspecialE:
    def test_confirmacion_resumen_no_tiene_numero_ticket(self) -> None:
        template = obtener_mensaje("confirmacion_resumen")
        assert "numero_ticket" not in template
        assert "Ticket" not in template

    def test_confirmacion_resumen_tiene_vendedor_y_cerrador(self) -> None:
        template = obtener_mensaje("confirmacion_resumen")
        assert "{vendedor}" in template
        assert "{cerrador}" in template

    def test_confirmacion_resumen_format_completo_sin_error(self) -> None:
        template = obtener_mensaje("confirmacion_resumen")
        result = template.format(
            tipo="EXTERNO",
            canal="—",
            punto_de_venta="Oficina",
            destinos="Tour Playa Blanca",
            cliente_nombre="Juan Pérez",
            cliente_telefono="3001234567",
            cliente_email="juan@example.com",
            cliente_identificacion="1234567890",
            cliente_hotel="Hotel Mar",
            cliente_habitacion="302",
            fecha_salida="15/08/2025",
            adultos=2,
            ninos=0,
            valor="$200.000",
            abono="$100.000",
            neto="$150.000",
            vendedor="(tú)",
            cerrador="María García",
        )
        assert "{" not in result
        assert "Tour Playa Blanca" in result
        assert "Ticket" not in result
        assert "Vendedor: (tú)" in result
