"""GenerarCuentaCobroService — genera PDF cuenta de cobro para Isla Palma.

CTG Tours SAS emite la cuenta de cobro a favor de Julio César Garay Manzur
por las comisiones de ventas de Isla Palma del día indicado.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from garay.aplicacion.comun.formato import fmt_cop
from garay.aplicacion.operadores.notificaciones import detectar_operador
from garay.dominio.comun.dinero import Dinero

if TYPE_CHECKING:
    from garay.config.settings import Settings
    from garay.dominio.puertos.repositorios import (
        ComisionRegistradaRepository,
        ServicioRepository,
        VentaRepository,
    )
    from garay.dominio.ventas.entidades import Venta
    from garay.infraestructura.persistencia.contador_cobro_sql import (
        ContadorDocumentoSQLAlchemy,
    )

logger = logging.getLogger(__name__)

_TIPO_CONTADOR = "cuenta_cobro_isla_palma"


@dataclass
class ResultadoCuentaCobro:
    """Payload returned after successfully generating a cuenta de cobro."""

    numero: int
    fecha: datetime.date
    ganancia: Dinero
    num_ventas: int
    pdf_bytes: bytes


class GenerarCuentaCobroService:
    """Queries Isla Palma ventas for a date, increments the counter, renders PDF."""

    def __init__(
        self,
        ventas_repo: VentaRepository,
        servicio_repo: ServicioRepository,
        contador: ContadorDocumentoSQLAlchemy,
        renderer: object,
        assets_path: Path,
        settings: Settings,
    ) -> None:
        self._ventas = ventas_repo
        self._servicios = servicio_repo
        self._contador = contador
        self._renderer = renderer
        self._assets_path = assets_path
        self._settings = settings

    def buscar_ventas_isla_palma(self, fecha: datetime.date) -> list[Venta]:
        """Return ventas for Isla Palma services on the given date."""
        servicios = self._servicios.listar_activos()
        isla_palma_ids = {
            s.id
            for s in servicios
            if detectar_operador([s.nombre]) == "isla_palma"
        }
        if not isla_palma_ids:
            return []
        ventas = self._ventas.listar_por_periodo(fecha, fecha)
        return [
            v for v in ventas
            if any(sid in isla_palma_ids for sid in v.servicio_ids)
        ]

    async def ejecutar(
        self,
        fecha: datetime.date,
        comisiones_repo: ComisionRegistradaRepository,
    ) -> ResultadoCuentaCobro:
        """Generate the cuenta de cobro PDF for Isla Palma sales on *fecha*.

        Raises:
            ValueError: When no Isla Palma ventas exist for *fecha*.
        """
        ventas = self.buscar_ventas_isla_palma(fecha)
        if not ventas:
            raise ValueError("No hay ventas de Isla Palma para esa fecha.")

        # Sum agency commission across ventas using ComisionRegistradaRepository.
        ganancia_total = Dinero(0)
        for venta in ventas:
            comision = comisiones_repo.buscar_por_venta_id(venta.id)
            if comision is not None:
                ganancia_total = ganancia_total + comision.desglose.agencia
            else:
                # Fallback: use neto when no registered commission exists.
                logger.warning(
                    "No commission found for venta %s — using neto as fallback",
                    venta.id,
                )
                ganancia_total = ganancia_total + venta.neto

        numero = self._contador.siguiente_numero(_TIPO_CONTADOR)
        pdf_bytes = await self._render_pdf(numero, fecha, ganancia_total)

        return ResultadoCuentaCobro(
            numero=numero,
            fecha=fecha,
            ganancia=ganancia_total,
            num_ventas=len(ventas),
            pdf_bytes=pdf_bytes,
        )

    async def _render_pdf(
        self,
        numero: int,
        fecha: datetime.date,
        ganancia: Dinero,
    ) -> bytes:
        """Render the Jinja2 HTML template to PDF via Playwright."""
        import jinja2
        from playwright.async_api import async_playwright

        templates_dir = Path(__file__).parent.parent.parent / "infraestructura" / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=jinja2.select_autoescape(["html"]),
        )
        env.filters["fmt_cop"] = lambda v: fmt_cop(v)

        firma_path = self._assets_path / "firma garay.jpg"

        template = env.get_template("cuenta_cobro_isla_palma.html.jinja2")
        fecha_str = fecha.strftime("%d de %B de %Y")
        html = template.render(
            numero=numero,
            fecha=fecha_str,
            ganancia=fmt_cop(ganancia),
            empresa_nombre=self._settings.ctours_empresa,
            nit=self._settings.ctours_nit,
            cuenta_cobro=self._settings.ctours_cuenta_cobro,
            garay_nombre=self._settings.garay_nombre,
            garay_cc=self._settings.garay_cc,
            garay_tel=self._settings.garay_tel,
            garay_email=self._settings.garay_email,
            garay_direccion=self._settings.garay_direccion,
            firma_path=str(firma_path).replace("\\", "/"),
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="networkidle")
                pdf: bytes = await page.pdf(
                    format="A4",
                    margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                    print_background=True,
                )
            finally:
                await browser.close()

        return pdf
