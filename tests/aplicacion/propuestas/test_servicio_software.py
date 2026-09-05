"""Tests for GenerarPropuestaSoftwareService."""

from __future__ import annotations

from garay.aplicacion.propuestas.servicio_software import GenerarPropuestaSoftwareService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.propuestas.contexto import PreciosSoftware, PropuestaContexto


def test_llena_empresa_ejemplos_y_precios_con_derivados() -> None:
    plantilla = (
        "{{EMPRESA}}|{{EJEMPLOS_SERVICIOS}}|{{PRECIO_DESARROLLO}}|"
        "{{PRECIO_IMPLEMENTACION}}|{{PRECIO_MENSUAL}}|{{PRECIO_ANUAL}}|"
        "{{PRECIO_ANUAL_MES}}|{{PRECIO_AHORRO}}"
    )
    svc = GenerarPropuestaSoftwareService(plantilla=plantilla)
    out = svc.generar(PropuestaContexto(empresa_nombre="Acme"))
    # anual_mes = 5.000.000 / 12 ≈ 416.667 ; ahorro = 500.000*12 - 5.000.000 = 1.000.000
    assert out == (
        "Acme|reservas, mesas, servicios y eventos|24.000.000|"
        "2.000.000|500.000|5.000.000|416.667|1.000.000"
    )


def test_reemplaza_logo() -> None:
    svc = GenerarPropuestaSoftwareService(
        plantilla='<img src="{{LOGO}}">', logo_data_uri="data:image/png;base64,AAA"
    )
    assert svc.generar(PropuestaContexto(empresa_nombre="X")) == (
        '<img src="data:image/png;base64,AAA">'
    )


def test_precios_software_personalizados() -> None:
    ctx = PropuestaContexto(
        empresa_nombre="X",
        precios_software=PreciosSoftware(
            desarrollo=Dinero(30_000_000),
            implementacion=Dinero(3_000_000),
            mensual=Dinero(600_000),
            anual=Dinero(6_000_000),
        ),
    )
    svc = GenerarPropuestaSoftwareService(plantilla="{{PRECIO_ANUAL_MES}}|{{PRECIO_AHORRO}}")
    # 6.000.000/12 = 500.000 ; ahorro = 600.000*12 - 6.000.000 = 1.200.000
    assert svc.generar(ctx) == "500.000|1.200.000"


def test_ejemplos_personalizados() -> None:
    ctx = PropuestaContexto(empresa_nombre="X", ejemplos_servicios="citas y consultas")
    svc = GenerarPropuestaSoftwareService(plantilla="{{EJEMPLOS_SERVICIOS}}")
    assert svc.generar(ctx) == "citas y consultas"
