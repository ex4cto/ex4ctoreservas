from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.importacion.errores import (
    DescripcionSinMapeo,
    ImportacionConNombresNoResueltos,
)
from garay.aplicacion.importacion.importar_ventas_excel import ImportarVentasExcelService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.freelancers.entidades import Freelancer
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
    resolver: Callable[[str], list[Freelancer]] | None = None,
) -> tuple[ImportarVentasExcelService, MagicMock, MagicMock, MagicMock, MagicMock]:
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
    freelancers = MagicMock()
    _default_freelancer = Freelancer(id=uuid.uuid4(), nombre="Mairele")
    if resolver is not None:
        freelancers.listar_por_nombre.side_effect = resolver
    else:
        freelancers.listar_por_nombre.return_value = [_default_freelancer]
    svc = ImportarVentasExcelService(
        lector,
        ventas,
        clientes,
        servicios,
        puntos,
        comisiones,
        {"playa tranquila": 12} if alias is None else alias,
        freelancers,
    )
    return svc, ventas, clientes, comisiones, freelancers


def test_importa_venta_y_comision() -> None:
    svc, ventas, _clientes, comisiones, _ = _build([_fila()])
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
    svc, ventas, _, _, _ = _build(filas)
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.ventas_creadas == 1
    ventas.guardar.assert_called_once()


def test_crea_cliente_si_no_existe() -> None:
    svc, _, clientes, _, _ = _build([_fila()], cliente_existente=None)
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.clientes_creados == 1
    clientes.guardar.assert_called_once()


def test_usa_cliente_existente() -> None:
    existente = Cliente(id=uuid.uuid4(), nombre="Stefan Ponce", tipo=TipoCliente.EXTERNO)
    svc, ventas, clientes, _, _ = _build([_fila()], cliente_existente=existente)
    r = svc.ejecutar("x.xlsx", 7, 2026)
    assert r.clientes_creados == 0
    clientes.guardar.assert_not_called()
    assert ventas.guardar.call_args.args[0].cliente_id == existente.id


def test_crespo_asigna_punto_y_hebert_como_residual() -> None:
    punto = PuntoDeVenta(id=uuid.uuid4(), nombre="Crespo", porcentaje_capa=Decimal("20"))
    # margen 180000, agencia 54000, vend 0, cerr 90000 -> residual Hebert 36000
    fila = _fila(canal="Crespo", valor=560000, neto=380000, agencia=54000, vend=0, cerr=90000)
    svc, ventas, _, comisiones, _ = _build([fila], punto=punto)
    svc.ejecutar("x.xlsx", 7, 2026)
    venta = ventas.guardar.call_args.args[0]
    assert venta.participantes.punto_de_venta_id == punto.id
    desglose = comisiones.guardar.call_args.args[0].desglose
    assert desglose.punto_de_venta == Dinero(36000)  # Hebert = margen - agencia - vend - cerr


def test_descripcion_sin_mapeo_falla() -> None:
    svc, _, _, _, _ = _build([_fila(desc="Tour desconocido")], alias={})
    with pytest.raises(DescripcionSinMapeo):
        svc.ejecutar("x.xlsx", 7, 2026)


def test_idempotente_mismo_venta_id() -> None:
    svc1, ventas1, _, _, _ = _build([_fila()])
    svc2, ventas2, _, _, _ = _build([_fila()])
    svc1.ejecutar("x.xlsx", 7, 2026)
    svc2.ejecutar("x.xlsx", 7, 2026)
    assert ventas1.guardar.call_args.args[0].id == ventas2.guardar.call_args.args[0].id


# ---------------------------------------------------------------------------
# New tests: freelancer resolution (SC-01 to SC-08)
# ---------------------------------------------------------------------------


def _fila_con_participantes(
    *,
    vendedor_nombre: str | None = "Eduardo",
    cerrador_nombre: str | None = "Bryan",
) -> FilaVentaImportada:
    """Helper for resolution tests: single row with custom participant names."""
    return FilaVentaImportada(
        canal="Externas",
        cliente_nombre="Stefan Ponce",
        fecha=datetime.date(2026, 7, 3),
        descripcion="Playa tranquila",
        valor=Dinero(400000),
        neto=Dinero(300000),
        margen=Dinero(100000),
        agencia=Dinero(48000),
        comision_vendedor=Dinero(36000),
        comision_cerrador=Dinero(36000),
        vendedor_nombre=vendedor_nombre,
        cerrador_nombre=cerrador_nombre,
    )


def test_asigna_ids_cuando_hay_match_unico() -> None:
    """SC-01: Both names resolve to 1 freelancer -> ids set, snapshots kept."""
    uuid_e = uuid.uuid4()
    uuid_b = uuid.uuid4()
    eduardo = Freelancer(id=uuid_e, nombre="Eduardo")
    bryan = Freelancer(id=uuid_b, nombre="Bryan")

    def _resolver(nombre: str) -> list[Freelancer]:
        return [eduardo] if nombre == "Eduardo" else [bryan]

    svc, ventas, _, _, _ = _build(
        [_fila_con_participantes(vendedor_nombre="Eduardo", cerrador_nombre="Bryan")],
        resolver=_resolver,
    )
    svc.ejecutar("x.xlsx", 7, 2026)

    ventas.guardar.assert_called_once()
    participantes = ventas.guardar.call_args.args[0].participantes
    assert participantes.vendedor_id == uuid_e
    assert participantes.cerrador_id == uuid_b
    assert participantes.vendedor_nombre == "Eduardo"
    assert participantes.cerrador_nombre == "Bryan"


def test_aborta_cuando_nombre_no_existe() -> None:
    """SC-02: 0 matches -> ImportacionConNombresNoResueltos, nothing persisted."""
    uuid_b = uuid.uuid4()
    bryan = Freelancer(id=uuid_b, nombre="Bryan")

    def _resolver(nombre: str) -> list[Freelancer]:
        if nombre == "Mairele":
            return []
        return [bryan]

    svc, ventas, _, comisiones, _ = _build(
        [_fila_con_participantes(vendedor_nombre="Mairele", cerrador_nombre="Bryan")],
        resolver=_resolver,
    )
    with pytest.raises(ImportacionConNombresNoResueltos) as exc_info:
        svc.ejecutar("x.xlsx", 7, 2026)

    ventas.guardar.assert_not_called()
    comisiones.guardar.assert_not_called()
    nombres_no_encontrados = [nombre for _, nombre in exc_info.value.no_encontrados]
    assert "Mairele" in nombres_no_encontrados
    assert exc_info.value.ambiguos == []


def test_aborta_cuando_nombre_ambiguo() -> None:
    """SC-03: >=2 matches -> ImportacionConNombresNoResueltos, nothing persisted."""
    kike1 = Freelancer(id=uuid.uuid4(), nombre="Kike")
    kike2 = Freelancer(id=uuid.uuid4(), nombre="Kike")
    uuid_b = uuid.uuid4()
    bryan = Freelancer(id=uuid_b, nombre="Bryan")

    def _resolver(nombre: str) -> list[Freelancer]:
        if nombre == "Kike":
            return [kike1, kike2]
        return [bryan]

    svc, ventas, _, _, _ = _build(
        [_fila_con_participantes(vendedor_nombre="Kike", cerrador_nombre="Bryan")],
        resolver=_resolver,
    )
    with pytest.raises(ImportacionConNombresNoResueltos) as exc_info:
        svc.ejecutar("x.xlsx", 7, 2026)

    ventas.guardar.assert_not_called()
    nombres_ambiguos = [nombre for _, nombre in exc_info.value.ambiguos]
    assert "Kike" in nombres_ambiguos
    assert exc_info.value.no_encontrados == []


def test_nombre_en_blanco_no_es_error() -> None:
    """SC-04: Blank cerrador_nombre -> no error, vendedor_id set, cerrador_id None."""
    uuid_e = uuid.uuid4()
    eduardo = Freelancer(id=uuid_e, nombre="Eduardo")

    svc, ventas, _, _, freelancers = _build(
        [_fila_con_participantes(vendedor_nombre="Eduardo", cerrador_nombre=None)],
        resolver=lambda nombre: [eduardo],
    )
    svc.ejecutar("x.xlsx", 7, 2026)

    ventas.guardar.assert_called_once()
    participantes = ventas.guardar.call_args.args[0].participantes
    assert participantes.vendedor_id == uuid_e
    assert participantes.cerrador_id is None
    # listar_por_nombre only called for vendedor (cerrador is None -> skipped)
    freelancers.listar_por_nombre.assert_called_once_with("Eduardo")


def test_aborta_agrega_todos_los_nombres_fallidos() -> None:
    """SC-05/SC-06: Mixed sheet — abort-all, nothing persisted, all failures collected."""
    eduardo = Freelancer(id=uuid.uuid4(), nombre="Eduardo")
    bryan = Freelancer(id=uuid.uuid4(), nombre="Bryan")

    filas = [
        _fila_con_participantes(vendedor_nombre="Mairele", cerrador_nombre="Bryan"),
        _fila_con_participantes(vendedor_nombre="Eduardo", cerrador_nombre="Bryan"),
    ]

    def _resolver(nombre: str) -> list[Freelancer]:
        if nombre == "Mairele":
            return []
        if nombre == "Eduardo":
            return [eduardo]
        return [bryan]

    svc, ventas, _, comisiones, _ = _build(filas, resolver=_resolver)
    with pytest.raises(ImportacionConNombresNoResueltos) as exc_info:
        svc.ejecutar("x.xlsx", 7, 2026)

    ventas.guardar.assert_not_called()
    comisiones.guardar.assert_not_called()
    nombres_no_encontrados = [nombre for _, nombre in exc_info.value.no_encontrados]
    assert "Mairele" in nombres_no_encontrados


def test_normalizado_delega_al_repo() -> None:
    """SC-07: Raw name with spaces passed to repo; normalization is repo's job."""
    uuid_e = uuid.uuid4()
    eduardo = Freelancer(id=uuid_e, nombre="Eduardo")

    svc, ventas, _, _, freelancers = _build(
        [_fila_con_participantes(vendedor_nombre="  eduardo  ", cerrador_nombre=None)],
        resolver=lambda nombre: [eduardo],
    )
    svc.ejecutar("x.xlsx", 7, 2026)

    ventas.guardar.assert_called_once()
    participantes = ventas.guardar.call_args.args[0].participantes
    assert participantes.vendedor_id == uuid_e
    assert participantes.vendedor_nombre == "  eduardo  "
    freelancers.listar_por_nombre.assert_called_once_with("  eduardo  ")


def test_filas_omitidas_no_resuelven() -> None:
    """SC-08: Rows skipped by valor/neto guard do not trigger resolution."""
    uuid_e = uuid.uuid4()
    eduardo = Freelancer(id=uuid_e, nombre="Eduardo")

    filas = [
        # Row 1: omitted (valor=0)
        FilaVentaImportada(
            canal="Externas",
            cliente_nombre="Omitido",
            fecha=datetime.date(2026, 7, 1),
            descripcion="Playa tranquila",
            valor=Dinero(0),
            neto=Dinero(0),
            margen=Dinero(0),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Eduardo",
            cerrador_nombre=None,
        ),
        # Row 2: valid
        _fila_con_participantes(vendedor_nombre="Eduardo", cerrador_nombre=None),
    ]
    svc, ventas, _, _, freelancers = _build(filas, resolver=lambda nombre: [eduardo])
    r = svc.ejecutar("x.xlsx", 7, 2026)

    assert r.ventas_omitidas == 1
    ventas.guardar.assert_called_once()
    # listar_por_nombre called exactly once (omitted row skipped)
    freelancers.listar_por_nombre.assert_called_once_with("Eduardo")
