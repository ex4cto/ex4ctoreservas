"""Tests for es_transaccion — conservative non-transaction gate."""

from __future__ import annotations

import pytest

from garay.infraestructura.webhook.parser.base import es_transaccion

# ---------------------------------------------------------------------------
# TRUE cases — every transaction verb must be recognized
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cuerpo", [
    "Recibiste una transferencia por $500,000 de Carlos Gomez en tu cuenta **5643",
    "Transferiste $580,000 desde tu cuenta *5643 a la cuenta * 08600002475 el 10/08/2026",
    "Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb *9283",
    "Enviaste de manera exitosa 5.000 a la llave 1047487553 de BRYAN CASTRO",
    "Pagaste con Nequi tu factura por $3.000",
    "Hiciste un pago de $120,000 con Bancolombia",
    "Bancolombia: consignación recibida por $200,000",  # covers "consignaci"
])
def test_es_transaccion_retorna_true_para_verbos_transaccionales(cuerpo: str) -> None:
    assert es_transaccion(cuerpo) is True


def test_es_transaccion_retorna_true_para_cuerpo_pse() -> None:
    """PSE marker 'CUS:' must be recognized via the existing _es_pse helper."""
    cuerpo = (
        "PSE - Transaccion aprobada. "
        "CUS: 455692497 Valor: $120,000 Comercio: GARAY TOURS"
    )
    assert es_transaccion(cuerpo) is True


# ---------------------------------------------------------------------------
# FALSE cases — non-transaction emails must be rejected
# ---------------------------------------------------------------------------

def test_es_transaccion_retorna_false_para_marketing() -> None:
    cuerpo = (
        "Si todo sube, ¿qué pasa con tu plata? ... "
        "Haz que crezca con un fondo de inversión."
    )
    assert es_transaccion(cuerpo) is False


def test_es_transaccion_retorna_false_para_aviso_factura() -> None:
    cuerpo = (
        "Tu factura de Tigo con referencia 3012853555 está lista para pagar. "
        "Págala en la app."
    )
    assert es_transaccion(cuerpo) is False


def test_es_transaccion_retorna_false_para_cuerpo_vacio() -> None:
    assert es_transaccion("") is False


def test_es_transaccion_retorna_false_para_boletin_seguridad() -> None:
    cuerpo = (
        "En temporada de declaración cuida tu info y tu plata. "
        "Repórtalo a correosospechoso@nequi.com"
    )
    assert es_transaccion(cuerpo) is False
