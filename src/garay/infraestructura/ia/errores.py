"""Errores del módulo de IA."""


class OllamaNoDisponible(Exception):
    """Raised when Ollama server is not reachable."""


class ModeloNoEncontrado(Exception):
    """Raised when the requested model is not found in Ollama (HTTP 404)."""
