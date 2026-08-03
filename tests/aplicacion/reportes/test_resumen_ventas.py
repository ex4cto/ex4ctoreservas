"""Tests for ResumenVentasService — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.resumen_ventas import ResumenVendedor, ResumenVentasService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def _make_snapshot() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("10"),
        porcentaje_cerrador=Decimal("5"),
        porcentaje_referido_maximo=Decimal("3"),
        porcentaje_capa_punto=Decimal("2"),
    )


def _make_venta(
    *,
    valor: int = 500_000,
    neto: int | None = None,
    vendedor: str | None = "Carlos",
    cerrador: str | None = "Maria",
    fecha: datetime.date = datetime.date(2026, 7, 10),
    vendedor_id: uuid.UUID | None = None,
    cerrador_id: uuid.UUID | None = None,
) -> Venta:
    # neto defaults to half of valor to always satisfy valor_venta > neto
    effective_neto = neto if neto is not None else valor // 2
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(effective_neto),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=fecha,
        participantes=Participantes(
            vendedor_nombre=vendedor,
            cerrador_nombre=cerrador,
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
        ),
    )


def _make_comision(
    venta_id: uuid.UUID,
    *,
    vendedor: int = 50_000,
    cerrador: int = 25_000,
    agencia: int = 200_000,
) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero(vendedor),
            cerrador=Dinero(cerrador),
            punto_de_venta=Dinero(0),
            referido=Dinero(0),
            agencia=Dinero(agencia),
            snapshot=_make_snapshot(),
        ),
        fecha=datetime.date(2026, 7, 10),
    )


def _make_service(
    ventas: list[Venta],
    comisiones: list[ComisionRegistrada],
    freelancers: list[Freelancer] | None = None,
) -> ResumenVentasService:
    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = ventas

    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = comisiones

    freelancer_repo = MagicMock()
    freelancer_repo.listar_todos.return_value = freelancers or []

    return ResumenVentasService(
        ventas=ventas_repo,
        comisiones=comisiones_repo,
        freelancers=freelancer_repo,
    )


class TestResumenVentasServiceSinVentas:
    def test_sin_ventas_devuelve_ceros(self) -> None:
        service = _make_service(ventas=[], comisiones=[])
        resumen = service.ejecutar(mes=7, año=2026)

        assert resumen.total_ventas == 0
        assert resumen.total_valor == Dinero(0)
        assert resumen.ganancia_agencia == Dinero(0)
        assert resumen.por_vendedor == ()
        assert resumen.mes == 7
        assert resumen.año == 2026


class TestResumenVentasServiceUnVendedor:
    def test_un_vendedor_una_venta(self) -> None:
        venta = _make_venta(valor=500_000, neto=300_000, vendedor="Carlos", cerrador="Carlos")
        comision = _make_comision(venta.id, vendedor=50_000, cerrador=25_000, agencia=200_000)
        service = _make_service(ventas=[venta], comisiones=[comision])

        resumen = service.ejecutar(mes=7, año=2026)

        assert resumen.total_ventas == 1
        assert resumen.total_valor == Dinero(500_000)
        assert resumen.ganancia_agencia == Dinero(200_000)

    def test_un_vendedor_distintos_roles_en_misma_venta(self) -> None:
        """Mismo freelancer como vendedor Y cerrador — suma ambas comisiones."""
        venta = _make_venta(vendedor="Juan", cerrador="Juan")
        comision = _make_comision(venta.id, vendedor=50_000, cerrador=25_000, agencia=100_000)
        service = _make_service(ventas=[venta], comisiones=[comision])

        resumen = service.ejecutar(mes=7, año=2026)

        # Juan aparece una vez con la suma de vendedor + cerrador
        assert len(resumen.por_vendedor) == 1
        juan = resumen.por_vendedor[0]
        assert juan.nombre == "Juan"
        assert juan.comision == Dinero(75_000)  # 50000 + 25000


class TestResumenVentasServiceVendedorNulo:
    def test_vendedor_none_queda_como_sin_asignar(self) -> None:
        venta = _make_venta(vendedor=None, cerrador="Maria")
        comision = _make_comision(venta.id, vendedor=0, cerrador=25_000, agencia=100_000)
        service = _make_service(ventas=[venta], comisiones=[comision])

        resumen = service.ejecutar(mes=7, año=2026)

        nombres = {v.nombre for v in resumen.por_vendedor}
        assert "Sin asignar" in nombres


# ─── Phase 1: ResumenVendedor.freelancer_id ──────────────────────────────────

_UUID_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_UUID_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_UUID_INACTIVE = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_UUID_UNKNOWN = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_UUID_OTHER = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _make_freelancer(
    fid: uuid.UUID,
    nombre: str,
    display: str | None,
    *,
    activo: bool = True,
) -> Freelancer:
    return Freelancer(id=fid, nombre=nombre, display=display, activo=activo)


class TestResumenVendedorFreelancerId:
    """Tasks 1.1 and 1.2 — ResumenVendedor gains freelancer_id field (additive)."""

    def test_construye_con_freelancer_id(self) -> None:
        """SC-01 variant: ResumenVendedor accepts and stores freelancer_id."""
        rv = ResumenVendedor(
            nombre="Mairelis G.",
            ventas=1,
            valor_total=Dinero(500_000),
            comision=Dinero(50_000),
            freelancer_id=_UUID_A,
        )
        assert rv.freelancer_id == _UUID_A

    def test_freelancer_id_none_para_bucket_nombre(self) -> None:
        """SC-02 variant: name-keyed bucket has freelancer_id=None."""
        rv = ResumenVendedor(
            nombre="Bryan C.",
            ventas=1,
            valor_total=Dinero(300_000),
            comision=Dinero(30_000),
            freelancer_id=None,
        )
        assert rv.freelancer_id is None


# ─── Phase 3: two-level grouping (SC-01..SC-09, SC-16) ───────────────────────


class TestResumenVentasIdKeyedGrouping:
    """SC-01 — id-keyed venta uses display name from bulk dict."""

    def test_id_keyed_uses_display_not_snapshot(self) -> None:
        fl = _make_freelancer(_UUID_A, "Mairelis", "Mairelis G.")
        venta = _make_venta(
            vendedor="Mairele",
            cerrador=None,
            vendedor_id=_UUID_A,
        )
        com = _make_comision(venta.id)
        service = _make_service([venta], [com], freelancers=[fl])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Mairelis G." in vendedores, f"Expected 'Mairelis G.' in {list(vendedores)}"
        assert "Mairele" not in vendedores
        assert vendedores["Mairelis G."].freelancer_id == _UUID_A


class TestResumenVentasNullIdGrouping:
    """SC-02 — NULL-id venta uses snapshot name as vendedor bucket key (not 'Sin asignar')."""

    def test_null_id_uses_snapshot_not_sin_asignar(self) -> None:
        # cerrador is also "Bryan C." so no "Sin asignar" cerrador bucket is created
        venta = _make_venta(vendedor="Bryan C.", cerrador="Bryan C.", vendedor_id=None)
        com = _make_comision(venta.id)
        service = _make_service([venta], [com], freelancers=[])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Bryan C." in vendedores
        assert "Sin asignar" not in vendedores
        assert vendedores["Bryan C."].freelancer_id is None


class TestResumenVentasTwoNullIdNotCollapsed:
    """SC-03 — two NULL-id ventas with different snapshots are NOT merged."""

    def test_two_null_id_distinct_names_two_buckets(self) -> None:
        v1 = _make_venta(vendedor="Ana", cerrador=None, vendedor_id=None)
        v2 = _make_venta(vendedor="Pedro", cerrador=None, vendedor_id=None)
        c1 = _make_comision(v1.id)
        c2 = _make_comision(v2.id)
        service = _make_service([v1, v2], [c1, c2], freelancers=[])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre for rv in resumen.por_vendedor}
        assert "Ana" in vendedores
        assert "Pedro" in vendedores


class TestResumenVentasSameIdOneBucket:
    """SC-04 — two id-keyed ventas with same id → one bucket, ventas=2."""

    def test_same_id_collapses_to_one_bucket(self) -> None:
        fl = _make_freelancer(_UUID_A, "Carlos", "Carlos P.")
        v1 = _make_venta(vendedor="Carlos", cerrador=None, vendedor_id=_UUID_A, valor=300_000)
        v2 = _make_venta(vendedor="Carlos", cerrador=None, vendedor_id=_UUID_A, valor=200_000)
        c1 = _make_comision(v1.id)
        c2 = _make_comision(v2.id)
        service = _make_service([v1, v2], [c1, c2], freelancers=[fl])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Carlos P." in vendedores
        assert vendedores["Carlos P."].ventas == 2
        assert vendedores["Carlos P."].freelancer_id == _UUID_A


class TestResumenVentasCerradorAndVendedorIndependent:
    """SC-05 — cerrador_id set + vendedor_id None → independent buckets."""

    def test_cerrador_id_vendedor_null_independent(self) -> None:
        fl = _make_freelancer(_UUID_B, "Luisa", "Luisa M.")
        venta = _make_venta(
            vendedor="Ana",
            cerrador="Luisa",
            vendedor_id=None,
            cerrador_id=_UUID_B,
        )
        com = _make_comision(venta.id)
        service = _make_service([venta], [com], freelancers=[fl])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Ana" in vendedores
        assert vendedores["Ana"].freelancer_id is None
        assert "Luisa M." in vendedores
        assert vendedores["Luisa M."].freelancer_id == _UUID_B


class TestResumenVentasTransitionDoubleCount:
    """SC-06 — transition double-count is present and correct."""

    def test_transition_produces_two_buckets_for_same_person(self) -> None:
        # Transition artifact — resolved by Slice E backfill
        fl = _make_freelancer(_UUID_A, "Mairelis", "Mairelis G.")
        v_new = _make_venta(vendedor="Mairele", cerrador=None, vendedor_id=_UUID_A)
        v_old = _make_venta(vendedor="Mairele", cerrador=None, vendedor_id=None)
        c_new = _make_comision(v_new.id)
        c_old = _make_comision(v_old.id)
        service = _make_service([v_new, v_old], [c_new, c_old], freelancers=[fl])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Mairelis G." in vendedores, "id-bucket should use display"
        assert "Mairele" in vendedores, "name-bucket should use snapshot"
        assert vendedores["Mairelis G."].ventas == 1
        assert vendedores["Mairele"].ventas == 1


class TestResumenVentasBulkLoadOnce:
    """SC-07 — listar_todos called exactly once."""

    def test_listar_todos_called_once_for_multiple_ventas(self) -> None:
        fl_a = _make_freelancer(_UUID_A, "Carlos", "Carlos P.")
        fl_b = _make_freelancer(_UUID_B, "Luisa", "Luisa M.")
        v1 = _make_venta(vendedor="Carlos", cerrador=None, vendedor_id=_UUID_A)
        v2 = _make_venta(vendedor="Luisa", cerrador=None, vendedor_id=_UUID_B)
        v3 = _make_venta(vendedor="Carlos", cerrador=None, vendedor_id=_UUID_A)
        comisiones = [_make_comision(v.id) for v in [v1, v2, v3]]

        ventas_repo = MagicMock()
        ventas_repo.listar_por_periodo.return_value = [v1, v2, v3]
        comisiones_repo = MagicMock()
        comisiones_repo.listar_por_venta_ids.return_value = comisiones
        freelancer_repo = MagicMock()
        freelancer_repo.listar_todos.return_value = [fl_a, fl_b]

        from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService as _Svc

        service = _Svc(ventas=ventas_repo, comisiones=comisiones_repo, freelancers=freelancer_repo)
        service.ejecutar(mes=7, año=2026)

        freelancer_repo.listar_todos.assert_called_once()


class TestResumenVentasInactiveFreelancer:
    """SC-08 — inactive freelancer still resolves display."""

    def test_inactive_freelancer_resolves_display(self) -> None:
        fl = _make_freelancer(_UUID_INACTIVE, "Ex Vendedor", "Ex V.", activo=False)
        venta = _make_venta(vendedor="Ex", cerrador=None, vendedor_id=_UUID_INACTIVE)
        com = _make_comision(venta.id)
        service = _make_service([venta], [com], freelancers=[fl])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Ex V." in vendedores
        assert vendedores["Ex V."].freelancer_id == _UUID_INACTIVE


class TestResumenVentasUnknownIdFallback:
    """SC-09 — id-keyed freelancer not in dict falls back to snapshot."""

    def test_unknown_id_falls_back_to_snapshot(self) -> None:
        venta = _make_venta(vendedor="Copia vieja", cerrador=None, vendedor_id=_UUID_UNKNOWN)
        com = _make_comision(venta.id)
        service = _make_service([venta], [com], freelancers=[])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Copia vieja" in vendedores
        assert vendedores["Copia vieja"].freelancer_id == _UUID_UNKNOWN


class TestResumenVentasDisplayNoneFallback:
    """display=None → nombre fallback for label."""

    def test_display_none_uses_nombre(self) -> None:
        fl = _make_freelancer(_UUID_A, "Carlos Perez", None)
        venta = _make_venta(vendedor="Carlos viejo", cerrador=None, vendedor_id=_UUID_A)
        com = _make_comision(venta.id)
        service = _make_service([venta], [com], freelancers=[fl])
        resumen = service.ejecutar(mes=7, año=2026)

        vendedores = {rv.nombre: rv for rv in resumen.por_vendedor}
        assert "Carlos Perez" in vendedores
        assert vendedores["Carlos Perez"].freelancer_id == _UUID_A


class TestResumenVentasRequiresFreelancers:
    """SC-16 — TypeError when no freelancers arg."""

    def test_missing_freelancers_raises_type_error(self) -> None:
        import pytest

        ventas_repo = MagicMock()
        comisiones_repo = MagicMock()
        with pytest.raises(TypeError):
            ResumenVentasService(ventas=ventas_repo, comisiones=comisiones_repo)  # type: ignore[call-arg]


def test_por_dia_agrupa_correctamente() -> None:
    v1 = _make_venta(valor=300_000, neto=200_000, fecha=datetime.date(2026, 7, 10))
    v2 = _make_venta(valor=200_000, neto=150_000, fecha=datetime.date(2026, 7, 10))
    v3 = _make_venta(valor=400_000, neto=300_000, fecha=datetime.date(2026, 7, 15))
    c1 = _make_comision(v1.id)
    c2 = _make_comision(v2.id)
    c3 = _make_comision(v3.id)
    service = _make_service(ventas=[v1, v2, v3], comisiones=[c1, c2, c3])
    resumen = service.ejecutar(mes=7, año=2026)

    assert len(resumen.por_dia) == 2
    assert resumen.por_dia[0] == (datetime.date(2026, 7, 10), 2, Dinero(500_000))
    assert resumen.por_dia[1] == (datetime.date(2026, 7, 15), 1, Dinero(400_000))


def test_por_dia_vacio_si_sin_ventas() -> None:
    service = _make_service(ventas=[], comisiones=[])
    resumen = service.ejecutar(mes=7, año=2026)

    assert resumen.por_dia == ()
