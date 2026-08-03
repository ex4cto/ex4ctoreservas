"""Tests for ConsultaVentasService — FK resolution + flattening, TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.consulta_ventas import ConsultaVentasService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_UUID_F = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_UUID_G = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_freelancer(fid: uuid.UUID, nombre: str, display: str | None) -> Freelancer:
    return Freelancer(id=fid, nombre=nombre, display=display, activo=True)


def _make_venta_con_ids(
    *,
    vendedor_id: uuid.UUID | None = None,
    vendedor_nombre: str | None = None,
    cerrador_id: uuid.UUID | None = None,
    cerrador_nombre: str | None = None,
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("300000"),
        servicio_ids=[],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 10),
        participantes=Participantes(
            vendedor_nombre=vendedor_nombre,
            cerrador_nombre=cerrador_nombre,
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
        ),
    )


def test_ejecutar_resuelve_fks_y_aplana() -> None:
    cliente_id = uuid.uuid4()
    serv_a = uuid.uuid4()
    serv_b = uuid.uuid4()
    venta = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("300000"),
        servicio_ids=[serv_a, serv_b],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.DIGITAL,
        fecha=datetime.date(2026, 7, 10),
        participantes=Participantes(vendedor_nombre="Carlos", cerrador_nombre="Maria"),
        adultos=2,
        ninos=1,
        canal_origen="WhatsApp",
    )
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = [venta]
    clientes = MagicMock()
    clientes.listar.return_value = [
        Cliente(id=cliente_id, nombre="Juan Perez", tipo=TipoCliente.DIGITAL)
    ]
    servicios = MagicMock()
    servicios.listar.return_value = [
        Servicio(id=serv_a, numero=1, nombre="Tour Islas"),
        Servicio(id=serv_b, numero=2, nombre="City Tour"),
    ]

    freelancers = MagicMock()
    freelancers.listar_todos.return_value = []
    servicio = ConsultaVentasService(
        ventas=ventas, clientes=clientes, servicios=servicios, freelancers=freelancers
    )
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert len(filas) == 1
    fila = filas[0]
    assert fila.cliente_nombre == "Juan Perez"
    assert fila.servicios == "Tour Islas, City Tour"
    assert fila.valor == Dinero("500000")
    assert fila.neto == Dinero("300000")
    assert fila.ganancia == Dinero("200000")
    assert fila.tipo_cliente == "DIGITAL"
    assert fila.canal_origen == "WhatsApp"
    assert fila.vendedor == "Carlos"
    assert fila.cerrador == "Maria"
    assert fila.adultos == 2
    assert fila.ninos == 1
    ventas.listar_por_periodo.assert_called_once_with(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )


def test_cliente_desconocido_usa_placeholder() -> None:
    venta = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("100000"),
        neto=Dinero("50000"),
        servicio_ids=[],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 5),
        participantes=Participantes(),
    )
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = [venta]
    clientes = MagicMock()
    clientes.listar.return_value = []
    servicios = MagicMock()
    servicios.listar.return_value = []

    freelancers = MagicMock()
    freelancers.listar_todos.return_value = []
    servicio = ConsultaVentasService(
        ventas=ventas, clientes=clientes, servicios=servicios, freelancers=freelancers
    )
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert filas[0].cliente_nombre == "—"
    assert filas[0].servicios == ""


def test_sin_ventas_devuelve_vacio() -> None:
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = []
    clientes = MagicMock()
    clientes.listar.return_value = []
    servicios = MagicMock()
    servicios.listar.return_value = []

    freelancers = MagicMock()
    freelancers.listar_todos.return_value = []
    servicio = ConsultaVentasService(
        ventas=ventas, clientes=clientes, servicios=servicios, freelancers=freelancers
    )
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert filas == []


# ─── SC-10, SC-11, SC-12, SC-17: display name resolution ─────────────────────


def _make_consulta_service(
    lista_ventas: list[Venta],
    lista_freelancers: list[Freelancer] | None = None,
) -> ConsultaVentasService:
    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = lista_ventas
    clientes_repo = MagicMock()
    clientes_repo.listar.return_value = []
    servicios_repo = MagicMock()
    servicios_repo.listar.return_value = []
    freelancers_repo = MagicMock()
    freelancers_repo.listar_todos.return_value = lista_freelancers or []
    return ConsultaVentasService(
        ventas=ventas_repo,
        clientes=clientes_repo,
        servicios=servicios_repo,
        freelancers=freelancers_repo,
    )


class TestConsultaVentasDisplayResolution:
    """SC-10 — id-keyed row resolves display name."""

    def test_vendedor_id_resolves_display(self) -> None:
        fl = _make_freelancer(_UUID_F, "Mairelis", "Mairelis G.")
        venta = _make_venta_con_ids(vendedor_id=_UUID_F, vendedor_nombre="Mairele")
        service = _make_consulta_service([venta], [fl])
        filas = service.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

        assert len(filas) == 1
        assert filas[0].vendedor == "Mairelis G."

    def test_null_vendedor_id_uses_snapshot(self) -> None:
        """SC-11 — NULL-id row uses snapshot directly."""
        venta = _make_venta_con_ids(vendedor_id=None, vendedor_nombre="Ana")
        service = _make_consulta_service([venta], [])
        filas = service.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

        assert filas[0].vendedor == "Ana"

    def test_listar_todos_called_once(self) -> None:
        """SC-12 — bulk load called exactly once for N rows."""
        fl = _make_freelancer(_UUID_F, "X", "X display")
        ventas = [
            _make_venta_con_ids(vendedor_id=_UUID_F, vendedor_nombre="X"),
            _make_venta_con_ids(vendedor_id=_UUID_F, vendedor_nombre="X"),
            _make_venta_con_ids(vendedor_id=_UUID_F, vendedor_nombre="X"),
        ]
        ventas_repo = MagicMock()
        ventas_repo.listar_por_periodo.return_value = ventas
        clientes_repo = MagicMock()
        clientes_repo.listar.return_value = []
        servicios_repo = MagicMock()
        servicios_repo.listar.return_value = []
        freelancers_repo = MagicMock()
        freelancers_repo.listar_todos.return_value = [fl]
        service = ConsultaVentasService(
            ventas=ventas_repo,
            clientes=clientes_repo,
            servicios=servicios_repo,
            freelancers=freelancers_repo,
        )
        service.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

        freelancers_repo.listar_todos.assert_called_once()

    def test_cerrador_id_resolves_display(self) -> None:
        """SC-17 — cerrador_id set resolves display for cerrador field."""
        fl = _make_freelancer(_UUID_G, "Luisa", "Luisa M.")
        venta = _make_venta_con_ids(cerrador_id=_UUID_G, cerrador_nombre="Luisa")
        service = _make_consulta_service([venta], [fl])
        filas = service.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

        assert filas[0].cerrador == "Luisa M."
