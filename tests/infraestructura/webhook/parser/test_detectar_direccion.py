"""Tests for detectar_direccion — RED phase."""

from __future__ import annotations

from garay.infraestructura.webhook.parser.base import detectar_direccion


def test_compraste_detecta_egreso() -> None:
    texto = (
        "Bancolombia: Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb *9283,"
        " el 27/07/2026 a las 18:25."
    )
    assert detectar_direccion(texto) == "egreso"


def test_transferiste_detecta_egreso() -> None:
    texto = (
        "Bancolombia: Transferiste $50,000.00 desde tu cuenta 7488 a la cuenta"
        " *3207904880 el 26/07/2026 a las 14:05."
    )
    assert detectar_direccion(texto) == "egreso"


def test_enviaste_detecta_egreso() -> None:
    texto = (
        "Enviaste de manera exitosa 5.000 a la llave 1047487553 de BRYAN CASTRO"
        " el 25 de julio de 2026 a las 7:05 p.m."
    )
    assert detectar_direccion(texto) == "egreso"


def test_pagaste_con_nequi_detecta_egreso() -> None:
    texto = "Pagaste con Nequi tu factura por $3.000"
    assert detectar_direccion(texto) == "egreso"


def test_texto_ingreso_retorna_ingreso() -> None:
    texto = "recibiste una transferencia de Juan Perez por $500,000 el 15/07/26 a las 10:30"
    assert detectar_direccion(texto) == "ingreso"


def test_texto_sin_keywords_retorna_ingreso() -> None:
    texto = "Notificacion bancaria sin keywords relevantes"
    assert detectar_direccion(texto) == "ingreso"
