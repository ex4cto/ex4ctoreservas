"""Category constants for expense classification.

Single source of truth for expense category identifiers.
No imports from infraestructura/ or aplicacion/.
"""

from __future__ import annotations

import difflib
import unicodedata
from collections.abc import Iterable
from typing import Final

CATEGORIA_TRANSPORTE: Final[str] = "transporte"
CATEGORIA_OTRO: Final[str] = "otro"

# Categorias que el codigo referencia como destino fijo de la clasificacion
# automatica (banco_a_categoria). No pueden desactivarse ni renombrarse desde
# la gestion de categorias: hacerlo romperia la clasificacion de egresos del banco.
CATEGORIAS_PROTEGIDAS: Final[frozenset[str]] = frozenset(
    [CATEGORIA_TRANSPORTE, CATEGORIA_OTRO]
)

# Umbral de similitud (0..1) para sugerir una categoria existente parecida.
_UMBRAL_PARECIDO: Final[float] = 0.8

_BANCOS_TRANSPORTE: frozenset[str] = frozenset(["Uber", "DiDi"])


def banco_a_categoria(banco: str) -> str:
    """Return the expense category for a given bank identifier.

    Returns CATEGORIA_TRANSPORTE for Uber and DiDi.
    Returns CATEGORIA_OTRO for all other banks.
    """
    if banco in _BANCOS_TRANSPORTE:
        return CATEGORIA_TRANSPORTE
    return CATEGORIA_OTRO


def _clave(nombre: str) -> str:
    """Normaliza un nombre para comparar: minusculas, sin acentos, sin espacios extra."""
    sin_acentos = "".join(
        c
        for c in unicodedata.normalize("NFKD", nombre)
        if not unicodedata.combining(c)
    )
    return " ".join(sin_acentos.lower().split())


def es_categoria_protegida(nombre: str) -> bool:
    """True si el nombre corresponde a una categoria protegida (transporte / otro)."""
    return nombre.strip().lower() in CATEGORIAS_PROTEGIDAS


def es_categoria_duplicada(nombre: str, existentes: Iterable[str]) -> bool:
    """True si ``nombre`` ya existe (ignorando mayusculas, acentos y espacios)."""
    objetivo = _clave(nombre)
    return any(_clave(e) == objetivo for e in existentes)


def sugerir_categoria_parecida(
    nombre: str,
    existentes: Iterable[str],
    *,
    umbral: float = _UMBRAL_PARECIDO,
) -> str | None:
    """Devuelve una categoria existente parecida a ``nombre``, o None.

    Compara ignorando mayusculas y acentos (difflib). Un match exacto normalizado
    NO se sugiere (eso es un duplicado, se maneja aparte). Sirve para atajar
    errores de escritura al crear una categoria nueva (ej: "papleria" -> "Papeleria").
    """
    objetivo = _clave(nombre)
    por_clave = {_clave(e): e for e in existentes}
    if objetivo in por_clave:
        return None
    parecidas = difflib.get_close_matches(objetivo, list(por_clave), n=1, cutoff=umbral)
    return por_clave[parecidas[0]] if parecidas else None
