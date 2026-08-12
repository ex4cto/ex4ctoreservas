"""Tests for Bug Fix: the invoice HTML must render purchased tour name(s).

ROOT CAUSE: GenerarFacturaService.generar() had no row in the "Detalle del
servicio" table that rendered the tour/servicio name. The fix adds a "Tour"
row as the FIRST row in that table.

Scenarios:
  - Single tour: HTML contains the tour name.
  - Multiple tours: HTML contains the joined tour names.
  - Empty destinos_nombres: HTML renders "—" (no crash, no blank value).
"""

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


def _resultado() -> ResultadoRegistrarVenta:
    return ResultadoRegistrarVenta(
        venta_id=uuid.UUID("a3f7b200-0000-0000-0000-000000000000"),
        desglose=DesgloseComision(
            vendedor=_CERO,
            cerrador=_CERO,
            punto_de_venta=_CERO,
            referido=_CERO,
            agencia=_CERO,
            snapshot=_SNAPSHOT,
        ),
    )


def _ctx_base() -> ContextoVenta:
    ctx = ContextoVenta()
    ctx.cliente_nombre = "Maria Perez"
    ctx.cliente_email = "maria@example.com"
    ctx.cliente_identificacion = "9876543210"
    ctx.cliente_tipo_identificacion = "CC"
    ctx.cliente_telefono = "+573009876543"
    ctx.fecha_salida = datetime.datetime(2026, 9, 1)
    ctx.valor = Decimal("400000")
    ctx.abono = Decimal("100000")
    ctx.neto = Decimal("300000")
    return ctx


class TestFacturaTourNombre:
    """The 'Detalle del servicio' table must include a Tour row."""

    def test_single_tour_name_appears_in_html(self) -> None:
        """destinos_nombres=['Tour Playa Blanca'] → 'Tour Playa Blanca' in HTML."""
        ctx = _ctx_base()
        ctx.destinos_nombres = ["Tour Playa Blanca"]
        html = GenerarFacturaService().generar(ctx, _resultado().venta_id)
        assert "Tour Playa Blanca" in html

    def test_two_tours_names_joined_in_html(self) -> None:
        """Triangulation: two tours → joined string in HTML."""
        ctx = _ctx_base()
        ctx.destinos_nombres = ["Islas del Rosario", "Bahía Rumbera"]
        html = GenerarFacturaService().generar(ctx, _resultado().venta_id)
        assert "Islas del Rosario, Bahía Rumbera" in html

    def test_empty_destinos_nombres_renders_dash(self) -> None:
        """destinos_nombres=[] → HTML contains '—' (dash), no crash, no blank cell."""
        ctx = _ctx_base()
        ctx.destinos_nombres = []
        html = GenerarFacturaService().generar(ctx, _resultado().venta_id)
        # Must not raise; must render the dash
        assert "—" in html

    def test_tour_row_label_present(self) -> None:
        """The label 'Tour' must appear in the Detalle section."""
        ctx = _ctx_base()
        ctx.destinos_nombres = ["Tour Playa Blanca"]
        html = GenerarFacturaService().generar(ctx, _resultado().venta_id)
        assert ">Tour<" in html or "Tour</td>" in html or ">Tour " in html

    def test_tour_row_before_fecha_row(self) -> None:
        """The Tour row must appear BEFORE the 'Fecha del tour' row in the HTML."""
        ctx = _ctx_base()
        ctx.destinos_nombres = ["Tour Playa Blanca"]
        html = GenerarFacturaService().generar(ctx, _resultado().venta_id)
        tour_pos = html.find("Tour Playa Blanca")
        fecha_pos = html.find("Fecha del tour")
        assert tour_pos != -1
        assert fecha_pos != -1
        assert tour_pos < fecha_pos
