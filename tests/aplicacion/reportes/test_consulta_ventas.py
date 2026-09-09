"""Tests for ConsultaVentasService — FK resolution + flattening, TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.consulta_ventas import ConsultaVentasService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.facturas.tipos import EstadoEnvioFactura
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_UUID_F = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_UUID_G = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_freelancer(fid: uuid.UUID, nombre: str, display: str | None) -> Freelancer:
    return Freelancer(id=fid, nombre=nombre, display=display, activo=True)


def _repo_vacio(metodo: str) -> MagicMock:
    """MagicMock repo whose ``metodo`` returns an empty list."""
    repo = MagicMock()
    getattr(repo, metodo).return_value = []
    return repo


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
    punto_id = uuid.uuid4()
    venta = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("300000"),
        abono=Dinero("200000"),
        servicio_ids=[serv_a, serv_b],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 10),
        participantes=Participantes(
            vendedor_nombre="Carlos",
            cerrador_nombre="Maria",
            punto_de_venta_id=punto_id,
            referido_nombre="Pedro",
        ),
        adultos=2,
        ninos=1,
        canal_origen="WhatsApp",
        fechas_por_servicio={serv_a: datetime.datetime(2026, 7, 12, 9, 0)},
        horarios_por_servicio={serv_a: "mañana"},
    )
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = [venta]
    clientes = MagicMock()
    clientes.listar.return_value = [
        Cliente(
            id=cliente_id,
            nombre="Juan Perez",
            tipo=TipoCliente.EXTERNO,
            telefono="3001234567",
            email="juan@example.com",
            identificacion="12345",
            hotel="Hotel Mar",
            numero_habitacion="101",
        )
    ]
    servicios = MagicMock()
    servicios.listar.return_value = [
        Servicio(id=serv_a, numero=1, nombre="Tour Islas"),
        Servicio(id=serv_b, numero=2, nombre="City Tour"),
    ]

    freelancers = MagicMock()
    freelancers.listar_todos.return_value = []
    puntos = MagicMock()
    puntos.listar.return_value = [
        PuntoDeVenta(id=punto_id, nombre="Recepción", porcentaje_capa=Decimal(10))
    ]

    comision = MagicMock()
    comision.venta_id = venta.id
    comision.desglose.vendedor = Dinero("50000")
    comision.desglose.cerrador = Dinero("30000")
    comision.desglose.punto_de_venta = Dinero("10000")
    comision.desglose.referido = Dinero("5000")
    comision.desglose.agencia = Dinero("205000")
    comisiones = MagicMock()
    comisiones.listar_por_venta_ids.return_value = [comision]

    factura = MagicMock()
    factura.venta_id = venta.id
    factura.numero = "F-001"
    factura.estado_envio = EstadoEnvioFactura.ENVIADO
    facturas = MagicMock()
    facturas.listar_por_venta_ids.return_value = [factura]

    servicio = ConsultaVentasService(
        ventas=ventas,
        clientes=clientes,
        servicios=servicios,
        freelancers=freelancers,
        puntos_de_venta=puntos,
        comisiones=comisiones,
        facturas=facturas,
    )
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert len(filas) == 1
    fila = filas[0]
    assert fila.cliente_nombre == "Juan Perez"
    assert fila.servicios == "Tour Islas, City Tour"
    assert fila.valor == Dinero("500000")
    assert fila.neto == Dinero("300000")
    assert fila.ganancia == Dinero("200000")
    assert fila.tipo_cliente == "EXTERNO"
    assert fila.canal_origen == "WhatsApp"
    assert fila.vendedor == "Carlos"
    assert fila.cerrador == "Maria"
    assert fila.adultos == 2
    assert fila.ninos == 1
    # Raw-data expansion (PR A)
    assert fila.venta_id == str(venta.id)
    assert fila.abono == Dinero("200000")
    assert fila.saldo_pendiente == Dinero("300000")
    assert fila.anulada is False
    assert fila.cliente_telefono == "3001234567"
    assert fila.cliente_email == "juan@example.com"
    assert fila.cliente_identificacion == "12345"
    assert fila.cliente_hotel == "Hotel Mar"
    assert fila.cliente_habitacion == "101"
    assert fila.punto_de_venta == "Recepción"
    assert fila.referido == "Pedro"
    assert "Tour Islas — 12/07/2026 09:00 (mañana)" in fila.fechas_horarios
    assert "City Tour — 10/07/2026" in fila.fechas_horarios
    # Comisión + factura (PR B)
    assert fila.comision_vendedor == Dinero("50000")
    assert fila.comision_cerrador == Dinero("30000")
    assert fila.comision_punto_de_venta == Dinero("10000")
    assert fila.comision_referido == Dinero("5000")
    assert fila.comision_agencia == Dinero("205000")
    assert fila.factura_numero == "F-001"
    assert fila.factura_estado == "ENVIADO"
    comisiones.listar_por_venta_ids.assert_called_once_with([venta.id])
    facturas.listar_por_venta_ids.assert_called_once_with([venta.id])
    ventas.listar_por_periodo.assert_called_once_with(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )


def test_venta_sin_comision_ni_factura_deja_campos_none() -> None:
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
    servicio = ConsultaVentasService(
        ventas=ventas,
        clientes=_repo_vacio("listar"),
        servicios=_repo_vacio("listar"),
        freelancers=_repo_vacio("listar_todos"),
        puntos_de_venta=_repo_vacio("listar"),
        comisiones=_repo_vacio("listar_por_venta_ids"),
        facturas=_repo_vacio("listar_por_venta_ids"),
    )
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    fila = filas[0]
    assert fila.comision_vendedor is None
    assert fila.comision_agencia is None
    assert fila.factura_numero is None
    assert fila.factura_estado is None


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
    servicio = ConsultaVentasService(
        ventas=ventas,
        clientes=_repo_vacio("listar"),
        servicios=_repo_vacio("listar"),
        freelancers=_repo_vacio("listar_todos"),
        puntos_de_venta=_repo_vacio("listar"),
        comisiones=_repo_vacio("listar_por_venta_ids"),
        facturas=_repo_vacio("listar_por_venta_ids"),
    )
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert filas[0].cliente_nombre == "—"
    assert filas[0].servicios == ""


def test_sin_ventas_devuelve_vacio() -> None:
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = []
    servicio = ConsultaVentasService(
        ventas=ventas,
        clientes=_repo_vacio("listar"),
        servicios=_repo_vacio("listar"),
        freelancers=_repo_vacio("listar_todos"),
        puntos_de_venta=_repo_vacio("listar"),
        comisiones=_repo_vacio("listar_por_venta_ids"),
        facturas=_repo_vacio("listar_por_venta_ids"),
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
    freelancers_repo = MagicMock()
    freelancers_repo.listar_todos.return_value = lista_freelancers or []
    return ConsultaVentasService(
        ventas=ventas_repo,
        clientes=_repo_vacio("listar"),
        servicios=_repo_vacio("listar"),
        freelancers=freelancers_repo,
        puntos_de_venta=_repo_vacio("listar"),
        comisiones=_repo_vacio("listar_por_venta_ids"),
        facturas=_repo_vacio("listar_por_venta_ids"),
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
        freelancers_repo = MagicMock()
        freelancers_repo.listar_todos.return_value = [fl]
        service = ConsultaVentasService(
            ventas=ventas_repo,
            clientes=_repo_vacio("listar"),
            servicios=_repo_vacio("listar"),
            freelancers=freelancers_repo,
            puntos_de_venta=_repo_vacio("listar"),
            comisiones=_repo_vacio("listar_por_venta_ids"),
            facturas=_repo_vacio("listar_por_venta_ids"),
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
