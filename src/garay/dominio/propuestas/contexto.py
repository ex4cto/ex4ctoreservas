"""Contexto de dominio para la generación de propuestas comerciales.

Empieza mínimo (solo el nombre de la empresa) y crece con los campos que defina
el UX del comando. Reemplaza el paso de strings sueltos: el servicio de
aplicación recibe este contexto tipado, no argumentos crudos.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropuestaContexto:
    """Datos variables de una propuesta para una empresa."""

    empresa_nombre: str
