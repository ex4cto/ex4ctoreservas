"""Tests for GenerarFacturaService — pure HTML generation, no side effects."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from garay.aplicacion.factura.servicio import GenerarFacturaService
from garay.aplicacion.tiquetera.comandos import ResultadoRegistrarVenta
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta

_CERO = Dinero(Decimal("0"), "COP")
_SNAPSHOT = SnapshotReglas(
    tipo_cliente=TipoCliente.EXTERNO,
    porcentaje_vendedor=Decimal("0"),
    porcentaje_cerrador=Decimal("0"),
    porcentaje_referido_maximo=Decimal("0"),
    porcentaje_capa_punto=Decimal("0"),
)


def _resultado(venta_id: uuid.UUID | None = None) -> ResultadoRegistrarVenta:
    _id = venta_id or uuid.UUID("a3f7b200-0000-0000-0000-000000000000")
    return ResultadoRegistrarVenta(
        venta_id=_id,
        desglose=DesgloseComision(
            vendedor=_CERO,
            cerrador=_CERO,
            punto_de_venta=_CERO,
            referido=_CERO,
            agencia=_CERO,
            snapshot=_SNAPSHOT,
        ),
    )


def _ctx_completo() -> ContextoVenta:
    ctx = ContextoVenta()
    ctx.cliente_nombre = "Juan Perez"
    ctx.cliente_email = "juan@example.com"
    ctx.cliente_identificacion = "1234567890"
    ctx.cliente_tipo_identificacion = "CC"
    ctx.cliente_telefono = "+573001234567"
    ctx.fecha_salida = datetime.datetime(2026, 8, 15)
    ctx.valor = Decimal("500000")
    ctx.abono = Decimal("200000")
    ctx.neto = Decimal("300000")
    return ctx


def _venta_id(resultado: ResultadoRegistrarVenta | None = None) -> uuid.UUID:
    if resultado is not None:
        return resultado.venta_id
    return uuid.UUID("a3f7b200-0000-0000-0000-000000000000")


class TestGenerarFacturaHtml:
    def test_generar_devuelve_string_html(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert isinstance(html, str)
        assert len(html) > 100

    def test_html_contiene_nit_empresa(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "1128049588-6" in html

    def test_html_contiene_nombre_cliente(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "Juan Perez" in html

    def test_html_contiene_email_cliente(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "juan@example.com" in html

    def test_html_contiene_identificacion_cliente(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "1234567890" in html

    def test_html_tiene_page_break_para_segunda_pagina(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "page-break" in html

    def test_html_contiene_politicas_cancelacion(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert (
            "FORCE MAJEURE" in html
            or "fuerza mayor" in html.lower()
            or "FUERZA MAYOR" in html
            or "force majeure" in html.lower()
        )

    def test_numero_factura_formato_correcto(self) -> None:
        venta_id = uuid.UUID("a3f7b200-cafe-0000-0000-000000000000")
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), venta_id)
        # Format: GT-YYYYMMDD-XXXXXX
        assert "GT-" in html
        assert "-A3F7B2" in html

    def test_html_sin_logo_muestra_texto_empresa(self) -> None:
        servicio = GenerarFacturaService(logo_url="")
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "GARAY TOURS" in html

    def test_html_con_logo_incluye_img_tag(self) -> None:
        servicio = GenerarFacturaService(logo_url="data:image/png;base64,ABC123")
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "<img" in html
        assert "ABC123" in html

    def test_fmt_cop_formatea_correctamente(self) -> None:
        from garay.aplicacion.factura.servicio import _fmt_cop

        assert _fmt_cop(Decimal("500000")) == "$500.000"
        assert _fmt_cop(Decimal("1000000")) == "$1.000.000"
        assert _fmt_cop(None) == "$0"

    def test_fecha_emision_usa_zona_bogota(self) -> None:
        from unittest.mock import patch

        fecha_bogota = datetime.date(2026, 7, 29)
        with patch("garay.aplicacion.factura.servicio._hoy_bogota", return_value=fecha_bogota):
            servicio = GenerarFacturaService()
            html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "29/07/2026" in html

    def test_html_contiene_llave_bre_b(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "BRE-B" in html.upper()
        assert "@garay58804" in html

    def test_html_no_menciona_nequi(self) -> None:
        servicio = GenerarFacturaService()
        html = servicio.generar(_ctx_completo(), _venta_id(_resultado()))
        assert "nequi" not in html.lower()


class TestFacturaFechasPorTour:
    """Per-tour date rendering in the invoice 'Fecha del tour' cell (Slice 3)."""

    def test_single_tour_date_only(self) -> None:
        """One tour → '%d/%m/%Y', no name and no hour (byte-identical parity)."""
        ctx = _ctx_completo()
        ctx.destinos_numeros = [1]
        ctx.destinos_nombres = ["Islas del Rosario"]
        ctx.fecha_salida = datetime.datetime(2026, 8, 15, 8, 0)
        ctx.fechas_por_servicio = {1: datetime.datetime(2026, 8, 15, 8, 0)}
        html = GenerarFacturaService().generar(ctx, _venta_id(_resultado()))
        assert "15/08/2026" in html
        assert "Islas del Rosario 15/08 08:00" not in html

    def test_two_tours_compact_string_in_cell(self) -> None:
        """Two tours → compact 'nombre DD/MM HH:MM, ...' in the same cell."""
        ctx = _ctx_completo()
        ctx.destinos_numeros = [1, 2]
        ctx.destinos_nombres = ["Islas del Rosario", "Bahía Rumbera"]
        ctx.fecha_salida = datetime.datetime(2026, 8, 15, 8, 0)
        ctx.fechas_por_servicio = {
            1: datetime.datetime(2026, 8, 15, 8, 0),
            2: datetime.datetime(2026, 8, 15, 19, 0),
        }
        html = GenerarFacturaService().generar(ctx, _venta_id(_resultado()))
        assert (
            "Islas del Rosario 15/08 08:00, Bahía Rumbera 15/08 19:00" in html
        )

    def test_three_tours_compact_string_in_order(self) -> None:
        """Three tours render in destinos_numeros order."""
        ctx = _ctx_completo()
        ctx.destinos_numeros = [1, 2, 3]
        ctx.destinos_nombres = ["Islas del Rosario", "Bahía Rumbera", "City Tour"]
        ctx.fecha_salida = datetime.datetime(2026, 8, 10, 9, 0)
        ctx.fechas_por_servicio = {
            1: datetime.datetime(2026, 8, 15, 8, 0),
            2: datetime.datetime(2026, 8, 15, 19, 0),
            3: datetime.datetime(2026, 8, 10, 9, 0),
        }
        html = GenerarFacturaService().generar(ctx, _venta_id(_resultado()))
        assert (
            "Islas del Rosario 15/08 08:00, "
            "Bahía Rumbera 15/08 19:00, "
            "City Tour 10/08 09:00" in html
        )

    def test_multi_tour_missing_entry_falls_back_to_scalar(self) -> None:
        """Missing per-tour date falls back to the scalar for that tour."""
        ctx = _ctx_completo()
        ctx.destinos_numeros = [1, 2]
        ctx.destinos_nombres = ["Islas del Rosario", "Bahía Rumbera"]
        ctx.fecha_salida = datetime.datetime(2026, 8, 15, 8, 0)
        ctx.fechas_por_servicio = {1: datetime.datetime(2026, 8, 15, 8, 0)}
        html = GenerarFacturaService().generar(ctx, _venta_id(_resultado()))
        assert "Islas del Rosario 15/08 08:00" in html
        assert "Bahía Rumbera 15/08 08:00" in html

    def test_multi_tour_empty_fechas_degrades_to_scalar(self) -> None:
        """Two tours with fechas_por_servicio={} must degrade to scalar DD/MM/YYYY,
        not render '00:00' midnight artifacts from a dict-miss fallback."""
        ctx = _ctx_completo()
        ctx.destinos_numeros = [1, 2]
        ctx.destinos_nombres = ["Islas del Rosario", "Bahía Rumbera"]
        ctx.fecha_salida = datetime.datetime(2026, 8, 15, 8, 0)
        ctx.fechas_por_servicio = {}
        html = GenerarFacturaService().generar(ctx, _venta_id(_resultado()))
        assert "15/08/2026" in html
        assert "00:00" not in html
