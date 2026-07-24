"""Tests for ExtractorOllama — parser logic, no real HTTP calls."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from garay.infraestructura.ia.errores import OllamaNoDisponible
from garay.infraestructura.ia.extractor_ollama import ExtractorOllama


def _make_response(payload: dict) -> MagicMock:
    """Build a mock urllib response that returns JSON bytes."""
    envelope = {"response": json.dumps(payload)}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(envelope).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_extractor(tmp_path) -> tuple[ExtractorOllama, str]:
    """Create an extractor and a fake image file."""
    img = tmp_path / "ticket.jpg"
    img.write_bytes(b"fake-image")
    return ExtractorOllama(), str(img)


class TestExtractorOllamaParser:
    def test_extraer_campos_completos(self, tmp_path) -> None:
        extractor, ruta = _make_extractor(tmp_path)
        payload = {
            "numero_ticket": 42,
            "nombre_cliente": "Juan Perez",
            "telefono": "3001234567",
            "cliente_hotel": "Hotel Playa",
            "numero_habitacion": "101",
            "destinos": ["Cartagena", "Baru"],
            "fecha_salida": "15/08/2025 08:30",
            "adultos": 2,
            "ninos": 1,
            "valor": 350000.0,
            "abono": 100000.0,
            "vendedor": "Carlos",
            "confianza": 0.92,
        }
        mock_resp = _make_response(payload)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extractor.extraer_de_foto(ruta)

        assert result.numero_ticket == 42
        assert result.nombre_cliente == "Juan Perez"
        assert result.telefono == "3001234567"
        assert result.cliente_hotel == "Hotel Playa"
        assert result.numero_habitacion == "101"
        assert result.destinos == ("Cartagena", "Baru")
        assert result.adultos == 2
        assert result.ninos == 1
        assert result.valor_venta is not None
        assert result.abono is not None
        assert result.confianza == Decimal("0.92")
        assert result.fecha_salida is not None
        assert result.fecha_salida.day == 15
        assert result.fecha_salida.month == 8

    def test_extraer_campos_parciales(self, tmp_path) -> None:
        extractor, ruta = _make_extractor(tmp_path)
        payload = {
            "numero_ticket": None,
            "nombre_cliente": "Ana",
            "telefono": None,
            "cliente_hotel": None,
            "numero_habitacion": None,
            "destinos": [],
            "fecha_salida": None,
            "adultos": None,
            "ninos": None,
            "valor": None,
            "abono": None,
            "vendedor": None,
            "confianza": 0.5,
        }
        mock_resp = _make_response(payload)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extractor.extraer_de_foto(ruta)

        assert result.nombre_cliente == "Ana"
        assert result.numero_ticket is None
        assert result.valor_venta is None
        assert result.abono is None
        assert result.fecha_salida is None
        assert result.destinos == ()
        assert result.confianza == Decimal("0.5")

    def test_confianza_clamped_sobre_1(self, tmp_path) -> None:
        extractor, ruta = _make_extractor(tmp_path)
        payload = {
            "numero_ticket": None,
            "nombre_cliente": None,
            "telefono": None,
            "cliente_hotel": None,
            "numero_habitacion": None,
            "destinos": [],
            "fecha_salida": None,
            "adultos": None,
            "ninos": None,
            "valor": None,
            "abono": None,
            "vendedor": None,
            "confianza": 2.5,
        }
        mock_resp = _make_response(payload)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extractor.extraer_de_foto(ruta)

        assert result.confianza == Decimal("1")

    def test_respuesta_json_invalida_devuelve_confianza_cero(self, tmp_path) -> None:
        extractor, ruta = _make_extractor(tmp_path)
        envelope = {"response": "no json aqui"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(envelope).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extractor.extraer_de_foto(ruta)

        assert result.confianza == Decimal("0")

    def test_destinos_como_tuple(self, tmp_path) -> None:
        extractor, ruta = _make_extractor(tmp_path)
        payload = {
            "numero_ticket": None,
            "nombre_cliente": None,
            "telefono": None,
            "cliente_hotel": None,
            "numero_habitacion": None,
            "destinos": ["Isla Baru", "Playa Blanca"],
            "fecha_salida": None,
            "adultos": None,
            "ninos": None,
            "valor": None,
            "abono": None,
            "vendedor": None,
            "confianza": 0.8,
        }
        mock_resp = _make_response(payload)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extractor.extraer_de_foto(ruta)

        assert isinstance(result.destinos, tuple)
        assert result.destinos == ("Isla Baru", "Playa Blanca")

    def test_ollama_no_disponible_lanza_error(self, tmp_path) -> None:
        extractor, ruta = _make_extractor(tmp_path)

        with (
            patch("urllib.request.urlopen", side_effect=ConnectionRefusedError()),
            pytest.raises(OllamaNoDisponible),
        ):
            extractor.extraer_de_foto(ruta)
