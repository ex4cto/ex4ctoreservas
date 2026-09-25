"""Tests de la entidad Venta (aggregate root del modulo ventas)."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, MetodoPago, TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    AbonoSuperaValorVenta,
    CantidadInvalida,
    DigitalConPuntoDeVenta,
    GananciaNegativa,
    MismoMetodoPago,
    MonedaIncompatible,
    ValorVentaInvalido,
    VentaYaAnulada,
)
from garay.dominio.ventas.valor_objetos import Participantes


def _venta(
    valor_venta: Dinero | None = None,
    neto: Dinero | None = None,
    id: uuid.UUID | None = None,
    adultos: int = 1,
    ninos: int = 0,
    abono: Dinero | None = None,
) -> Venta:
    return Venta(
        id=id or uuid.uuid4(),
        valor_venta=valor_venta or Dinero(1_000_000),
        neto=neto or Dinero(900_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2024, 1, 15),
        participantes=Participantes(),
        adultos=adultos,
        ninos=ninos,
        abono=abono,
    )


class TestGanancia:
    def test_ganancia_calculada_correctamente(self) -> None:
        venta = _venta(Dinero(1_000_000), Dinero(900_000))
        assert venta.ganancia == Dinero(100_000)

    def test_ganancia_cero_cuando_venta_igual_neto(self) -> None:
        venta = _venta(Dinero(500_000), Dinero(500_000))
        assert venta.ganancia == Dinero("0")

    def test_ganancia_con_decimales(self) -> None:
        venta = _venta(Dinero("1000.75"), Dinero("900.25"))
        assert venta.ganancia == Dinero("100.50")


class TestValidaciones:
    def test_neto_mayor_que_venta_levanta_ganancia_negativa(self) -> None:
        with pytest.raises(GananciaNegativa):
            _venta(Dinero(500_000), Dinero(600_000))

    def test_valor_venta_cero_levanta_error(self) -> None:
        with pytest.raises(ValorVentaInvalido):
            _venta(Dinero(0), Dinero(0))

    def test_monedas_incompatibles_levanta_error(self) -> None:
        with pytest.raises(MonedaIncompatible):
            _venta(Dinero(1_000_000, "COP"), Dinero(900_000, "USD"))


class TestIdentidad:
    def test_dos_ventas_con_mismo_id_son_iguales(self) -> None:
        uid = uuid.uuid4()
        v1 = _venta(id=uid)
        v2 = _venta(id=uid)
        assert v1 == v2

    def test_dos_ventas_con_distinto_id_son_distintas(self) -> None:
        assert _venta() != _venta()

    def test_venta_no_es_igual_a_otro_tipo(self) -> None:
        assert _venta() != "no soy una venta"

    def test_estado_inicial_es_pendiente(self) -> None:
        assert _venta().estado == EstadoVenta.PENDIENTE


class TestPax:
    def test_adultos_cero_invalido(self) -> None:
        with pytest.raises(CantidadInvalida):
            _venta(adultos=0)

    def test_adultos_negativo_invalido(self) -> None:
        with pytest.raises(CantidadInvalida):
            _venta(adultos=-1)

    def test_ninos_negativo_invalido(self) -> None:
        with pytest.raises(CantidadInvalida):
            _venta(ninos=-1)


class TestAbono:
    def test_venta_abono_supera_valor_invalido(self) -> None:
        with pytest.raises(AbonoSuperaValorVenta):
            _venta(valor_venta=Dinero(500_000), neto=Dinero(400_000), abono=Dinero(600_000))

    def test_venta_abono_valido(self) -> None:
        venta = _venta(valor_venta=Dinero(1_000_000), neto=Dinero(900_000), abono=Dinero(200_000))
        assert venta.abono == Dinero(200_000)

    def test_venta_sin_abono_es_none(self) -> None:
        venta = _venta()
        assert venta.abono is None


class TestCambiarFecha:
    """B3: cambiar_fecha mutates fecha (and fechas_por_servicio when 1 entry)."""

    def _venta_con_fechas_por_servicio(
        self, sid: uuid.UUID | None = None
    ) -> tuple[Venta, uuid.UUID]:
        """Build a Venta with a single fechas_por_servicio entry."""
        sid = sid or uuid.uuid4()
        v = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero(1_000_000),
            neto=Dinero(900_000),
            servicio_ids=[sid],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2026, 8, 10),
            participantes=Participantes(),
            fechas_por_servicio={sid: datetime.datetime(2026, 8, 10, 9, 0)},
        )
        return v, sid

    def test_cambiar_fecha_actualiza_fecha_escalar(self) -> None:
        """The scalar fecha field must reflect nueva_fecha.date()."""
        venta, _ = self._venta_con_fechas_por_servicio()
        nueva = datetime.datetime(2026, 9, 15, 10, 30)

        venta.cambiar_fecha(nueva)

        assert venta.fecha == datetime.date(2026, 9, 15)

    def test_cambiar_fecha_actualiza_entrada_en_fechas_por_servicio(self) -> None:
        """When fechas_por_servicio has one entry, its value must be replaced."""
        venta, sid = self._venta_con_fechas_por_servicio()
        nueva = datetime.datetime(2026, 9, 20, 14, 0)

        venta.cambiar_fecha(nueva)

        assert venta.fechas_por_servicio is not None
        assert venta.fechas_por_servicio[sid] == nueva

    def test_cambiar_fecha_preserva_el_servicio_id_key(self) -> None:
        """The dict key (servicio_id) must not change, only the value."""
        sid = uuid.uuid4()
        venta, _ = self._venta_con_fechas_por_servicio(sid)
        nueva = datetime.datetime(2026, 10, 1, 8, 0)

        venta.cambiar_fecha(nueva)

        assert sid in venta.fechas_por_servicio  # type: ignore[operator]

    def test_cambiar_fecha_con_fechas_por_servicio_none_solo_actualiza_escalar(self) -> None:
        """If fechas_por_servicio is None, only fecha is updated — no crash."""
        venta = _venta()  # has fechas_por_servicio=None by default
        nueva = datetime.datetime(2026, 11, 5, 7, 0)

        venta.cambiar_fecha(nueva)

        assert venta.fecha == datetime.date(2026, 11, 5)
        assert venta.fechas_por_servicio is None

    def test_cambiar_fecha_venta_anulada_levanta_venta_ya_anulada(self) -> None:
        """Cannot edit an already-anulada venta."""
        venta, _ = self._venta_con_fechas_por_servicio()
        venta.anular()
        nueva = datetime.datetime(2026, 12, 1, 9, 0)

        with pytest.raises(VentaYaAnulada):
            venta.cambiar_fecha(nueva)


class TestAnular:
    """B1: soft-delete via Venta.anular()."""

    def test_venta_nueva_tiene_anulada_false(self) -> None:
        assert _venta().anulada is False

    def test_anular_cambia_anulada_a_true(self) -> None:
        venta = _venta()
        venta.anular()
        assert venta.anulada is True

    def test_anular_dos_veces_levanta_venta_ya_anulada(self) -> None:
        venta = _venta()
        venta.anular()
        with pytest.raises(VentaYaAnulada):
            venta.anular()


class TestDigitalConPuntoDeVenta:
    """WU-3: DigitalConPuntoDeVenta domain invariant (REQ-04)."""

    def test_digital_con_punto_de_venta_id_levanta_error(self) -> None:
        from garay.dominio.ventas.errores import DigitalConPuntoDeVenta

        with pytest.raises(DigitalConPuntoDeVenta):
            Venta(
                id=uuid.uuid4(),
                valor_venta=Dinero(1_000_000),
                neto=Dinero(900_000),
                servicio_ids=[uuid.uuid4()],
                cliente_id=uuid.uuid4(),
                tipo_cliente=TipoCliente.DIGITAL,
                fecha=datetime.date(2024, 1, 15),
                participantes=Participantes(punto_de_venta_id=uuid.uuid4()),
            )

    def test_digital_sin_punto_de_venta_id_valido(self) -> None:
        # DIGITAL with punto_de_venta_id=None is allowed
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero(1_000_000),
            neto=Dinero(900_000),
            servicio_ids=[uuid.uuid4()],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.DIGITAL,
            fecha=datetime.date(2024, 1, 15),
            participantes=Participantes(punto_de_venta_id=None),
        )
        assert venta.tipo_cliente == TipoCliente.DIGITAL

    def test_externo_con_punto_de_venta_id_valido(self) -> None:
        # Non-DIGITAL tipo_cliente may have punto_de_venta_id (REQ-08b)
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero(1_000_000),
            neto=Dinero(900_000),
            servicio_ids=[uuid.uuid4()],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2024, 1, 15),
            participantes=Participantes(punto_de_venta_id=uuid.uuid4()),
        )
        assert venta.tipo_cliente == TipoCliente.EXTERNO

    def test_interno_con_punto_de_venta_id_valido(self) -> None:
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero(1_000_000),
            neto=Dinero(900_000),
            servicio_ids=[uuid.uuid4()],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.INTERNO,
            fecha=datetime.date(2024, 1, 15),
            participantes=Participantes(punto_de_venta_id=uuid.uuid4()),
        )
        assert venta.tipo_cliente == TipoCliente.INTERNO


class TestFacturaIdioma:
    """factura_idioma persists the client's chosen invoice language on the sale."""

    def test_default_es(self) -> None:
        """Venta defaults factura_idioma to Spanish ("es")."""
        assert _venta().factura_idioma == "es"

    def test_acepta_en(self) -> None:
        """Venta accepts factura_idioma="en"."""
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero(1_000_000),
            neto=Dinero(900_000),
            servicio_ids=[uuid.uuid4()],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2024, 1, 15),
            participantes=Participantes(),
            factura_idioma="en",
        )
        assert venta.factura_idioma == "en"


# ---------------------------------------------------------------------------
# Task-1 RED: MismoCanal and PuntoDeVentaRequerido error classes
# ---------------------------------------------------------------------------


class TestDomainErrorsCanal:
    """editar-canal-venta: new domain error classes must exist and be ErrorDeDominio."""

    def test_mismo_canal_is_subclass_of_error_de_dominio(self) -> None:
        from garay.dominio.comun.errores import ErrorDeDominio
        from garay.dominio.ventas.errores import MismoCanal

        assert issubclass(MismoCanal, ErrorDeDominio)

    def test_punto_de_venta_requerido_is_subclass_of_error_de_dominio(self) -> None:
        from garay.dominio.comun.errores import ErrorDeDominio
        from garay.dominio.ventas.errores import PuntoDeVentaRequerido

        assert issubclass(PuntoDeVentaRequerido, ErrorDeDominio)

    def test_mismo_canal_is_instantiable(self) -> None:
        from garay.dominio.ventas.errores import MismoCanal

        err = MismoCanal("already the same")
        assert "already the same" in str(err)

    def test_punto_de_venta_requerido_is_instantiable(self) -> None:
        from garay.dominio.ventas.errores import PuntoDeVentaRequerido

        err = PuntoDeVentaRequerido("punto required")
        assert "punto required" in str(err)


# ---------------------------------------------------------------------------
# Task-3 RED: AccionAuditoria.EDITAR_CANAL enum member
# ---------------------------------------------------------------------------


class TestAccionAuditoriaEditarCanal:
    """editar-canal-venta: AccionAuditoria.EDITAR_CANAL must exist."""

    def test_editar_canal_value(self) -> None:
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_CANAL == "EDITAR_CANAL"

    def test_editar_canal_is_str_enum_member(self) -> None:
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert "EDITAR_CANAL" in [a.value for a in AccionAuditoria]


# ---------------------------------------------------------------------------
# Task-5 RED: Venta.cambiar_tipo_cliente — all 7 branches
# ---------------------------------------------------------------------------


def _venta_externo(punto_id: uuid.UUID | None = None) -> Venta:
    """EXTERNO venta with optional punto_de_venta_id (for INTERNO tests)."""
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(1_000_000),
        neto=Dinero(900_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2024, 1, 15),
        participantes=Participantes(punto_de_venta_id=punto_id),
    )


def _venta_interno(punto_id: uuid.UUID | None = None) -> Venta:
    """INTERNO venta with a punto_de_venta_id set."""
    pid = punto_id or uuid.uuid4()
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(1_000_000),
        neto=Dinero(900_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.INTERNO,
        fecha=datetime.date(2024, 1, 15),
        participantes=Participantes(punto_de_venta_id=pid),
    )


def _venta_digital() -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(1_000_000),
        neto=Dinero(900_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.DIGITAL,
        fecha=datetime.date(2024, 1, 15),
        participantes=Participantes(punto_de_venta_id=None),
    )


class TestCambiarTipoCliente:
    """editar-canal-venta: Venta.cambiar_tipo_cliente — all 7 branches."""

    # Branch 1: anulada venta → raises VentaYaAnulada
    def test_anulada_venta_raises_venta_ya_anulada(self) -> None:
        venta = _venta_externo()
        venta.anular()
        with pytest.raises(VentaYaAnulada):
            venta.cambiar_tipo_cliente(TipoCliente.INTERNO, uuid.uuid4())

    # Branch 2: mismo tipo_cliente → raises MismoCanal
    def test_mismo_tipo_raises_mismo_canal(self) -> None:
        from garay.dominio.ventas.errores import MismoCanal

        venta = _venta_externo()
        with pytest.raises(MismoCanal):
            venta.cambiar_tipo_cliente(TipoCliente.EXTERNO)

    # Branch 3: INTERNO with punto_id=None → raises PuntoDeVentaRequerido
    def test_interno_sin_punto_raises_punto_de_venta_requerido(self) -> None:
        from garay.dominio.ventas.errores import PuntoDeVentaRequerido

        venta = _venta_externo()
        with pytest.raises(PuntoDeVentaRequerido):
            venta.cambiar_tipo_cliente(TipoCliente.INTERNO, None)

    # Branch 4: EXTERNO → clears participantes.punto_de_venta_id to None
    def test_externo_clears_punto_de_venta_id(self) -> None:
        pid = uuid.uuid4()
        venta = _venta_interno(punto_id=pid)
        venta.cambiar_tipo_cliente(TipoCliente.EXTERNO)
        assert venta.participantes.punto_de_venta_id is None
        assert venta.tipo_cliente == TipoCliente.EXTERNO

    # Branch 5: DIGITAL → clears participantes.punto_de_venta_id to None
    def test_digital_clears_punto_de_venta_id(self) -> None:
        pid = uuid.uuid4()
        venta = _venta_interno(punto_id=pid)
        venta.cambiar_tipo_cliente(TipoCliente.DIGITAL)
        assert venta.participantes.punto_de_venta_id is None
        assert venta.tipo_cliente == TipoCliente.DIGITAL

    # Branch 6: DIGITAL with non-null punto_id → raises DigitalConPuntoDeVenta
    # (This tests passing punto_id explicitly when target is DIGITAL — not a
    # real use-case but the guard must fire if implementation accidentally leaves
    # a non-null punto_de_venta_id with DIGITAL type.)
    def test_digital_with_punto_id_arg_raises_digital_con_punto(self) -> None:
        venta = _venta_externo()
        with pytest.raises(DigitalConPuntoDeVenta):
            venta.cambiar_tipo_cliente(TipoCliente.DIGITAL, uuid.uuid4())

    # Branch 7: INTERNO with valid punto_id → sets participantes.punto_de_venta_id
    # and tipo_cliente atomically; canal_origen is NOT changed
    def test_interno_con_punto_sets_atomically(self) -> None:
        venta = _venta_externo()
        original_canal = venta.canal_origen
        pid = uuid.uuid4()

        venta.cambiar_tipo_cliente(TipoCliente.INTERNO, pid)

        assert venta.participantes.punto_de_venta_id == pid
        assert venta.tipo_cliente == TipoCliente.INTERNO
        # canal_origen MUST NOT change
        assert venta.canal_origen == original_canal

    def test_interno_punto_de_venta_id_is_set_from_arg(self) -> None:
        """The punto_de_venta_id stored must equal the punto_id argument, not something else."""
        venta = _venta_externo()
        pid = uuid.uuid4()
        venta.cambiar_tipo_cliente(TipoCliente.INTERNO, pid)
        assert venta.participantes.punto_de_venta_id == pid

    def test_participantes_is_replaced_not_mutated(self) -> None:
        """Participantes is frozen; cambiar_tipo_cliente must produce a new instance."""
        venta = _venta_externo()
        old_participantes = venta.participantes
        pid = uuid.uuid4()

        venta.cambiar_tipo_cliente(TipoCliente.INTERNO, pid)

        # A new Participantes instance must have been created
        assert venta.participantes is not old_participantes


# ---------------------------------------------------------------------------
# Venta.cambiar_participantes
# ---------------------------------------------------------------------------


def _venta_con_participantes(
    vendedor_id: uuid.UUID | None = None,
    vendedor_nombre: str | None = "Ana",
    cerrador_id: uuid.UUID | None = None,
    cerrador_nombre: str | None = "Luis",
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(1_000_000),
        neto=Dinero(900_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2024, 1, 15),
        participantes=Participantes(
            vendedor_id=vendedor_id or uuid.uuid4(),
            vendedor_nombre=vendedor_nombre,
            cerrador_id=cerrador_id or uuid.uuid4(),
            cerrador_nombre=cerrador_nombre,
        ),
    )


class TestVentaCambiarParticipantes:
    def test_cambia_vendedor_correctamente(self) -> None:
        from garay.dominio.ventas.errores import MismosParticipantes

        venta = _venta_con_participantes()
        nuevo_id = uuid.uuid4()

        venta.cambiar_participantes(
            nuevo_vendedor_id=nuevo_id,
            nuevo_vendedor_nombre="Pedro",
            nuevo_cerrador_id=venta.participantes.cerrador_id,
            nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
        )

        assert venta.participantes.vendedor_id == nuevo_id
        assert venta.participantes.vendedor_nombre == "Pedro"
        # cerrador unchanged
        assert venta.participantes.cerrador_nombre == "Luis"

    def test_cambia_cerrador_correctamente(self) -> None:
        venta = _venta_con_participantes()
        nuevo_id = uuid.uuid4()

        venta.cambiar_participantes(
            nuevo_vendedor_id=venta.participantes.vendedor_id,
            nuevo_vendedor_nombre=venta.participantes.vendedor_nombre,
            nuevo_cerrador_id=nuevo_id,
            nuevo_cerrador_nombre="Carlos",
        )

        assert venta.participantes.cerrador_id == nuevo_id
        assert venta.participantes.cerrador_nombre == "Carlos"
        # vendedor unchanged
        assert venta.participantes.vendedor_nombre == "Ana"

    def test_lanza_venta_ya_anulada(self) -> None:
        venta = _venta_con_participantes()
        venta.anular()

        with pytest.raises(VentaYaAnulada):
            venta.cambiar_participantes(
                nuevo_vendedor_id=uuid.uuid4(),
                nuevo_vendedor_nombre="Pedro",
                nuevo_cerrador_id=venta.participantes.cerrador_id,
                nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
            )

    def test_lanza_mismos_participantes_si_sin_cambios(self) -> None:
        from garay.dominio.ventas.errores import MismosParticipantes

        venta = _venta_con_participantes()

        with pytest.raises(MismosParticipantes):
            venta.cambiar_participantes(
                nuevo_vendedor_id=venta.participantes.vendedor_id,
                nuevo_vendedor_nombre=venta.participantes.vendedor_nombre,
                nuevo_cerrador_id=venta.participantes.cerrador_id,
                nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
            )

    def test_participantes_instance_replaced(self) -> None:
        venta = _venta_con_participantes()
        old = venta.participantes
        nuevo_id = uuid.uuid4()

        venta.cambiar_participantes(
            nuevo_vendedor_id=nuevo_id,
            nuevo_vendedor_nombre="Pedro",
            nuevo_cerrador_id=venta.participantes.cerrador_id,
            nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
        )

        assert venta.participantes is not old


# ---------------------------------------------------------------------------
# TestCambiarMetodoPago
# ---------------------------------------------------------------------------


class TestCambiarMetodoPago:
    def test_success_cambia_metodo_pago(self) -> None:
        """cambiar_metodo_pago must update metodo_pago on the entity."""
        venta = _venta()
        venta.metodo_pago = MetodoPago.TRANSFERENCIA
        venta.cambiar_metodo_pago(MetodoPago.EFECTIVO)
        assert venta.metodo_pago == MetodoPago.EFECTIVO

    def test_mismo_metodo_pago_raises_mismo_metodo_pago(self) -> None:
        """Idempotency guard: raises MismoMetodoPago when nuevo equals current."""
        venta = _venta()
        venta.metodo_pago = MetodoPago.EFECTIVO
        with pytest.raises(MismoMetodoPago):
            venta.cambiar_metodo_pago(MetodoPago.EFECTIVO)

    def test_venta_anulada_raises_venta_ya_anulada(self) -> None:
        """Raises VentaYaAnulada when venta.anulada is True."""
        venta = _venta()
        venta.metodo_pago = MetodoPago.TRANSFERENCIA
        venta.anulada = True
        with pytest.raises(VentaYaAnulada):
            venta.cambiar_metodo_pago(MetodoPago.EFECTIVO)
