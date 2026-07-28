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
