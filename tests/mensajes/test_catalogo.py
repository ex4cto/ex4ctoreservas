"""Tests for the centralized message catalog."""

from __future__ import annotations

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
