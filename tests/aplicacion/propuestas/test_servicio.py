"""Tests for GenerarPropuestaAudiovisualService — RED phase."""

from __future__ import annotations

from garay.aplicacion.propuestas.servicio import GenerarPropuestaAudiovisualService


def test_reemplaza_nombre_empresa() -> None:
    svc = GenerarPropuestaAudiovisualService(plantilla="<h1>{{EMPRESA}}</h1>")
    assert svc.generar("Capri Beach Club") == "<h1>Capri Beach Club</h1>"


def test_reemplaza_logo_por_data_uri() -> None:
    svc = GenerarPropuestaAudiovisualService(
        plantilla='<img src="{{LOGO}}">',
        logo_data_uri="data:image/png;base64,AAA",
    )
    assert svc.generar("Acme") == '<img src="data:image/png;base64,AAA">'


def test_no_deja_placeholders_sin_resolver() -> None:
    svc = GenerarPropuestaAudiovisualService(
        plantilla="{{EMPRESA}} — {{LOGO}}",
        logo_data_uri="L",
    )
    salida = svc.generar("Acme S.A.S.")
    assert "{{EMPRESA}}" not in salida
    assert "{{LOGO}}" not in salida


def test_reemplaza_todas_las_ocurrencias_de_empresa() -> None:
    svc = GenerarPropuestaAudiovisualService(plantilla="{{EMPRESA}} y {{EMPRESA}}")
    assert svc.generar("X") == "X y X"
