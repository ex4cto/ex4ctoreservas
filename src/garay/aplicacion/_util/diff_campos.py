"""Utility: compute per-field diff between two entity snapshots.

Returns a list of (campo, valor_anterior, valor_nuevo) tuples for every field
whose value changed. Only fields present in both dicts are compared.

Serialization rules:
- dict values (e.g. netos_por_horario): serialize via json.dumps(sort_keys=True,
  ensure_ascii=False) after converting inner Decimal values to str.
- All other values: str(value).
"""

from __future__ import annotations

import json
from typing import Any


def _serializar(valor: Any) -> str:
    """Convert a field value to a canonical string for audit storage."""
    if isinstance(valor, dict):
        return json.dumps(
            {k: str(v) for k, v in valor.items()},
            sort_keys=True,
            ensure_ascii=False,
        )
    return str(valor)


def calcular_diff(
    viejo: dict[str, Any],
    nuevo: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """Return one (campo, valor_anterior, valor_nuevo) tuple per changed field.

    Only keys present in *both* dicts are compared. Extra keys in either dict
    are silently ignored.
    """
    resultado: list[tuple[str, str, str]] = []
    for campo in viejo:
        if campo not in nuevo:
            continue
        v_viejo = viejo[campo]
        v_nuevo = nuevo[campo]
        # Normalize for comparison: dicts compared as canonical JSON,
        # Decimals compared numerically, rest compared as str.
        if isinstance(v_viejo, dict) or isinstance(v_nuevo, dict):
            s_viejo = _serializar(v_viejo)
            s_nuevo = _serializar(v_nuevo)
        else:
            s_viejo = str(v_viejo)
            s_nuevo = str(v_nuevo)
        if s_viejo != s_nuevo:
            resultado.append((campo, s_viejo, s_nuevo))
    return resultado
