from __future__ import annotations

import uuid

import pytest

from garay.dominio.puertos.repositorios import (
    IngresoRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import ExtractorIA
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.dominio.ventas.entidades import Venta


class TestVentaRepository:
    def test_implementacion_cumple_interfaz(self) -> None:
        class _Impl(VentaRepository):
            def guardar(self, venta: Venta) -> None:
                pass

            def buscar_por_id(self, id: uuid.UUID) -> Venta | None:
                return None

            def listar(self) -> list[Venta]:
                return []

        assert isinstance(_Impl(), VentaRepository)

    def test_sin_implementar_no_se_puede_instanciar(self) -> None:
        class _Incompleto(VentaRepository):
            pass

        with pytest.raises(TypeError):
            _Incompleto()  # type: ignore[abstract]


class TestIngresoRepository:
    def test_implementacion_cumple_interfaz(self) -> None:
        from garay.dominio.conciliacion.entidades import Ingreso

        class _Impl(IngresoRepository):
            def guardar(self, ingreso: Ingreso) -> None:
                pass

            def buscar_por_id(self, id: uuid.UUID) -> Ingreso | None:
                return None

            def listar_sin_clasificar(self) -> list[Ingreso]:
                return []

        assert isinstance(_Impl(), IngresoRepository)

    def test_sin_implementar_no_se_puede_instanciar(self) -> None:
        class _Incompleto(IngresoRepository):
            pass

        with pytest.raises(TypeError):
            _Incompleto()  # type: ignore[abstract]


class TestExtractorIA:
    def test_implementacion_cumple_interfaz(self) -> None:
        from decimal import Decimal

        class _Impl(ExtractorIA):
            def extraer_de_foto(self, ruta_foto: str) -> DatosExtraidos:
                return DatosExtraidos(confianza=Decimal("1"))

        assert isinstance(_Impl(), ExtractorIA)

    def test_sin_implementar_no_se_puede_instanciar(self) -> None:
        class _Incompleto(ExtractorIA):
            pass

        with pytest.raises(TypeError):
            _Incompleto()  # type: ignore[abstract]
