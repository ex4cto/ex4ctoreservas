from __future__ import annotations

import uuid
from datetime import date

import pytest

from garay.dominio.puertos.repositorios import (
    FreelancerRepository,
    IngresoRepository,
    VentaRepository,
)
from garay.dominio.freelancers.entidades import Freelancer
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

            def listar_por_freelancer_y_periodo(
                self, nombre: str, desde: date, hasta: date
            ) -> list[Venta]:
                return []

            def listar_por_periodo(self, desde: date, hasta: date) -> list[Venta]:
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

            def existe_referencia(self, referencia: str) -> bool:
                return False

            def listar_recientes(self, minutos: int) -> list[Ingreso]:
                return []

            def listar_por_periodo(self, desde: date, hasta: date) -> list[Ingreso]:
                return []

        assert isinstance(_Impl(), IngresoRepository)

    def test_sin_implementar_no_se_puede_instanciar(self) -> None:
        class _Incompleto(IngresoRepository):
            pass

        with pytest.raises(TypeError):
            _Incompleto()  # type: ignore[abstract]


class TestFreelancerRepository:
    """Verify that FreelancerRepository ABC exposes the A1 contract.

    WU-1 scope: buscar_por_nombre is KEPT; three new methods are ADDED.
    buscar_por_nombre removal happens in WU-2.
    """

    def test_implementacion_cumple_interfaz_con_nuevos_metodos(self) -> None:
        class _Impl(FreelancerRepository):
            def guardar(self, freelancer: Freelancer) -> None:
                pass

            def buscar_por_id(self, id: uuid.UUID) -> Freelancer | None:
                return None

            def listar_activos(self) -> list[Freelancer]:
                return []

            def buscar_por_telegram_id(self, telegram_user_id: int) -> Freelancer | None:
                return None

            def buscar_por_nombre(self, nombre: str) -> Freelancer | None:
                return None

            def listar_todos(self) -> list[Freelancer]:
                return []

            # New A1 methods
            def buscar_por_cedula(self, cedula: str) -> Freelancer | None:
                return None

            def listar_por_nombre(self, nombre: str) -> list[Freelancer]:
                return []

            def buscar_por_telegram_id_cualquier_estado(
                self, telegram_user_id: int
            ) -> Freelancer | None:
                return None

        assert isinstance(_Impl(), FreelancerRepository)

    def test_sin_nuevos_metodos_no_instanciable(self) -> None:
        """Missing any of the 3 new abstractmethods → TypeError."""

        class _Incompleto(FreelancerRepository):
            def guardar(self, freelancer: Freelancer) -> None:
                pass

            def buscar_por_id(self, id: uuid.UUID) -> Freelancer | None:
                return None

            def listar_activos(self) -> list[Freelancer]:
                return []

            def buscar_por_telegram_id(self, telegram_user_id: int) -> Freelancer | None:
                return None

            def buscar_por_nombre(self, nombre: str) -> Freelancer | None:
                return None

            def listar_todos(self) -> list[Freelancer]:
                return []

            # Intentionally missing buscar_por_cedula, listar_por_nombre,
            # and buscar_por_telegram_id_cualquier_estado

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
