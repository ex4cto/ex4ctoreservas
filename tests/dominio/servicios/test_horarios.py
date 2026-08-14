"""Tests for schedule time helpers — normalizar_horario, formato_display,
agregar_horario, quitar_horario.

RED phase: all tests in this file must FAIL before the implementation exists.
"""

from __future__ import annotations

import pytest

from garay.dominio.servicios.errores import HorarioDuplicado, HorarioInvalido
from garay.dominio.servicios.horarios import (
    agregar_horario,
    formato_display,
    normalizar_horario,
    quitar_horario,
)

# ── Task 1.1: normalizar_horario — 14-case table ──────────────────────────────


class TestNormalizarHorario:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("19:00", "19:00"),
            ("7pm", "19:00"),
            ("7:30am", "07:30"),
            ("7 PM", "19:00"),
            ("07:00", "07:00"),
            ("12pm", "12:00"),
            ("12am", "00:00"),
            ("9", "09:00"),
            ("9:5", "09:05"),
        ],
    )
    def test_entradas_validas(self, entrada: str, esperado: str) -> None:
        assert normalizar_horario(entrada) == esperado

    @pytest.mark.parametrize(
        "entrada",
        [
            "abc",
            "25:00",
            "7:60pm",
            "13pm",
            "",
        ],
    )
    def test_entradas_invalidas_levantan_error(self, entrada: str) -> None:
        with pytest.raises(HorarioInvalido):
            normalizar_horario(entrada)

    def test_minutos_cero_padded(self) -> None:
        assert normalizar_horario("9:05") == "09:05"

    def test_hora_24h_limite_superior(self) -> None:
        assert normalizar_horario("23:59") == "23:59"

    def test_medianoche_24h(self) -> None:
        assert normalizar_horario("0:00") == "00:00"

    def test_entrada_con_espacios_internos(self) -> None:
        assert normalizar_horario("7 : 30 pm") == "19:30"

    def test_no_acepta_mas_de_2_digitos_sin_separador(self) -> None:
        """Inputs like '730' (>2 digits, no colon) must be rejected per Q1 decision."""
        with pytest.raises(HorarioInvalido):
            normalizar_horario("730")

    def test_no_acepta_1930_sin_separador(self) -> None:
        with pytest.raises(HorarioInvalido):
            normalizar_horario("1930")


# ── Task 1.2: formato_display ─────────────────────────────────────────────────


class TestFormatoDisplay:
    @pytest.mark.parametrize(
        "canonico,esperado",
        [
            ("19:00", "7:00 PM"),
            ("07:30", "7:30 AM"),
            ("12:00", "12:00 PM"),
            ("00:00", "12:00 AM"),
            ("09:05", "9:05 AM"),
            ("13:45", "1:45 PM"),
        ],
    )
    def test_display_correcto(self, canonico: str, esperado: str) -> None:
        assert formato_display(canonico) == esperado


# ── Task 1.3: agregar_horario ─────────────────────────────────────────────────


class TestAgregarHorario:
    def test_agrega_y_ordena(self) -> None:
        resultado = agregar_horario(["09:00"], "7am")
        assert resultado == ["07:00", "09:00"]

    def test_lista_vacia(self) -> None:
        resultado = agregar_horario([], "7pm")
        assert resultado == ["19:00"]

    def test_orden_cronologico(self) -> None:
        lista = agregar_horario(["07:00", "19:00"], "12pm")
        assert lista == ["07:00", "12:00", "19:00"]

    def test_duplicado_levanta_error(self) -> None:
        with pytest.raises(HorarioDuplicado):
            agregar_horario(["19:00"], "7pm")

    def test_duplicado_exacto(self) -> None:
        with pytest.raises(HorarioDuplicado):
            agregar_horario(["07:00"], "07:00")

    def test_no_muta_lista_original(self) -> None:
        original = ["09:00"]
        resultado = agregar_horario(original, "7am")
        assert original == ["09:00"]
        assert resultado == ["07:00", "09:00"]

    def test_invalido_levanta_horario_invalido(self) -> None:
        with pytest.raises(HorarioInvalido):
            agregar_horario([], "abc")


# ── Task 1.4: quitar_horario ──────────────────────────────────────────────────


class TestQuitarHorario:
    def test_quita_por_canonico(self) -> None:
        resultado = quitar_horario(["07:00", "19:00"], "07:00")
        assert resultado == ["19:00"]

    def test_idempotente_si_no_esta(self) -> None:
        lista = ["07:00", "19:00"]
        resultado = quitar_horario(lista, "12:00")
        assert resultado == ["07:00", "19:00"]

    def test_no_muta_lista_original(self) -> None:
        original = ["07:00", "19:00"]
        resultado = quitar_horario(original, "07:00")
        assert original == ["07:00", "19:00"]
        assert resultado == ["19:00"]

    def test_quita_unico_elemento(self) -> None:
        assert quitar_horario(["12:00"], "12:00") == []

    def test_lista_vacia_idempotente(self) -> None:
        assert quitar_horario([], "07:00") == []
