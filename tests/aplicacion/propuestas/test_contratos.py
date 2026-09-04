"""Tests for the contract generation services."""

from __future__ import annotations

import datetime

from garay.aplicacion.propuestas.contratos import (
    GenerarContratoAudiovisualService,
    GenerarContratoSoftwareService,
)
from garay.dominio.propuestas.contexto import (
    DatosCliente,
    PlanAudiovisual,
    PropuestaContexto,
)

_DATOS = DatosCliente(
    razon_social="Clinica Sonrisa SAS",
    nit="900123456-7",
    rep_legal="Ana Perez",
    rep_cc="43.111.222",
    direccion="Cra 1 #2-3",
    ciudad="Medellin",
)
_FECHA = datetime.date(2026, 9, 4)


def _ctx(**kw: object) -> PropuestaContexto:
    return PropuestaContexto(empresa_nombre="Clinica Sonrisa", datos_cliente=_DATOS, **kw)


def test_contrato_software_llena_legal_y_deriva_precios() -> None:
    plantilla = (
        "{{NUMERO_CONTRATO}}|{{FECHA_FIRMA}}|{{CIUDAD_FIRMA}}|"
        "{{CONTRATANTE_RAZON_SOCIAL}}|{{CONTRATANTE_NIT}}|{{CONTRATANTE_REP_LEGAL}}|"
        "{{CONTRATANTE_REP_CC}}|{{CONTRATANTE_DIRECCION}}|{{CONTRATANTE_CIUDAD}}|"
        "{{VALOR_IMPLEMENTACION}}|{{VALOR_LICENCIA}}|{{PERIODICIDAD}}|"
        "{{VIGENCIA}}|{{FECHA_INICIO}}|{{ALCANCE_RESUMEN}}|{{LOGO}}|{{FIRMA}}"
    )
    svc = GenerarContratoSoftwareService(plantilla, logo_data_uri="LOGO", firma_data_uri="FIRMA")
    out = svc.generar(_ctx(), numero="GT-C-X", fecha=_FECHA)
    assert out == (
        "GT-C-X|04/09/2026|Cartagena|"
        "Clinica Sonrisa SAS|900123456-7|Ana Perez|"
        "43.111.222|Cra 1 #2-3|Medellin|"
        "$2.000.000|$500.000|mensual|"
        "doce (12) meses|la fecha de firma|según la propuesta comercial aceptada|LOGO|FIRMA"
    )


def test_contrato_audiovisual_completo() -> None:
    svc = GenerarContratoAudiovisualService("{{PAQUETE}}|{{VALOR_MENSUAL}}|{{DIA_PAGO}}")
    out = svc.generar(_ctx(plan_audiovisual=PlanAudiovisual.COMPLETO), numero="X", fecha=_FECHA)
    assert out == "Máximo Alcance (28 videos)|$3.000.000|cinco (5)"


def test_contrato_audiovisual_medio() -> None:
    svc = GenerarContratoAudiovisualService("{{PAQUETE}}|{{VALOR_MENSUAL}}")
    out = svc.generar(_ctx(plan_audiovisual=PlanAudiovisual.MEDIO), numero="X", fecha=_FECHA)
    assert out == "Alcance Esencial (14 videos)|$1.800.000"


def test_numero_contrato_autogenerado() -> None:
    svc = GenerarContratoSoftwareService("{{NUMERO_CONTRATO}}")
    out = svc.generar(_ctx(), fecha=_FECHA)
    assert out.startswith("GT-C-20260904-")
    assert len(out) == len("GT-C-20260904-") + 6


def test_sin_datos_cliente_no_crashea() -> None:
    svc = GenerarContratoSoftwareService("{{CONTRATANTE_NIT}}")
    ctx = PropuestaContexto(empresa_nombre="X")  # datos_cliente None
    assert svc.generar(ctx, numero="X", fecha=_FECHA) == ""
