"""Tests for dominio/comisiones/errores.py — task 1.1."""

from __future__ import annotations

import pytest


class TestPorcentajeReferidoSuperaTechoRemovido:
    """Task 1.1: PorcentajeReferidoSuperaTecho must NOT exist in the module."""

    def test_clase_no_existe_en_modulo(self) -> None:
        import garay.dominio.comisiones.errores as m

        assert not hasattr(m, "PorcentajeReferidoSuperaTecho"), (
            "PorcentajeReferidoSuperaTecho debe haber sido eliminada del módulo"
        )

    def test_importar_directo_falla(self) -> None:
        with pytest.raises(ImportError):
            from garay.dominio.comisiones.errores import PorcentajeReferidoSuperaTecho  # noqa: F401
