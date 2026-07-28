"""Tests for ExtractorClaude — Claude vision API adapter."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock

from garay.infraestructura.ia.extractor_claude import ExtractorClaude


class TestExtractorClaudeInit:
    def test_instancia_con_parametros_minimos(self) -> None:
        extractor = ExtractorClaude(api_key="sk-test")
        assert extractor is not None


class TestExtractorClaudeExtraerDeFoto:
    def _make_response(self, payload: dict) -> MagicMock:
        block = MagicMock(spec=TextBlock)
        block.text = json.dumps(payload)
        msg = MagicMock()
        msg.content = [block]
        return msg

    def test_extrae_campos_correctamente(self, tmp_path) -> None:
        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        payload = {
            "numero_ticket": 42,
            "nombre_cliente": "Juan Perez",
            "telefono": "3001234567",
            "destinos": ["Playa Blanca"],
            "fecha_salida": "15/08/2025",
            "adultos": 2,
            "ninos": 1,
            "valor": 500000,
            "abono": 100000,
            "vendedor": None,
            "confianza": 0.9,
        }

        with patch("garay.infraestructura.ia.extractor_claude.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = self._make_response(payload)
            extractor = ExtractorClaude(api_key="sk-test")
            result = extractor.extraer_de_foto(str(foto))

        assert result.nombre_cliente == "Juan Perez"
        assert result.adultos == 2
        assert result.confianza == Decimal("0.9")
        assert result.numero_ticket == 42

    def test_respuesta_json_invalida_retorna_confianza_cero(self, tmp_path) -> None:
        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        with patch("garay.infraestructura.ia.extractor_claude.anthropic.Anthropic") as mock_cls:
            msg = MagicMock()
            msg.content = [MagicMock(text="no es json")]
            mock_cls.return_value.messages.create.return_value = msg
            extractor = ExtractorClaude(api_key="sk-test")
            result = extractor.extraer_de_foto(str(foto))

        assert result.confianza == Decimal("0")

    def test_auth_error_lanza_excepcion(self, tmp_path) -> None:
        import anthropic

        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        with patch("garay.infraestructura.ia.extractor_claude.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                message="invalid key", response=MagicMock(), body={}
            )
            extractor = ExtractorClaude(api_key="sk-bad")
            with pytest.raises(anthropic.AuthenticationError):
                extractor.extraer_de_foto(str(foto))
