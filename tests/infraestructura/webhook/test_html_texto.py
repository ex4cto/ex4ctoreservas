"""Tests for html_a_texto and the schema-level HTML fallback (Nequi auto-forward)."""

from __future__ import annotations

from decimal import Decimal

from garay.infraestructura.webhook.html_texto import html_a_texto
from garay.infraestructura.webhook.parser.bancolombia_egreso import ParserBancolombiaEgreso
from garay.infraestructura.webhook.parser.nequi import ParserNequi
from garay.infraestructura.webhook.parser.nequi_egreso import ParserNequiEgreso
from garay.infraestructura.webhook.schemas import PayloadEmail

# HTML-only egreso emails (Gmail auto-forward): wrap the real bank egreso text in
# markup to prove the schema-level html_a_texto fallback feeds the egreso parsers.
_BANCOLOMBIA_EGRESO_HTML = (
    "<html><body><table><tr><td>"
    "<p>Bancolombia: Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb *9283, "
    "el 27/07/2026 a las 18:25.</p>"
    "</td></tr></table></body></html>"
)
_NEQUI_EGRESO_HTML = (
    "<html><body><div>"
    "Enviaste de manera exitosa 5.000 a la llave 1047487553 de BRYAN CASTRO "
    "el 25 de julio de 2026 a las 7:05 p.m."
    "</div></body></html>"
)

# Realistic Nequi Bre-B "Recibiste" email: HTML-only, wrapped in tables/spans,
# with an NBSP and an entity — mirrors what Gmail auto-forward delivers.
_NEQUI_HTML = (
    "<html><head><style>.x{color:#da0081}</style></head><body>"
    "<table><tr><td>"
    "<h1>¡Recibiste plata por Bre-B!</h1>"
    "<p>¡Hola,&nbsp;julio Cesar Garay Manzur!</p>"
    "<p>Recibiste <span>1.183.000</span> de Carlos Alberto Ferro Urango "
    "el 31 de julio de 2026 a las 6:24 p.m, desde el banco Bold.</p>"
    "</td></tr></table>"
    "<script>track()</script></body></html>"
)


def test_saca_etiquetas_y_conserva_texto() -> None:
    assert html_a_texto("<p>Hola <b>mundo</b></p>") == "Hola mundo"


def test_decodifica_entidades() -> None:
    assert html_a_texto("Garc&iacute;a &amp; Co") == "García & Co"


def test_ignora_style_y_script() -> None:
    html = "<style>.x{color:red}</style><div>Recibiste 1 de BRYAN</div><script>x()</script>"
    assert html_a_texto(html) == "Recibiste 1 de BRYAN"


def test_colapsa_espacios_saltos_y_nbsp() -> None:
    assert html_a_texto("a\n\nb\t c\xa0d") == "a b c d"


def test_nequi_html_produce_texto_con_frase_parseable() -> None:
    texto = html_a_texto(_NEQUI_HTML)
    assert (
        "Recibiste 1.183.000 de Carlos Alberto Ferro Urango "
        "el 31 de julio de 2026 a las 6:24 p.m" in texto
    )


def test_schema_rellena_cuerpo_texto_desde_html_cuando_falta() -> None:
    payload = PayloadEmail.model_validate(
        {
            "messageId": "<nequi-1>",
            "from": {"value": [{"address": "notificaciones@nequi.com.co"}]},
            "to": {"value": [{"address": "garaytours@ex4cto.co"}]},
            "subject": "¡Recibiste plata por Bre-B!",
            "html": _NEQUI_HTML,
            "text": None,
        }
    )
    assert payload.cuerpo_texto  # antes quedaba vacío y el parser fallaba
    assert "Recibiste 1.183.000 de Carlos Alberto Ferro Urango" in payload.cuerpo_texto


def test_nequi_ingreso_html_only_extremo_a_extremo() -> None:
    """The exact production failure: Nequi HTML-only auto-forward must now parse."""
    payload = PayloadEmail.model_validate(
        {
            "messageId": "<nequi-1>",
            "from": {"value": [{"address": "notificaciones@nequi.com.co"}]},
            "to": {"value": [{"address": "garaytours@ex4cto.co"}]},
            "subject": "¡Recibiste plata por Bre-B!",
            "html": _NEQUI_HTML,
            "text": None,
        }
    )
    pago = ParserNequi().parsear(payload.cuerpo_html, payload.cuerpo_texto)
    assert pago.monto == Decimal("1183000.00")
    assert pago.remitente == "Carlos Alberto Ferro Urango"
    assert pago.banco_origen == "Nequi"
    assert pago.fecha_pago.day == 31
    assert pago.fecha_pago.hour == 18
    assert pago.fecha_pago.minute == 24


def test_bancolombia_egreso_html_only_extremo_a_extremo() -> None:
    """The original 2:29pm problem shape: a Bancolombia egreso arriving HTML-only."""
    payload = PayloadEmail.model_validate(
        {
            "messageId": "<bc-egreso-1>",
            "from": {
                "value": [
                    {"address": "alertasynotificaciones@an.notificacionesbancolombia.com"}
                ]
            },
            "to": {"value": [{"address": "garaytours@ex4cto.co"}]},
            "subject": "Compraste",
            "html": _BANCOLOMBIA_EGRESO_HTML,
            "text": None,
        }
    )
    egreso = ParserBancolombiaEgreso().parsear(payload.cuerpo_html, payload.cuerpo_texto)
    assert egreso.monto == Decimal("69328.00")
    assert egreso.descripcion == "Compra en MOVISTAR PAGOSEPAYCO"
    assert egreso.banco_origen == "Bancolombia"


def test_nequi_egreso_html_only_extremo_a_extremo() -> None:
    payload = PayloadEmail.model_validate(
        {
            "messageId": "<nequi-egreso-1>",
            "from": {"value": [{"address": "notificaciones@nequi.com.co"}]},
            "to": {"value": [{"address": "garaytours@ex4cto.co"}]},
            "subject": "Enviaste",
            "html": _NEQUI_EGRESO_HTML,
            "text": None,
        }
    )
    egreso = ParserNequiEgreso().parsear(payload.cuerpo_html, payload.cuerpo_texto)
    assert egreso.monto == Decimal("5000")
    assert egreso.descripcion == "Envio a BRYAN CASTRO"
    assert egreso.banco_origen == "Nequi"
