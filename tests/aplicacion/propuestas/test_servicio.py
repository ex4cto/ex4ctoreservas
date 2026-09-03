"""Tests for GenerarPropuestaAudiovisualService."""

from __future__ import annotations

from garay.aplicacion.propuestas.servicio import GenerarPropuestaAudiovisualService
from garay.dominio.propuestas.contexto import PropuestaContexto


def _ctx(nombre: str) -> PropuestaContexto:
    return PropuestaContexto(empresa_nombre=nombre)


def test_reemplaza_nombre_empresa() -> None:
    svc = GenerarPropuestaAudiovisualService(plantilla="<h1>{{EMPRESA}}</h1>")
    assert svc.generar(_ctx("Capri Beach Club")) == "<h1>Capri Beach Club</h1>"


def test_reemplaza_logo_por_data_uri() -> None:
    svc = GenerarPropuestaAudiovisualService(
        plantilla='<img src="{{LOGO}}">',
        logo_data_uri="data:image/png;base64,AAA",
    )
    assert svc.generar(_ctx("Acme")) == '<img src="data:image/png;base64,AAA">'


def test_no_deja_placeholders_sin_resolver() -> None:
    svc = GenerarPropuestaAudiovisualService(
        plantilla="{{EMPRESA}} — {{LOGO}}",
        logo_data_uri="L",
    )
    salida = svc.generar(_ctx("Acme S.A.S."))
    assert "{{EMPRESA}}" not in salida
    assert "{{LOGO}}" not in salida


def test_reemplaza_todas_las_ocurrencias_de_empresa() -> None:
    svc = GenerarPropuestaAudiovisualService(plantilla="{{EMPRESA}} y {{EMPRESA}}")
    assert svc.generar(_ctx("X")) == "X y X"


def test_formatea_precios_por_defecto_en_cop() -> None:
    plantilla = "{{PRECIO_COMPLETO}}|{{PRECIO_MEDIO}}|{{PRECIO_COMMUNITY}}|{{PRECIO_TRAFFICKER}}"
    svc = GenerarPropuestaAudiovisualService(plantilla=plantilla)
    assert svc.generar(_ctx("X")) == "3.000.000|1.800.000|500.000|600.000"


def test_precios_personalizados_se_formatean() -> None:
    from garay.dominio.comun.dinero import Dinero
    from garay.dominio.propuestas.contexto import PreciosAudiovisual, PropuestaContexto

    ctx = PropuestaContexto(
        empresa_nombre="X",
        precios=PreciosAudiovisual(
            completo=Dinero(4_500_000),
            medio=Dinero(2_250_000),
            community=Dinero(500_000),
            trafficker=Dinero(600_000),
        ),
    )
    svc = GenerarPropuestaAudiovisualService(plantilla="{{PRECIO_COMPLETO}} / {{PRECIO_MEDIO}}")
    assert svc.generar(ctx) == "4.500.000 / 2.250.000"
