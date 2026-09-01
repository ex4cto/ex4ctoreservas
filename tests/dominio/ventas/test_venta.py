"""Tests de la entidad Venta (aggregate root del modulo ventas)."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    AbonoSuperaValorVenta,
    CantidadInvalida,
    GananciaNegativa,
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
