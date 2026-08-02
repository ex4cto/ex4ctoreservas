"""RED tests — CedulaInvalida domain error."""

from __future__ import annotations

import pytest

from garay.dominio.comun.errores import ErrorDeDominio
from garay.dominio.freelancers.errores import CedulaInvalida, NombreFreelancerVacio


class TestCedulaInvalida:
    def test_es_subclase_de_error_de_dominio(self) -> None:
        assert issubclass(CedulaInvalida, ErrorDeDominio)

    def test_es_levantable(self) -> None:
        with pytest.raises(CedulaInvalida):
            raise CedulaInvalida("cedula invalida")

    def test_nombre_freelancer_vacio_sigue_siendo_subclase(self) -> None:
        """Regression: existing error must still work after adding CedulaInvalida."""
        assert issubclass(NombreFreelancerVacio, ErrorDeDominio)
