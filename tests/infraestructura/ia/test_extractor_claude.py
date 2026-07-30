"""Tests for ExtractorClaude — Claude vision API adapter."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock

from garay.infraestructura.ia.extractor_claude import ExtractorClaude


class TestExtractorClaudeInit:
    def test_instancia_con_parametros_minimos(self) -> None:
        extractor = ExtractorClaude(api_key="sk-test")
        assert extractor is not None


class TestExtractorClaudeExtraerDeFoto:
    def _make_response(self, payload: dict[str, object]) -> MagicMock:
        block = MagicMock(spec=TextBlock)
        block.text = json.dumps(payload)
        msg = MagicMock()
        msg.content = [block]
        return msg

    def test_extrae_campos_correctamente(self, tmp_path: Path) -> None:
        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        payload = {
            "numero_ticket": "0845",
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
        assert result.numero_ticket == "0845"

    def test_respuesta_json_invalida_retorna_confianza_cero(self, tmp_path: Path) -> None:
        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        with patch("garay.infraestructura.ia.extractor_claude.anthropic.Anthropic") as mock_cls:
            msg = MagicMock()
            msg.content = [MagicMock(text="no es json en absoluto")]
            mock_cls.return_value.messages.create.return_value = msg
            extractor = ExtractorClaude(api_key="sk-test")
            result = extractor.extraer_de_foto(str(foto))

        assert result.confianza == Decimal("0")

    def test_json_envuelto_en_markdown_se_parsea_correctamente(self, tmp_path: Path) -> None:
        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        payload = {
            "numero_ticket": "7",
            "nombre_cliente": "Ana Lopez",
            "telefono": None,
            "destinos": ["Playa Blanca"],
            "fecha_salida": None,
            "adultos": 1,
            "ninos": 0,
            "valor": None,
            "abono": None,
            "vendedor": None,
            "confianza": 0.8,
        }
        raw_with_fences = f"```json\n{json.dumps(payload)}\n```"

        with patch("garay.infraestructura.ia.extractor_claude.anthropic.Anthropic") as mock_cls:
            msg = MagicMock()
            msg.content = [MagicMock(spec=TextBlock, text=raw_with_fences)]
            mock_cls.return_value.messages.create.return_value = msg
            extractor = ExtractorClaude(api_key="sk-test")
            result = extractor.extraer_de_foto(str(foto))

        assert result.nombre_cliente == "Ana Lopez"
        assert result.confianza == Decimal("0.8")
        assert result.numero_ticket == "7"

    def test_numero_con_cero_inicial_se_parsea_correctamente(self, tmp_path: Path) -> None:
        foto = tmp_path / "ticket.jpg"
        foto.write_bytes(b"fake-image")

        raw_with_leading_zero = (
            '```json\n{"numero_ticket": null, "nombre_cliente": null, "telefono": null,'
            ' "cliente_hotel": null, "numero_habitacion": null, "destinos": [],'
            ' "fecha_salida": null, "adultos": 2, "ninos": 1,'
            ' "valor": 226000, "abono": 0845, "vendedor": null, "confianza": 0.55}\n```'
        )

        with patch("garay.infraestructura.ia.extractor_claude.anthropic.Anthropic") as mock_cls:
            msg = MagicMock()
            msg.content = [MagicMock(spec=TextBlock, text=raw_with_leading_zero)]
            mock_cls.return_value.messages.create.return_value = msg
            extractor = ExtractorClaude(api_key="sk-test")
            result = extractor.extraer_de_foto(str(foto))

        assert result.abono is not None
        assert result.abono.monto == Decimal("845")
        assert result.adultos == 2

    def test_auth_error_lanza_excepcion(self, tmp_path: Path) -> None:
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
