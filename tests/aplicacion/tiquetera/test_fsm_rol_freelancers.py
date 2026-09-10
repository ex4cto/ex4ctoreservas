"""Tests for E: 'A nombre de freelancers' role option (registrant plays no role)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

_SERVICIOS: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour", Decimal("100000"), Decimal("50000"), "BARÚ", []),
]
_PUNTOS = ["Marie Real"]
F1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
F2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
_FREELANCERS: list[tuple[uuid.UUID, str, bool]] = [(F1, "Ana", True), (F2, "Luis", True)]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=_SERVICIOS, puntos_venta=_PUNTOS, freelancers=_FREELANCERS)


def _ctx(privilegiado: bool = True) -> ContextoVenta:
    ctx = ContextoVenta()
    ctx.registrante_privilegiado = privilegiado
    return ctx


class TestOpcionesRol:
    def test_privilegiado_ve_la_opcion(self, fsm: FSMTiquetera) -> None:
        assert "A nombre de freelancers" in fsm._opciones_rol(_ctx(True))

    def test_no_privilegiado_no_ve_la_opcion(self, fsm: FSMTiquetera) -> None:
        assert "A nombre de freelancers" not in fsm._opciones_rol(_ctx(False))


class TestFlujoANombreDeFreelancers:
    def test_elegir_opcion_pide_vendedor(self, fsm: FSMTiquetera) -> None:
        salida = fsm.procesar(
            EstadoFSM.PARTICIPANTE_ROL, "A nombre de freelancers", _ctx()
        )
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert salida.contexto.rol_registrante == "ninguno"

    def test_doble_seleccion_vendedor_luego_cerrador(self, fsm: FSMTiquetera) -> None:
        s1 = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "A nombre de freelancers", _ctx())
        s2 = fsm.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F1}", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO  # ahora pide cerrador
        assert s2.contexto.vendedor_id == F1
        assert s2.contexto.vendedor_nombre == "Ana"
        assert s2.contexto.cerrador_id is None

        s3 = fsm.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F2}", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s3.contexto.cerrador_id == F2
        assert s3.contexto.cerrador_nombre == "Luis"
        assert s3.contexto.rol_registrante == "ninguno"

    def test_mismo_freelancer_en_ambos_roles_permitido(self, fsm: FSMTiquetera) -> None:
        s1 = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "A nombre de freelancers", _ctx())
        s2 = fsm.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F1}", s1.contexto)
        s3 = fsm.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F1}", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s3.contexto.vendedor_id == F1
        assert s3.contexto.cerrador_id == F1

    def test_no_privilegiado_no_puede_usar_la_opcion(self, fsm: FSMTiquetera) -> None:
        salida = fsm.procesar(
            EstadoFSM.PARTICIPANTE_ROL, "A nombre de freelancers", _ctx(False)
        )
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.rol_registrante != "ninguno"
