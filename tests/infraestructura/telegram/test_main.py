"""Tests for the bot entry point utilities."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from garay.infraestructura.telegram.main import _ensure_ollama_running


class TestEnsureOllamaRunning:
    def test_launches_ollama_serve_in_background(self) -> None:
        with patch("garay.infraestructura.telegram.main.subprocess.Popen") as mock_popen:
            _ensure_ollama_running("ollama")
            mock_popen.assert_called_once_with(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def test_file_not_found_does_not_propagate(self) -> None:
        with patch(
            "garay.infraestructura.telegram.main.subprocess.Popen",
            side_effect=FileNotFoundError,
        ):
            _ensure_ollama_running("ollama")  # must not raise
