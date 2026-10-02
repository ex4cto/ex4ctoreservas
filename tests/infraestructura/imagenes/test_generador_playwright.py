"""Integration test for PlaywrightGeneradorImagen.

Marked as integration — only runs when Chromium is available.
Skipped automatically in environments without Playwright/Chromium.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.servicios.entidades import Servicio, TipoImagen


def _servicio(numero: int = 1, categoria: str = "TEST") -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=numero,
        nombre=f"Tour Test {numero}",
        categoria=categoria,
        activo=True,
        precio_neto_adulto=Decimal("30000"),
        precio_neto_nino=Decimal("20000"),
        precio_sugerido_adulto=Decimal("50000"),
        permite_ninos=True,
    )


# Skip this whole module if playwright is not installed
playwright = pytest.importorskip("playwright", reason="playwright not installed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_genera_imagen_interna_devuelve_png() -> None:
    """PlaywrightGeneradorImagen returns raw PNG bytes for INTERNA view."""
    from garay.infraestructura.imagenes.generador_playwright import PlaywrightGeneradorImagen

    generador = PlaywrightGeneradorImagen()
    servicios = [_servicio(1, "PLAYERO"), _servicio(2, "CIUDAD")]
    result = await generador.generar_imagen_precios(servicios, TipoImagen.INTERNA)

    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG", f"Expected PNG magic bytes, got: {result[:8]!r}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_genera_imagen_turista_devuelve_png() -> None:
    """PlaywrightGeneradorImagen returns raw PNG bytes for TURISTA view."""
    from garay.infraestructura.imagenes.generador_playwright import PlaywrightGeneradorImagen

    generador = PlaywrightGeneradorImagen()
    servicios = [_servicio(1, "PLAYERO")]
    result = await generador.generar_imagen_precios(servicios, TipoImagen.TURISTA)

    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG", f"Expected PNG magic bytes, got: {result[:8]!r}"
