"""RED/GREEN tests for validar_cedula and derivar_display pure functions."""

from __future__ import annotations

import pytest

from garay.dominio.freelancers.errores import CedulaInvalida, EmailInvalido
from garay.dominio.freelancers.validaciones import (
    derivar_display,
    validar_cedula,
    validar_email,
)


class TestValidarEmail:
    def test_email_valido_se_normaliza(self) -> None:
        assert validar_email("  cerrador@garay.com  ") == "cerrador@garay.com"

    def test_email_con_subdominio(self) -> None:
        assert validar_email("a.b@mail.ex4cto.co") == "a.b@mail.ex4cto.co"

    def test_sin_arroba_invalido(self) -> None:
        with pytest.raises(EmailInvalido):
            validar_email("cerrador.garay.com")

    def test_sin_punto_en_dominio_invalido(self) -> None:
        with pytest.raises(EmailInvalido):
            validar_email("cerrador@garay")

    def test_con_espacios_invalido(self) -> None:
        with pytest.raises(EmailInvalido):
            validar_email("cerra dor@garay.com")

    def test_vacio_invalido(self) -> None:
        with pytest.raises(EmailInvalido):
            validar_email("")


class TestValidarCedula:
    # --- valid inputs ---

    def test_cedula_6_digitos_valida(self) -> None:
        assert validar_cedula("123456") == "123456"

    def test_cedula_8_digitos_valida(self) -> None:
        assert validar_cedula("12345678") == "12345678"

    def test_cedula_10_digitos_valida(self) -> None:
        assert validar_cedula("1234567890") == "1234567890"

    def test_cedula_con_espacios_se_normaliza(self) -> None:
        assert validar_cedula("  123456  ") == "123456"

    # --- invalid inputs ---

    def test_cedula_5_digitos_rechazada(self) -> None:
        with pytest.raises(CedulaInvalida):
            validar_cedula("12345")

    def test_cedula_11_digitos_rechazada(self) -> None:
        with pytest.raises(CedulaInvalida):
            validar_cedula("12345678901")

    def test_cedula_con_letras_rechazada(self) -> None:
        with pytest.raises(CedulaInvalida):
            validar_cedula("1234AB78")

    def test_cedula_vacia_rechazada(self) -> None:
        with pytest.raises(CedulaInvalida):
            validar_cedula("")

    def test_cedula_solo_espacios_rechazada(self) -> None:
        with pytest.raises(CedulaInvalida):
            validar_cedula("   ")


class TestDerivarDisplay:
    def test_nombre_multipalabra_tres_tokens(self) -> None:
        assert derivar_display("Bryan Castro Gomez") == "Bryan C."

    def test_nombre_dos_tokens_inicial_del_ultimo(self) -> None:
        assert derivar_display("Yolymar Perez") == "Yolymar P."

    def test_nombre_tres_tokens_inicial_del_ultimo(self) -> None:
        assert derivar_display("Yolymar Perez Banquez") == "Yolymar P."

    def test_nombre_una_palabra_verbatim(self) -> None:
        assert derivar_display("Madonna") == "Madonna"

    def test_espacios_borde_ignorados(self) -> None:
        assert derivar_display("  Bryan Castro  ") == "Bryan C."

    def test_caracteres_acentuados_preservados(self) -> None:
        assert derivar_display("Ángela Gómez") == "Ángela G."

    def test_cadena_vacia_devuelve_vacia(self) -> None:
        assert derivar_display("") == ""
