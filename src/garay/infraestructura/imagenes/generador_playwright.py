"""Playwright + Jinja2 adapter implementing GeneradorListaPreciosPort.

Renders lista_precios.html to a PNG screenshot using a headless Chromium browser.
No temp files — returns raw in-memory PNG bytes via locator screenshot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from garay.dominio.puertos.generador_lista_precios import GeneradorListaPreciosPort
from garay.dominio.servicios.entidades import Servicio, TipoImagen

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_LOGO_FILENAME = "Gemini_Generated_Image_liebc8liebc8lieb.jpg"
_LOGO_PATH = Path(__file__).parent.parent.parent.parent.parent / "assets" / _LOGO_FILENAME


def _fmt_cop(value: object) -> str:
    """Format a Decimal price as Colombian peso string, e.g. $150.000."""
    from decimal import Decimal

    if value is None:
        return "—"
    try:
        d = Decimal(str(value))
        # Format as integer with thousands separator (Colombian style).
        entero = int(d)
        return f"${entero:,}".replace(",", ".")
    except Exception:
        return str(value)


def _build_jinja_env() -> Any:
    """Build a Jinja2 Environment with FileSystemLoader and custom filter."""
    import jinja2

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    env.filters["fmt_cop"] = _fmt_cop
    return env


class PlaywrightGeneradorImagen(GeneradorListaPreciosPort):
    """Renders the price list to a PNG screenshot using headless Chromium.

    Uses async_playwright so it integrates cleanly with the asyncio event loop
    used by PTB and the standalone scripts.
    """

    async def generar_imagen_precios(
        self, servicios: list[Servicio], tipo: TipoImagen
    ) -> bytes:
        """Render lista_precios.html for *tipo* and return the PNG screenshot bytes.

        Args:
            servicios: Filtered list of active services with prices set.
            tipo: TipoImagen.INTERNA or TipoImagen.TURISTA.

        Returns:
            Raw PNG bytes from Playwright's locator screenshot.
        """
        from playwright.async_api import async_playwright

        env = _build_jinja_env()
        template = env.get_template("lista_precios.html")
        logo_url = _LOGO_PATH.as_uri() if _LOGO_PATH.exists() else ""
        html = template.render(servicios=servicios, tipo=tipo.value, logo_url=logo_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1200, "height": 2400})
                await page.set_content(html, wait_until="networkidle")
                png_bytes: bytes = await page.locator("#lista").screenshot(type="png")
            finally:
                await browser.close()

        return png_bytes
