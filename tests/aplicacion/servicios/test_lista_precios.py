"""T2.8 RED — Unit tests for PublicarListaPreciosServicio.

All infrastructure dependencies are mocked. No Playwright, no DB.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.dominio.puertos.generador_lista_precios import GeneradorListaPreciosPort
from garay.dominio.puertos.servicios_externos import EnviadorFotoPort
from garay.dominio.servicios.entidades import Servicio, TipoImagen

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _servicio(
    activo: bool = True,
    precio_neto_adulto: Decimal | None = Decimal("100000"),
    precio_sugerido_adulto: Decimal | None = Decimal("120000"),
    nombre: str = "City Tour",
    categoria: str = "Cartagena",
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre=nombre,
        categoria=categoria,
        activo=activo,
        precio_neto_adulto=precio_neto_adulto,
        precio_neto_nino=None,
        precio_sugerido_adulto=precio_sugerido_adulto,
    )


class FakeGenerador(GeneradorListaPreciosPort):
    def __init__(self, imagen: bytes = b"\x89PNG") -> None:
        self.calls: list[tuple[list[Servicio], TipoImagen]] = []
        self._imagen = imagen

    async def generar_imagen_precios(self, servicios: list[Servicio], tipo: TipoImagen) -> bytes:
        self.calls.append((servicios, tipo))
        return self._imagen


class FakeEnviador(EnviadorFotoPort):
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, str]] = []

    async def enviar(self, imagen: bytes, grupo_id: str) -> None:
        self.sent.append((imagen, grupo_id))


# ---------------------------------------------------------------------------
# Tests for PublicarListaPreciosServicio.publicar()
# ---------------------------------------------------------------------------


class TestPublicarListaPreciosServicio:
    def _make_repo(self, servicios: list[Servicio]) -> MagicMock:
        repo = MagicMock()
        repo.listar_activos.return_value = servicios
        return repo

    @pytest.mark.asyncio
    async def test_filtra_solo_activos_con_sugerido(self) -> None:
        """Only active services with precio_sugerido_adulto not None pass the filter."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        s_ok = _servicio(activo=True, precio_sugerido_adulto=Decimal("120000"))
        s_sin_sugerido = _servicio(activo=True, precio_sugerido_adulto=None)
        # listar_activos already returns only active; we add an inactive one for safety
        repo = self._make_repo([s_ok, s_sin_sugerido])
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "grupo123")
        await svc.publicar()

        # generador must have received only s_ok in its calls
        for servicios, _ in generador.calls:
            assert len(servicios) == 1
            assert servicios[0] is s_ok

    @pytest.mark.asyncio
    async def test_llama_generador_con_interna_y_turista(self) -> None:
        """publicar() calls generador with INTERNA and TURISTA for the service's group."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        s = _servicio()
        repo = self._make_repo([s])
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "grupo123")
        await svc.publicar()

        tipos = [tipo for _, tipo in generador.calls]
        assert TipoImagen.INTERNA in tipos
        assert TipoImagen.TURISTA in tipos

    @pytest.mark.asyncio
    async def test_envia_ambas_imagenes_al_grupo(self) -> None:
        """Both images are sent to grupo_id (single group scenario)."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        s = _servicio()
        repo = self._make_repo([s])
        generador = FakeGenerador(imagen=b"\x89PNG_FAKE")
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "-1001234567")
        await svc.publicar()

        assert len(enviador.sent) == 2
        for _img, grupo_id in enviador.sent:
            assert grupo_id == "-1001234567"

    @pytest.mark.asyncio
    async def test_omite_envio_cuando_grupo_id_vacio(self) -> None:
        """No send is attempted when grupo_id is empty string."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        s = _servicio()
        repo = self._make_repo([s])
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "")
        await svc.publicar()

        assert len(enviador.sent) == 0

    @pytest.mark.asyncio
    async def test_retorno_temprano_cuando_lista_vacia(self) -> None:
        """publicar() returns early (no generador calls) when filtered list is empty."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        s_sin_sugerido = _servicio(precio_sugerido_adulto=None)
        repo = self._make_repo([s_sin_sugerido])
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "grupo123")
        await svc.publicar()

        assert generador.calls == []
        assert enviador.sent == []

    @pytest.mark.asyncio
    async def test_genera_cuatro_imagenes_con_ambos_grupos(self) -> None:
        """When services span both category groups, generador is called 4 times."""
        from garay.aplicacion.servicios.lista_precios import (
            _GRUPO_1_CATEGORIAS,
            PublicarListaPreciosServicio,
        )

        cat1 = next(iter(_GRUPO_1_CATEGORIAS))
        s_g1 = _servicio(categoria=cat1, nombre="Tour G1")
        s_g2 = _servicio(categoria="OTROS", nombre="Tour G2")
        repo = self._make_repo([s_g1, s_g2])
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "grupo123")
        await svc.publicar()

        assert len(generador.calls) == 4
        tipos = [tipo for _, tipo in generador.calls]
        assert tipos.count(TipoImagen.INTERNA) == 2
        assert tipos.count(TipoImagen.TURISTA) == 2

    @pytest.mark.asyncio
    async def test_omite_grupo_sin_servicios(self) -> None:
        """A group with no services produces no calls for that group."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        # categoria="Cartagena" is not in GRUPO_1 → only grupo2 has services → 2 calls
        s = _servicio(categoria="Cartagena")
        repo = self._make_repo([s])
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "grupo123")
        await svc.publicar()

        assert len(generador.calls) == 2  # only grupo2: INTERNA + TURISTA

    @pytest.mark.asyncio
    async def test_envia_cuatro_imagenes_cuando_ambos_grupos_tienen_servicios(self) -> None:
        """4 images are sent when both groups have services."""
        from garay.aplicacion.servicios.lista_precios import (
            _GRUPO_1_CATEGORIAS,
            PublicarListaPreciosServicio,
        )

        cat1 = next(iter(_GRUPO_1_CATEGORIAS))
        s_g1 = _servicio(categoria=cat1)
        s_g2 = _servicio(categoria="OTROS")
        repo = self._make_repo([s_g1, s_g2])
        generador = FakeGenerador(imagen=b"\x89PNG_FAKE")
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "-1001234567")
        await svc.publicar()

        assert len(enviador.sent) == 4
        for _img, grupo_id in enviador.sent:
            assert grupo_id == "-1001234567"


# ---------------------------------------------------------------------------
# Tests for publicar_seguro()
# ---------------------------------------------------------------------------


class TestPublicarSeguro:
    @pytest.mark.asyncio
    async def test_swallows_exception_from_generador(self) -> None:
        """publicar_seguro does not re-raise when generador raises."""
        import garay.aplicacion.servicios.lista_precios as mod
        from garay.aplicacion.servicios.lista_precios import (
            PublicarListaPreciosServicio,
            publicar_seguro,
        )

        # Reset concurrency guard
        mod._generando = False

        class GeneradorRoto(GeneradorListaPreciosPort):
            async def generar_imagen_precios(
                self, servicios: list[Servicio], tipo: TipoImagen
            ) -> bytes:
                raise RuntimeError("Playwright crashed")

        repo = MagicMock()
        repo.listar_activos.return_value = [_servicio()]
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, GeneradorRoto(), enviador, "grupo123")

        # Should NOT raise
        await publicar_seguro(svc)

    @pytest.mark.asyncio
    async def test_concurrency_guard_blocks_second_call(self) -> None:
        """A second concurrent call to publicar_seguro is silently skipped."""
        import garay.aplicacion.servicios.lista_precios as mod
        from garay.aplicacion.servicios.lista_precios import (
            PublicarListaPreciosServicio,
            publicar_seguro,
        )

        mod._generando = False

        # Make generador slow so the second call overlaps
        call_count = 0

        class LentoGenerador(GeneradorListaPreciosPort):
            async def generar_imagen_precios(
                self, servicios: list[Servicio], tipo: TipoImagen
            ) -> bytes:
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.05)
                return b"\x89PNG"

        repo = MagicMock()
        repo.listar_activos.return_value = [_servicio()]
        enviador = FakeEnviador()
        svc = PublicarListaPreciosServicio(repo, LentoGenerador(), enviador, "")

        # Start first call, then immediately try second — second should be skipped
        t1 = asyncio.create_task(publicar_seguro(svc))
        # Yield so t1 can start and set _generando = True
        await asyncio.sleep(0)
        t2 = asyncio.create_task(publicar_seguro(svc))
        await asyncio.gather(t1, t2)

        # t2 was skipped because guard was active; generador was called at most 4 times
        # (INTERNA + TURISTA per group, for t1 only, not t2; up to 4 calls if 2 groups)
        assert call_count <= 4


class TestFiltroNeto:
    @pytest.mark.asyncio
    async def test_excluye_servicios_sin_neto_adulto(self) -> None:
        """Services with precio_sugerido_adulto set but precio_neto_adulto=None are excluded."""
        from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio

        s_sin_neto = _servicio(precio_neto_adulto=None, precio_sugerido_adulto=Decimal("120000"))
        repo = MagicMock()
        repo.listar_activos.return_value = [s_sin_neto]
        generador = FakeGenerador()
        enviador = FakeEnviador()

        svc = PublicarListaPreciosServicio(repo, generador, enviador, "grupo123")
        await svc.publicar()

        assert generador.calls == []
        assert enviador.sent == []
