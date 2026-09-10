"""Tests for normalizar_texto — cosmetic text normalization (no autocorrect)."""

from __future__ import annotations

from garay.aplicacion.comun.texto import normalizar_texto


def test_quita_espacios_sobrantes_y_capitaliza() -> None:
    assert normalizar_texto("  juan   perez  ") == "Juan perez"


def test_capitaliza_solo_la_primera_letra_no_title_case() -> None:
    # No es title-case: "del", "rosario" NO se capitalizan (no daña nombres propios).
    assert normalizar_texto("islas del rosario") == "Islas del rosario"


def test_ya_normalizado_es_idempotente() -> None:
    assert normalizar_texto("Juan perez") == "Juan perez"


def test_solo_espacios_queda_vacio() -> None:
    assert normalizar_texto("   ") == ""


def test_cadena_vacia() -> None:
    assert normalizar_texto("") == ""


def test_colapsa_saltos_y_tabs() -> None:
    assert normalizar_texto("pago\t a\n  juan") == "Pago a juan"
