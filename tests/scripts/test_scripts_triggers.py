"""Tests for lista_precios trigger points in scripts.

Verifies that asyncio.run(publicar_seguro(...)) is called:
  - In actualizar_precios_servicios.main() when NOT dry-run
  - In actualizar_precios_servicios.main() it is NOT called on dry-run
  - In sincronizar_catalogo.main() when NOT dry-run
  - In sincronizar_catalogo.main() it is NOT called on dry-run

TDD RED: written before the trigger code is added to scripts.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestActualizarPreciosServicios:
    """Trigger in actualizar_precios_servicios.main()."""

    def test_main_triggers_publicar_when_not_dry_run(self) -> None:
        """main() calls asyncio.run(publicar_seguro(...)) when --dry-run is not set."""
        from scripts.actualizar_precios_servicios import main

        mock_engine = MagicMock()
        mock_sf = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: s
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_sf.return_value = mock_session

        mock_resumen = MagicMock()
        mock_resumen.actualizados = []
        mock_resumen.sin_cambios = []
        mock_resumen.no_encontrados = []

        with (
            patch("sys.argv", ["script"]),  # no --dry-run
            patch("scripts.actualizar_precios_servicios.obtener_settings") as mock_settings,
            patch("scripts.actualizar_precios_servicios.crear_engine", return_value=mock_engine),
            patch("scripts.actualizar_precios_servicios.crear_fabrica_sesiones", return_value=mock_sf),
            patch("scripts.actualizar_precios_servicios.cargar_entries", return_value=[]),
            patch("scripts.actualizar_precios_servicios.actualizar_precios", return_value=mock_resumen),
            patch("asyncio.run") as mock_asyncio_run,
        ):
            mock_settings.return_value.database_url = "sqlite:///:memory:"
            main()

        mock_asyncio_run.assert_called_once()

    def test_main_no_trigger_on_dry_run(self) -> None:
        """main() does NOT call asyncio.run(publicar_seguro(...)) with --dry-run."""
        from scripts.actualizar_precios_servicios import main

        mock_engine = MagicMock()
        mock_sf = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: s
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_sf.return_value = mock_session

        mock_resumen = MagicMock()
        mock_resumen.actualizados = []
        mock_resumen.sin_cambios = []
        mock_resumen.no_encontrados = []

        with (
            patch("sys.argv", ["script", "--dry-run"]),
            patch("scripts.actualizar_precios_servicios.obtener_settings") as mock_settings,
            patch("scripts.actualizar_precios_servicios.crear_engine", return_value=mock_engine),
            patch("scripts.actualizar_precios_servicios.crear_fabrica_sesiones", return_value=mock_sf),
            patch("scripts.actualizar_precios_servicios.cargar_entries", return_value=[]),
            patch("scripts.actualizar_precios_servicios.actualizar_precios", return_value=mock_resumen),
            patch("asyncio.run") as mock_asyncio_run,
        ):
            mock_settings.return_value.database_url = "sqlite:///:memory:"
            main()

        mock_asyncio_run.assert_not_called()


class TestSincronizarCatalogo:
    """Trigger in sincronizar_catalogo.main()."""

    def test_main_triggers_publicar_when_not_dry_run(self) -> None:
        """main() calls asyncio.run(publicar_seguro(...)) when --dry-run is not set."""
        from scripts.sincronizar_catalogo import main

        mock_engine = MagicMock()
        mock_sf = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: s
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_sf.return_value = mock_session

        mock_resumen = MagicMock()
        mock_resumen.actualizados = []
        mock_resumen.sin_cambios = []
        mock_resumen.insertados = []

        with (
            patch("sys.argv", ["script"]),  # no --dry-run
            patch("scripts.sincronizar_catalogo.obtener_settings") as mock_settings,
            patch("scripts.sincronizar_catalogo.crear_engine", return_value=mock_engine),
            patch("scripts.sincronizar_catalogo.crear_fabrica_sesiones", return_value=mock_sf),
            patch("scripts.sincronizar_catalogo.cargar_entries", return_value=[]),
            patch("scripts.sincronizar_catalogo.sincronizar_catalogo", return_value=mock_resumen),
            patch("asyncio.run") as mock_asyncio_run,
        ):
            mock_settings.return_value.database_url = "sqlite:///:memory:"
            main()

        mock_asyncio_run.assert_called_once()

    def test_main_no_trigger_on_dry_run(self) -> None:
        """main() does NOT call asyncio.run(publicar_seguro(...)) with --dry-run."""
        from scripts.sincronizar_catalogo import main

        mock_engine = MagicMock()
        mock_sf = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: s
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_sf.return_value = mock_session

        mock_resumen = MagicMock()
        mock_resumen.actualizados = []
        mock_resumen.sin_cambios = []
        mock_resumen.insertados = []

        with (
            patch("sys.argv", ["script", "--dry-run"]),
            patch("scripts.sincronizar_catalogo.obtener_settings") as mock_settings,
            patch("scripts.sincronizar_catalogo.crear_engine", return_value=mock_engine),
            patch("scripts.sincronizar_catalogo.crear_fabrica_sesiones", return_value=mock_sf),
            patch("scripts.sincronizar_catalogo.cargar_entries", return_value=[]),
            patch("scripts.sincronizar_catalogo.sincronizar_catalogo", return_value=mock_resumen),
            patch("asyncio.run") as mock_asyncio_run,
        ):
            mock_settings.return_value.database_url = "sqlite:///:memory:"
            main()

        mock_asyncio_run.assert_not_called()
