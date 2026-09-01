"""Unit tests for _formatear_mis_ventas — presentation of the MisVentas DTO.

All user-facing text comes from the message catalog (docs/ESTANDARES.md: mensajes
centralizados). Numbers/dates are data.
"""

from __future__ import annotations

import datetime

from garay.aplicacion.reportes.mis_ventas import LineaMisVentas, MisVentas
from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.telegram.handlers import _formatear_mis_ventas


def _mv(
    *,
    total: int = 0,
    valor: int = 0,
    comision: int = 0,
    realizados: tuple[LineaMisVentas, ...] = (),
    proximos: tuple[LineaMisVentas, ...] = (),
) -> MisVentas:
    return MisVentas(
        desde=datetime.date(2026, 9, 1),
        hoy=datetime.date(2026, 9, 15),
        total_ventas=total,
        valor_total=Dinero(valor),
        comision_total=Dinero(comision),
        realizados=realizados,
        proximos=proximos,
    )


def _linea(
    fecha: datetime.date,
    valor: int,
    *,
    varias: bool = False,
    canal: str | None = None,
) -> LineaMisVentas:
    return LineaMisVentas(
        fecha=fecha, valor=Dinero(valor), varias_fechas=varias, canal_origen=canal
    )


def test_vacio_muestra_mensaje() -> None:
    txt = _formatear_mis_ventas(_mv())
    assert "ventas" in txt.lower()


def test_incluye_totales_en_formato_cop() -> None:
    mv = _mv(
        total=2,
        valor=1_500_000,
        comision=30_000,
        realizados=(_linea(datetime.date(2026, 9, 10), 1_000_000),),
    )
    txt = _formatear_mis_ventas(mv)
    assert "$1.500.000" in txt
    assert "$30.000" in txt


def test_seccion_proximos_con_etiqueta_y_fecha() -> None:
    mv = _mv(
        total=1,
        valor=500_000,
        comision=10_000,
        proximos=(_linea(datetime.date(2026, 9, 20), 500_000),),
    )
    txt = _formatear_mis_ventas(mv)
    assert "Próximos" in txt
    assert "20/09" in txt


def test_realizados_y_proximos_en_secciones_separadas() -> None:
    mv = _mv(
        total=2,
        valor=1_500_000,
        comision=20_000,
        realizados=(_linea(datetime.date(2026, 9, 10), 1_000_000),),
        proximos=(_linea(datetime.date(2026, 9, 20), 500_000),),
    )
    txt = _formatear_mis_ventas(mv)
    assert "Realizados" in txt
    assert "Próximos" in txt
    assert "10/09" in txt
    assert "20/09" in txt
