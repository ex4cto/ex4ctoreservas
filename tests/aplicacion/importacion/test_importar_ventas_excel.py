from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.importacion.errores import DescripcionSinMapeo
from garay.aplicacion.importacion.importar_ventas_excel import ImportarVentasExcelService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puertos.servicios_externos import FilaVentaImportada
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.servicios.entidades import Servicio


def _fila(
    *,
    canal: str = "Externas",
    cliente: str = "Stefan Ponce",
    desc: str = "Playa tranquila",
    fecha: datetime.date = datetime.date(2026, 7, 3),
    valor: int = 400000,
    neto: int = 300000,
    agencia: int = 48000,
    vend: int = 36000,
    cerr: int = 36000,
) -> FilaVentaImportada:
    return FilaVentaImportada(
        canal=canal,
        cliente_nombre=cliente,
        fecha=fecha,
        descripcion=desc,
        valor=Dinero(valor),
        neto=Dinero(neto),
        margen=Dinero(valor - neto),
        agencia=Dinero(agencia),
        comision_vendedor=Dinero(vend),
        comision_cerrador=Dinero(cerr),
        vendedor_nombre="Mairele",
        cerrador_nombre="Mairele",
    )


def _build(
    filas: list[FilaVentaImportada],
    *,
    alias: dict[str, int] | None = None,
    cliente_existente: Cliente | None = None,
    punto: PuntoDeVenta | None = None,
) -> tuple[ImportarVentasExcelService, MagicMock, MagicMock, MagicMock]:
    lector = MagicMock()
    lector.leer.return_value = filas
    ventas = MagicMock()
    clientes = MagicMock()
    clientes.buscar_por_nombre.return_value = cliente_existente
    servicios = MagicMock()
    servicios.listar.return_value = [
        Servicio(id=uuid.uuid4(), numero=12, nombre="Playa tranquila", categoria="BARU")
    ]
    puntos = MagicMock()
    puntos.buscar_por_nombre.return_value = punto
    comisiones = MagicMock()
    svc = ImportarVentasExcelService(
        lector, ventas, clientes, servicios, puntos, comisiones,
        {"playa tranquila": 12} if alias is None else alias,
    )
    return svc, ventas, clientes, comisiones


def test_importa_venta_y_comision() -> None:
    svc, ventas, _clientes, comisiones = _build([_fila()])
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.ventas_creadas == 1
    ventas.guardar.assert_called_once()
    comisiones.guardar.assert_called_once()
    venta = ventas.guardar.call_args.args[0]
    assert venta.valor_venta == Dinero(400000)
    assert venta.canal_origen == "Externas"
    assert venta.tipo_cliente == TipoCliente.EXTERNO
    assert venta.participantes.vendedor_nombre == "Mairele"
    comision = comisiones.guardar.call_args.args[0]
    assert comision.desglose.agencia == Dinero(48000)


def test_filtra_por_mes() -> None:
    filas = [_fila(), _fila(fecha=datetime.date(2026, 8, 1), cliente="Otro")]
    svc, ventas, _, _ = _build(filas)
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.ventas_creadas == 1
    ventas.guardar.assert_called_once()


def test_crea_cliente_si_no_existe() -> None:
    svc, _, clientes, _ = _build([_fila()], cliente_existente=None)
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.clientes_creados == 1
    clientes.guardar.assert_called_once()


def test_usa_cliente_existente() -> None:
    existente = Cliente(id=uuid.uuid4(), nombre="Stefan Ponce", tipo=TipoCliente.EXTERNO)
    svc, ventas, clientes, _ = _build([_fila()], cliente_existente=existente)
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.clientes_creados == 0
    clientes.guardar.assert_not_called()
    assert ventas.guardar.call_args.args[0].cliente_id == existente.id


def test_crespo_asigna_punto_y_hebert_como_residual() -> None:
    punto = PuntoDeVenta(id=uuid.uuid4(), nombre="Crespo", porcentaje_capa=Decimal("20"))
    # margen 180000, agencia 54000, vend 0, cerr 90000 -> residual Hebert 36000
    fila = _fila(canal="Crespo", valor=560000, neto=380000, agencia=54000, vend=0, cerr=90000)
    svc, ventas, _, comisiones = _build([fila], punto=punto)
    svc.ejecutar("x.xlsx", 7, 2026)
    venta = ventas.guardar.call_args.args[0]
    assert venta.participantes.punto_de_venta_id == punto.id
    desglose = comisiones.guardar.call_args.args[0].desglose
    assert desglose.punto_de_venta == Dinero(36000)  # Hebert = margen - agencia - vend - cerr


def test_descripcion_sin_mapeo_falla() -> None:
    svc, _, _, _ = _build([_fila(desc="Tour desconocido")], alias={})
    with pytest.raises(DescripcionSinMapeo):
        svc.ejecutar("x.xlsx", 7, 2026)


def test_idempotente_mismo_venta_id() -> None:
    svc1, ventas1, _, _ = _build([_fila()])
    svc2, ventas2, _, _ = _build([_fila()])
    svc1.ejecutar("x.xlsx", 7, 2026)
    svc2.ejecutar("x.xlsx", 7, 2026)
    assert ventas1.guardar.call_args.args[0].id == ventas2.guardar.call_args.args[0].id
