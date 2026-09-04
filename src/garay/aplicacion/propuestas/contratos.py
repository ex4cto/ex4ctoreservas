"""Servicios de generación de contratos (software y audiovisual).

Los datos legales del cliente vienen en ``ctx.datos_cliente``; los valores
comerciales se derivan de los precios ya recolectados; el número, la fecha y la
ciudad de firma son automáticos. EL CONTRATISTA y la firma son fijos.
"""

from __future__ import annotations

import datetime
import uuid
from zoneinfo import ZoneInfo

from garay.aplicacion.propuestas.formato import formatear_cop_simbolo
from garay.dominio.propuestas.contexto import (
    DatosCliente,
    PlanAudiovisual,
    PropuestaContexto,
)

_BOGOTA = ZoneInfo("America/Bogota")

# Etiquetas de cada plan audiovisual para el contrato.
_ETIQUETA_PLAN: dict[PlanAudiovisual, str] = {
    PlanAudiovisual.COMPLETO: "Máximo Alcance (28 videos)",
    PlanAudiovisual.MEDIO: "Alcance Esencial (14 videos)",
}


def _hoy_bogota() -> datetime.date:
    return datetime.datetime.now(_BOGOTA).date()


def _numero_contrato(fecha: datetime.date) -> str:
    return f"GT-C-{fecha:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _datos_o_vacios(datos: DatosCliente | None) -> DatosCliente:
    if datos is not None:
        return datos
    return DatosCliente(
        razon_social="", nit="", rep_legal="", rep_cc="", direccion="", ciudad=""
    )


def _reemplazos_comunes(
    ctx: PropuestaContexto, logo: str, firma: str, numero: str, fecha: datetime.date
) -> dict[str, str]:
    d = _datos_o_vacios(ctx.datos_cliente)
    return {
        "{{LOGO}}": logo,
        "{{FIRMA}}": firma,
        "{{NUMERO_CONTRATO}}": numero,
        "{{FECHA_FIRMA}}": fecha.strftime("%d/%m/%Y"),
        "{{CIUDAD_FIRMA}}": "Cartagena",
        "{{CONTRATANTE_RAZON_SOCIAL}}": d.razon_social,
        "{{CONTRATANTE_NIT}}": d.nit,
        "{{CONTRATANTE_REP_LEGAL}}": d.rep_legal,
        "{{CONTRATANTE_REP_CC}}": d.rep_cc,
        "{{CONTRATANTE_DIRECCION}}": d.direccion,
        "{{CONTRATANTE_CIUDAD}}": d.ciudad,
        "{{VIGENCIA}}": "doce (12) meses",
        "{{FECHA_INICIO}}": "la fecha de firma",
        "{{ALCANCE_RESUMEN}}": "según la propuesta comercial aceptada",
    }


def _aplicar(plantilla: str, reemplazos: dict[str, str]) -> str:
    for ph, valor in reemplazos.items():
        plantilla = plantilla.replace(ph, valor)
    return plantilla


class GenerarContratoSoftwareService:
    """Render the software license contract HTML."""

    def __init__(self, plantilla: str, logo_data_uri: str = "", firma_data_uri: str = "") -> None:
        self._plantilla = plantilla
        self._logo = logo_data_uri
        self._firma = firma_data_uri

    def generar(
        self,
        ctx: PropuestaContexto,
        numero: str | None = None,
        fecha: datetime.date | None = None,
    ) -> str:
        fecha = fecha or _hoy_bogota()
        numero = numero or _numero_contrato(fecha)
        reemplazos = _reemplazos_comunes(ctx, self._logo, self._firma, numero, fecha)
        p = ctx.precios_software
        reemplazos.update(
            {
                "{{VALOR_IMPLEMENTACION}}": formatear_cop_simbolo(p.implementacion.monto),
                "{{VALOR_LICENCIA}}": formatear_cop_simbolo(p.mensual.monto),
                "{{PERIODICIDAD}}": "mensual",
            }
        )
        return _aplicar(self._plantilla, reemplazos)


class GenerarContratoAudiovisualService:
    """Render the audiovisual production contract HTML."""

    def __init__(self, plantilla: str, logo_data_uri: str = "", firma_data_uri: str = "") -> None:
        self._plantilla = plantilla
        self._logo = logo_data_uri
        self._firma = firma_data_uri

    def generar(
        self,
        ctx: PropuestaContexto,
        numero: str | None = None,
        fecha: datetime.date | None = None,
    ) -> str:
        fecha = fecha or _hoy_bogota()
        numero = numero or _numero_contrato(fecha)
        reemplazos = _reemplazos_comunes(ctx, self._logo, self._firma, numero, fecha)
        if ctx.plan_audiovisual is PlanAudiovisual.MEDIO:
            valor = ctx.precios.medio.monto
        else:
            valor = ctx.precios.completo.monto
        reemplazos.update(
            {
                "{{PAQUETE}}": _ETIQUETA_PLAN[ctx.plan_audiovisual],
                "{{VALOR_MENSUAL}}": formatear_cop_simbolo(valor),
                "{{DIA_PAGO}}": "cinco (5)",
            }
        )
        return _aplicar(self._plantilla, reemplazos)
