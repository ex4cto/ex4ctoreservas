"""Tests for ExtractorReservaFoto — maps DatosExtraidos → ContextoVenta.

Uses a mock of the ExtractorIA port (not any concrete extractor directly).
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.servicios_externos import ExtractorIA
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.infraestructura.ia.extractor_reserva import ExtractorReservaFoto


@pytest.fixture()
def mock_extractor_ia() -> MagicMock:
    """Mock of the ExtractorIA port."""
    mock = MagicMock(spec=ExtractorIA)
    return mock


@pytest.fixture()
def extractor(mock_extractor_ia: MagicMock) -> ExtractorReservaFoto:
    return ExtractorReservaFoto(extractor_ia=mock_extractor_ia)


def _datos_vacios() -> DatosExtraidos:
    return DatosExtraidos()


class TestExtractorReservaFoto:
    def test_mapeo_completo(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 1 — all populated fields map correctly."""
        fecha = datetime.datetime(2025, 8, 15, 8, 30)
        datos = DatosExtraidos(
            valor_venta=Dinero(Decimal("500000")),
            neto=Dinero(Decimal("450000")),
            abono=Dinero(Decimal("100000")),
            nombre_cliente="Juan Perez",
            telefono="3001234567",
            cliente_hotel="Hotel Playa",
            numero_habitacion="101",
            servicio_nombre="Carlos",
            destinos=("Tour Playa Blanca", "City Tour"),
            fecha_salida=fecha,
            adultos=2,
            ninos=1,
            numero_ticket=42,
        )
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"fake-bytes")

        assert ctx.valor == Decimal("500000.00")
        assert ctx.neto == Decimal("450000.00")
        assert ctx.abono == Decimal("100000.00")
        assert ctx.cliente_nombre == "Juan Perez"
        assert ctx.cliente_telefono == "3001234567"
        assert ctx.cliente_hotel == "Hotel Playa"
        assert ctx.cliente_habitacion == "101"
        assert ctx.fecha_salida == fecha
        assert ctx.adultos == 2
        assert ctx.ninos == 1

    def test_numero_ticket_mapea_a_numero_fisico(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 2 — numero_ticket → numero_fisico (name trap)."""
        datos = DatosExtraidos(numero_ticket=42)
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.numero_fisico == 42

    def test_servicio_nombre_es_ignorado(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 3 — servicio_nombre must NOT appear in any ContextoVenta field."""
        datos = DatosExtraidos(servicio_nombre="Carlos")
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        for field_val in [
            ctx.cliente_nombre,
            ctx.cliente_telefono,
            ctx.cliente_hotel,
            ctx.cliente_habitacion,
            ctx.vendedor_nombre,
            ctx.cerrador_nombre,
            ctx.referido_nombre,
            ctx.punto_de_venta_nombre,
            ctx.rol_registrante,
        ]:
            assert field_val != "Carlos"
        assert "Carlos" not in ctx.destinos_nombres

    def test_destinos_tuple_a_destinos_nombres_list(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 4 — destinos tuple → destinos_nombres list."""
        datos = DatosExtraidos(destinos=("Ciudad Perdida",))
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.destinos_nombres == ["Ciudad Perdida"]

    def test_destinos_vacia_produce_lista_vacia(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 5 — empty destinos tuple → empty destinos_nombres list."""
        datos = DatosExtraidos(destinos=())
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.destinos_nombres == []

    def test_adultos_none_devuelve_none(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 6 — adultos=None → ctx.adultos == None."""
        datos = DatosExtraidos(adultos=None)
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.adultos is None

    def test_adultos_cero_devuelve_cero(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 7 — adultos=0 → ctx.adultos == 0."""
        datos = DatosExtraidos(adultos=0)
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.adultos == 0

    def test_dinero_a_decimal(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 8 — Dinero.monto is correctly extracted to Decimal."""
        datos = DatosExtraidos(valor_venta=Dinero(Decimal("500000")))
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.valor == Decimal("500000.00")

    def test_campos_no_extraibles_quedan_en_default(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 9 — unmapped fields stay at their defaults."""
        datos = _datos_vacios()
        mock_extractor_ia.extraer_de_foto.return_value = datos

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink"):
            ctx = extractor.extraer_de_foto(b"bytes")

        assert ctx.tipo_cliente is None
        assert ctx.destinos_numeros == []
        assert ctx.vendedor_nombre is None

    def test_temp_file_eliminado_cuando_extractor_lanza_excepcion(
        self, extractor: ExtractorReservaFoto, mock_extractor_ia: MagicMock
    ) -> None:
        """Scenario 10 — temp file is cleaned up even when ExtractorIA raises."""
        mock_extractor_ia.extraer_de_foto.side_effect = RuntimeError("fallo")

        with patch("garay.infraestructura.ia.extractor_reserva.os.unlink") as mock_unlink:
            with pytest.raises(RuntimeError):
                extractor.extraer_de_foto(b"bytes")
            mock_unlink.assert_called_once()
