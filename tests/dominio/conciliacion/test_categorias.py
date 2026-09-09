"""Tests for dominio/conciliacion/categorias.py — category constants and banco_a_categoria."""

from __future__ import annotations

from garay.dominio.conciliacion.categorias import (
    CATEGORIA_OTRO,
    CATEGORIA_TRANSPORTE,
    CATEGORIAS_PROTEGIDAS,
    banco_a_categoria,
    es_categoria_duplicada,
    es_categoria_protegida,
    sugerir_categoria_parecida,
)


class TestConstantes:
    def test_categoria_transporte_valor(self) -> None:
        assert CATEGORIA_TRANSPORTE == "transporte"

    def test_categoria_otro_valor(self) -> None:
        assert CATEGORIA_OTRO == "otro"


class TestBancoACategoria:
    def test_uber_retorna_transporte(self) -> None:
        assert banco_a_categoria("Uber") == "transporte"

    def test_didi_retorna_transporte(self) -> None:
        assert banco_a_categoria("DiDi") == "transporte"

    def test_nequi_retorna_otro(self) -> None:
        assert banco_a_categoria("Nequi") == "otro"

    def test_bancolombia_retorna_otro(self) -> None:
        assert banco_a_categoria("Bancolombia") == "otro"

    def test_pse_retorna_otro(self) -> None:
        assert banco_a_categoria("PSE") == "otro"

    def test_banco_desconocido_retorna_otro(self) -> None:
        assert banco_a_categoria("unknown_bank") == "otro"


class TestCategoriasProtegidas:
    def test_transporte_es_protegida(self) -> None:
        assert es_categoria_protegida("transporte") is True

    def test_otro_es_protegida(self) -> None:
        assert es_categoria_protegida("otro") is True

    def test_es_case_insensitive_y_tolera_espacios(self) -> None:
        assert es_categoria_protegida("Transporte") is True
        assert es_categoria_protegida("  OTRO  ") is True

    def test_categoria_normal_no_es_protegida(self) -> None:
        assert es_categoria_protegida("arriendo") is False

    def test_conjunto_protegidas(self) -> None:
        assert frozenset({CATEGORIA_TRANSPORTE, CATEGORIA_OTRO}) == CATEGORIAS_PROTEGIDAS


class TestEsCategoriaDuplicada:
    def test_duplicada_case_insensitive(self) -> None:
        assert es_categoria_duplicada("Comisiones", ["comisiones", "marketing"]) is True

    def test_duplicada_ignora_acentos(self) -> None:
        assert es_categoria_duplicada("alimentacion", ["Alimentación"]) is True

    def test_no_duplicada(self) -> None:
        assert es_categoria_duplicada("papelería", ["comisiones", "marketing"]) is False

    def test_lista_vacia(self) -> None:
        assert es_categoria_duplicada("comisiones", []) is False


class TestSugerirCategoriaParecida:
    def test_sugiere_parecida_por_typo(self) -> None:
        assert (
            sugerir_categoria_parecida("papleria", ["Papelería", "Marketing"])
            == "Papelería"
        )

    def test_sugiere_aunque_la_existente_tenga_acentos(self) -> None:
        # "alimentacio" (typo sin tilde) debe sugerir "Alimentación" (con tilde):
        # la comparacion ignora acentos, pero al NO ser identicos es una sugerencia.
        assert (
            sugerir_categoria_parecida("alimentacio", ["Alimentación"])
            == "Alimentación"
        )

    def test_nombre_distinto_no_sugiere(self) -> None:
        assert sugerir_categoria_parecida("software", ["comisiones", "marketing"]) is None

    def test_lista_vacia_no_sugiere(self) -> None:
        assert sugerir_categoria_parecida("papeleria", []) is None

    def test_match_exacto_no_se_sugiere_a_si_mismo(self) -> None:
        # Un match exacto (normalizado) es un duplicado, no una "sugerencia de parecido".
        assert sugerir_categoria_parecida("Comisiones", ["comisiones"]) is None
