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
    PuntoCrespoNoConfigurado,
    VentaCrespoSinParticipantes,
)
from garay.aplicacion.importacion.importar_ventas_excel import ImportarVentasExcelService
from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puertos.servicios_externos import FilaVentaImportada
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.valor_objetos import Participantes


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
    reglas_repo: MagicMock | None = None,
    motor: MotorComisiones | MagicMock | None = None,
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
    _reglas_repo = reglas_repo if reglas_repo is not None else MagicMock()
    _motor = motor if motor is not None else MagicMock()
    svc = ImportarVentasExcelService(
        lector,
        ventas,
        clientes,
        servicios,
        puntos,
        comisiones,
        {"playa tranquila": 12} if alias is None else alias,
        freelancers,
        reglas_repo=_reglas_repo,
        motor=_motor,
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


def test_crespo_asigna_punto_y_capa_motor() -> None:
    # ganancia = valor - neto = 560000 - 380000 = 180000
    # Crespo 1P rule (same person): capa = 20% of 180000 = 36000
    punto = PuntoDeVenta(id=uuid.uuid4(), nombre="Crespo", porcentaje_capa=Decimal("20"))
    fila = _fila(canal="Crespo", valor=560000, neto=380000, agencia=54000, vend=0, cerr=90000)
    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P
    svc, ventas, _, comisiones, _ = _build(
        [fila],
        punto=punto,
        reglas_repo=reglas_repo,
        motor=_MOTOR_REAL,
    )
    svc.ejecutar("x.xlsx", 7, 2026)
    venta = ventas.guardar.call_args.args[0]
    assert venta.participantes.punto_de_venta_id == punto.id
    desglose = comisiones.guardar.call_args.args[0].desglose
    # Motor path: capa = 20% of 180000 = 36000
    assert desglose.punto_de_venta == Dinero(36000)
    # FIX-D: lock the buscar_regla call contract
    reglas_repo.buscar_regla.assert_called_once_with(TipoCliente.EXTERNO, "Crespo", 1)


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


# ---------------------------------------------------------------------------
# T10 / T11 — Crespo Excel parity (REQ-07)
# ---------------------------------------------------------------------------
# These tests assert that _desglose for Crespo rows goes through buscar_regla
# + motor.calcular and produces IDENTICAL breakdowns to the live bot flow.
#
# Commission base: venta.ganancia = valor - neto (NOT spreadsheet margen).
# ganancia = 500000 - 400000 = 100000
#
# T10: 1-persona (vendedor_id == cerrador_id):
#   crespo_1p rule: 50% vendedor, 0% cerrador, 20% capa (punto), agencia=residual
#   Expected: vendedor=50000, cerrador=0, capa=20000, agencia=30000
#
# T11: 2-personas (vendedor_id != cerrador_id):
#   crespo_2p rule: 30% vendedor, 30% cerrador, 20% capa, agencia=residual
#   Expected: vendedor=30000, cerrador=30000, capa=20000, agencia=20000
# ---------------------------------------------------------------------------

_MOTOR_REAL = MotorComisiones()

_CRESPO_REGLA_1P = ReglasComision(
    id=uuid.uuid4(),
    tipo_cliente=TipoCliente.EXTERNO,
    porcentaje_vendedor=Decimal("50"),
    porcentaje_cerrador=Decimal("0"),
    porcentaje_referido_maximo=Decimal("10"),
    punto_de_venta_nombre="Crespo",
    numero_personas=1,
)

_CRESPO_REGLA_2P = ReglasComision(
    id=uuid.uuid4(),
    tipo_cliente=TipoCliente.EXTERNO,
    porcentaje_vendedor=Decimal("30"),
    porcentaje_cerrador=Decimal("30"),
    porcentaje_referido_maximo=Decimal("10"),
    punto_de_venta_nombre="Crespo",
    numero_personas=2,
)

_UUID_A = uuid.uuid4()
_UUID_B = uuid.uuid4()


def _freelancer_resolver_ab(nombre: str) -> list[Freelancer]:
    """Resolver: 'Ana' -> _UUID_A, 'Luis' -> _UUID_B."""
    if nombre == "Ana":
        return [Freelancer(id=_UUID_A, nombre="Ana")]
    return [Freelancer(id=_UUID_B, nombre="Luis")]


def _crespo_punto_obj() -> PuntoDeVenta:
    return PuntoDeVenta(id=uuid.uuid4(), nombre="Crespo", porcentaje_capa=Decimal("20"))


class TestT10CrespoExcel1Persona:
    """T10: Crespo Excel row, 1 persona (same vendedor+cerrador) — parity with live flow."""

    def _setup(self) -> tuple[ImportarVentasExcelService, MagicMock]:
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        # buscar_regla returns 1-persona rule when called with (EXTERNO, "Crespo", 1)
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P
        # Single person: vendedor == cerrador (same name, same id)
        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente",
            fecha=datetime.date(2026, 7, 3),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),          # spreadsheet values ignored for Crespo path
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        svc, _, _, comisiones, _ = _build(
            [fila],
            punto=punto,
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )
        svc.ejecutar("x.xlsx", 7, 2026)
        return svc, comisiones

    def test_vendedor_y_cerrador_combinados(self) -> None:
        """1 persona: vendedor gets 50 000 (50%), cerrador gets 0 (0%)."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        # Combined (same person): vendedor=50000, cerrador=0
        assert desglose.vendedor == Dinero("50000.00")
        assert desglose.cerrador == Dinero("0.00")

    def test_capa(self) -> None:
        """1 persona: capa = 20% of ganancia = 20 000."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        assert desglose.punto_de_venta == Dinero("20000.00")

    def test_agencia(self) -> None:
        """1 persona: agencia (residual) = 100000 - 50000 - 0 - 20000 = 30 000."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        assert desglose.agencia == Dinero("30000.00")

    def test_suma_exacta(self) -> None:
        """Invariante: vendedor + cerrador + capa + agencia == ganancia."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        total = desglose.vendedor + desglose.cerrador + desglose.punto_de_venta + desglose.agencia
        assert total == Dinero("100000.00")

    def test_buscar_regla_called_with_crespo_1(self) -> None:
        """FIX-D: buscar_regla is called with (EXTERNO, 'Crespo', 1) for a 1-persona row."""
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P
        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test D T10",
            fecha=datetime.date(2026, 7, 3),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        svc, _, _, _, _ = _build(
            [fila],
            punto=punto,
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )
        svc.ejecutar("x.xlsx", 7, 2026)
        reglas_repo.buscar_regla.assert_called_once_with(TipoCliente.EXTERNO, "Crespo", 1)


class TestT11CrespoExcel2Personas:
    """T11: Crespo Excel row, 2 personas (different vendedor+cerrador) — parity with live flow."""

    def _setup(self) -> tuple[ImportarVentasExcelService, MagicMock]:
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        # buscar_regla returns 2-personas rule when called with (EXTERNO, "Crespo", 2)
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_2P
        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente 2",
            fecha=datetime.date(2026, 7, 4),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),          # spreadsheet values ignored for Crespo path
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        svc, _, _, comisiones, _ = _build(
            [fila],
            punto=punto,
            resolver=_freelancer_resolver_ab,
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )
        svc.ejecutar("x.xlsx", 7, 2026)
        return svc, comisiones

    def test_vendedor(self) -> None:
        """2 personas: vendedor = 30% of ganancia = 30 000."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        assert desglose.vendedor == Dinero("30000.00")

    def test_cerrador(self) -> None:
        """2 personas: cerrador = 30% of ganancia = 30 000."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        assert desglose.cerrador == Dinero("30000.00")

    def test_capa(self) -> None:
        """2 personas: capa = 20% of ganancia = 20 000."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        assert desglose.punto_de_venta == Dinero("20000.00")

    def test_agencia(self) -> None:
        """2 personas: agencia (residual) = 100000 - 30000 - 30000 - 20000 = 20 000."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        assert desglose.agencia == Dinero("20000.00")

    def test_suma_exacta(self) -> None:
        """Invariante: vendedor + cerrador + capa + agencia == ganancia."""
        _, comisiones = self._setup()
        desglose = comisiones.guardar.call_args.args[0].desglose
        total = desglose.vendedor + desglose.cerrador + desglose.punto_de_venta + desglose.agencia
        assert total == Dinero("100000.00")

    def test_buscar_regla_called_with_crespo_2(self) -> None:
        """FIX-D: buscar_regla is called with (EXTERNO, 'Crespo', 2) for a 2-persona row."""
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_2P
        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test D T11",
            fecha=datetime.date(2026, 7, 4),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        svc, _, _, _, _ = _build(
            [fila],
            punto=punto,
            resolver=_freelancer_resolver_ab,
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )
        svc.ejecutar("x.xlsx", 7, 2026)
        reglas_repo.buscar_regla.assert_called_once_with(TipoCliente.EXTERNO, "Crespo", 2)


# ---------------------------------------------------------------------------
# Fix A — Atomicity: desglose must be computed BEFORE persisting venta
# ---------------------------------------------------------------------------


class TestFixAAtomicidad:
    """FIX-A: If buscar_regla returns None (desglose raises), venta must NOT be persisted."""

    def test_crespo_desglose_raises_venta_not_persisted(self) -> None:
        """When buscar_regla returns None for a Crespo row, ReglasComisionNoEncontradas
        is raised and ventas.guardar must NOT have been called (atomicity guarantee)."""
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = None  # forces raise in _desglose

        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente Atomicidad",
            fecha=datetime.date(2026, 7, 3),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        svc, ventas, _, comisiones, _ = _build(
            [fila],
            punto=punto,
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )

        with pytest.raises(ReglasComisionNoEncontradas):
            svc.ejecutar("x.xlsx", 7, 2026)

        # Nothing must have been persisted before the error
        ventas.guardar.assert_not_called()
        comisiones.guardar.assert_not_called()


# ---------------------------------------------------------------------------
# Fix B — Blank participant on Crespo row: abort the whole import in PASS 1
# ---------------------------------------------------------------------------


class TestFixBCrespoSinParticipantes:
    """FIX-B: Crespo row with blank cerrador_nombre raises VentaCrespoSinParticipantes
    and nothing is persisted."""

    def test_crespo_sin_cerrador_aborta_importacion(self) -> None:
        """A Crespo row with cerrador_nombre=None raises VentaCrespoSinParticipantes,
        names the offending row, and leaves nothing persisted."""
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P

        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente B",
            fecha=datetime.date(2026, 7, 3),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre=None,   # blank cerrador on a Crespo row
        )
        svc, ventas, _, comisiones, _ = _build(
            [fila],
            punto=punto,
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )

        with pytest.raises(VentaCrespoSinParticipantes) as exc_info:
            svc.ejecutar("x.xlsx", 7, 2026)

        # Error must name the row number
        assert "1" in str(exc_info.value)
        ventas.guardar.assert_not_called()
        comisiones.guardar.assert_not_called()

    def test_crespo_sin_vendedor_aborta_importacion(self) -> None:
        """A Crespo row with vendedor_nombre=None raises VentaCrespoSinParticipantes."""
        punto = _crespo_punto_obj()
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P

        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente B2",
            fecha=datetime.date(2026, 7, 4),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre=None,   # blank vendedor on a Crespo row
            cerrador_nombre="Luis",
        )
        # Resolver returns a match for Luis only
        def _res(nombre: str) -> list[Freelancer]:
            return [Freelancer(id=_UUID_B, nombre=nombre)]

        svc, ventas, _, _, _ = _build(
            [fila],
            punto=punto,
            resolver=_res,
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )

        with pytest.raises(VentaCrespoSinParticipantes) as exc_info:
            svc.ejecutar("x.xlsx", 7, 2026)

        assert "1" in str(exc_info.value)
        ventas.guardar.assert_not_called()

    def test_non_crespo_blank_participant_is_valid(self) -> None:
        """Non-Crespo rows with blank cerrador remain valid (behavior unchanged)."""
        fila = FilaVentaImportada(
            canal="Externas",
            cliente_nombre="Test No Crespo",
            fecha=datetime.date(2026, 7, 5),
            descripcion="Playa tranquila",
            valor=Dinero(400000),
            neto=Dinero(300000),
            margen=Dinero(100000),
            agencia=Dinero(48000),
            comision_vendedor=Dinero(36000),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre=None,  # blank on non-Crespo row — must NOT raise
        )
        svc, ventas, _, comisiones, _ = _build(
            [fila],
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
        )

        # Must NOT raise, must persist normally
        r = svc.ejecutar("x.xlsx", 7, 2026)
        assert r.ventas_creadas == 1
        ventas.guardar.assert_called_once()
        comisiones.guardar.assert_called_once()

    def test_crespo_sin_participantes_colecta_todos_los_errores(self) -> None:
        """Multiple Crespo rows missing participants: all rows are collected in one error."""
        punto = _crespo_punto_obj()

        def _crespo_fila(
            cliente: str, vendedor: str | None, cerrador: str | None
        ) -> FilaVentaImportada:
            return FilaVentaImportada(
                canal="Crespo",
                cliente_nombre=cliente,
                fecha=datetime.date(2026, 7, 3),
                descripcion="Playa tranquila",
                valor=Dinero(500000),
                neto=Dinero(400000),
                margen=Dinero(100000),
                agencia=Dinero(0),
                comision_vendedor=Dinero(0),
                comision_cerrador=Dinero(0),
                vendedor_nombre=vendedor,
                cerrador_nombre=cerrador,
            )

        filas = [
            _crespo_fila("C1", "Ana", None),    # row 1 — missing cerrador
            _crespo_fila("C2", None, "Luis"),   # row 2 — missing vendedor
        ]
        svc, ventas, _, comisiones, _ = _build(
            filas,
            punto=punto,
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=MagicMock(),
            motor=_MOTOR_REAL,
        )

        with pytest.raises(VentaCrespoSinParticipantes) as exc_info:
            svc.ejecutar("x.xlsx", 7, 2026)

        msg = str(exc_info.value)
        assert "1" in msg
        assert "2" in msg
        ventas.guardar.assert_not_called()
        comisiones.guardar.assert_not_called()


# ---------------------------------------------------------------------------
# Fix C — Missing Crespo punto: fail loudly instead of silently zeroing capa
# ---------------------------------------------------------------------------


class TestFixCPuntoCrespoNoConfigurado:
    """FIX-C: When the batch has Crespo rows and puntos.buscar_por_nombre('Crespo')
    returns None, raise PuntoCrespoNoConfigurado before any persistence."""

    def test_crespo_batch_sin_punto_falla_antes_de_persistir(self) -> None:
        """Crespo batch with puntos returning None raises PuntoCrespoNoConfigurado
        and nothing is persisted."""
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P

        fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente C",
            fecha=datetime.date(2026, 7, 3),
            descripcion="Playa tranquila",
            valor=Dinero(500000),
            neto=Dinero(400000),
            margen=Dinero(100000),
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        svc, ventas, _, comisiones, _ = _build(
            [fila],
            punto=None,  # simulates unseeded DB: buscar_por_nombre("Crespo") returns None
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=reglas_repo,
            motor=_MOTOR_REAL,
        )

        with pytest.raises(PuntoCrespoNoConfigurado):
            svc.ejecutar("x.xlsx", 7, 2026)

        ventas.guardar.assert_not_called()
        comisiones.guardar.assert_not_called()

    def test_non_crespo_batch_sin_punto_crespo_no_falla(self) -> None:
        """A batch with no Crespo rows must succeed even when Crespo punto is absent."""
        fila = _fila(canal="Externas")
        svc, ventas, _, _, _ = _build(
            [fila],
            punto=None,  # no Crespo punto seeded
        )

        # Must NOT raise
        r = svc.ejecutar("x.xlsx", 7, 2026)
        assert r.ventas_creadas == 1
        ventas.guardar.assert_called_once()


# ---------------------------------------------------------------------------
# Fix D — Parity test: live RegistrarVentaService vs Excel ImportarVentasExcelService
# ---------------------------------------------------------------------------


class TestDParidadLiveVsExcel:
    """FIX-D: Side-by-side parity — same financials, same rules, field-by-field equal desglose.

    Proves REQ-07 directly: RegistrarVentaService (live bot flow) and
    ImportarVentasExcelService (Excel import) produce IDENTICAL DesgloseComision
    when given the same ganancia, same participants, and the same ReglasComision.
    """

    def _shared_financials(self) -> tuple[Dinero, Dinero]:
        """Returns (valor, neto) such that ganancia = valor - neto = 100 000."""
        return Dinero(500000), Dinero(400000)

    def test_parity_1_persona_desglose_identico(self) -> None:
        """1-persona Crespo: live flow and Excel flow produce the same DesgloseComision."""
        valor, neto = self._shared_financials()
        ganancia = valor - neto  # Dinero(100000)
        punto = _crespo_punto_obj()

        # Shared mock: same ReglasComision object returned from both repos
        reglas_mock = MagicMock()
        reglas_mock.buscar_regla.return_value = _CRESPO_REGLA_1P

        # --- Live flow (RegistrarVentaService) ---
        live_ventas = MagicMock()
        live_puntos = MagicMock()
        live_puntos.buscar_por_id.return_value = punto
        live_comisiones = MagicMock()
        live_svc = RegistrarVentaService(
            ventas=live_ventas,
            reglas_repo=reglas_mock,
            tiqueteras=MagicMock(),
            puntos_repo=live_puntos,
            motor=_MOTOR_REAL,
            notificador=MagicMock(),
            grupo_id="test",
            comisiones_repo=live_comisiones,
        )
        live_cmd = RegistrarVentaComando(
            valor_venta=valor,
            neto=neto,
            servicio_ids=[uuid.uuid4()],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2026, 7, 3),
            participantes=Participantes(
                vendedor_nombre="Ana",
                cerrador_nombre="Ana",
                punto_de_venta_id=punto.id,
                vendedor_id=_UUID_A,
                cerrador_id=_UUID_A,
            ),
            adultos=1,
            ninos=0,
        )
        live_resultado = live_svc.ejecutar(live_cmd)
        live_desglose = live_resultado.desglose

        # --- Excel flow (ImportarVentasExcelService) ---
        excel_reglas_repo = MagicMock()
        excel_reglas_repo.buscar_regla.return_value = _CRESPO_REGLA_1P
        excel_fila = FilaVentaImportada(
            canal="Crespo",
            cliente_nombre="Test Cliente Paridad",
            fecha=datetime.date(2026, 7, 3),
            descripcion="Playa tranquila",
            valor=valor,
            neto=neto,
            margen=ganancia,
            agencia=Dinero(0),
            comision_vendedor=Dinero(0),
            comision_cerrador=Dinero(0),
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        excel_svc, _, _, excel_comisiones, _ = _build(
            [excel_fila],
            punto=punto,
            resolver=lambda nombre: [Freelancer(id=_UUID_A, nombre=nombre)],
            reglas_repo=excel_reglas_repo,
            motor=_MOTOR_REAL,
        )
        excel_svc.ejecutar("x.xlsx", 7, 2026)
        excel_desglose = excel_comisiones.guardar.call_args.args[0].desglose

        # Field-by-field equality proves REQ-07
        assert excel_desglose.vendedor == live_desglose.vendedor
        assert excel_desglose.cerrador == live_desglose.cerrador
        assert excel_desglose.punto_de_venta == live_desglose.punto_de_venta
        assert excel_desglose.agencia == live_desglose.agencia
