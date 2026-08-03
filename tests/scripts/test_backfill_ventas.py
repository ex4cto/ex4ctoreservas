"""Tests for the ventas freelancer-id backfill alias resolution."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backfill_ventas_freelancer_id.py"
_spec = importlib.util.spec_from_file_location("backfill_ventas_freelancer_id", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
resolver_id = _mod.resolver_id

_KIKE = uuid.uuid4()
_MAIRELIS = uuid.uuid4()
_ZAIDA = uuid.uuid4()
_EDUARDO = uuid.uuid4()
_IDS = {
    "kike": _KIKE,
    "mairelis": _MAIRELIS,
    "zaida": _ZAIDA,
    "eduardo": _EDUARDO,
    "maximo": uuid.uuid4(),
    "garay": uuid.uuid4(),
}


def test_alias_divergente_mapea() -> None:
    assert resolver_id("Mairele", _IDS) == _MAIRELIS
    assert resolver_id("Maximar", _IDS) == _IDS["maximo"]
    assert resolver_id("Saida", _IDS) == _ZAIDA


def test_variantes_de_caso_kike_fusionan() -> None:
    assert resolver_id("KiKe", _IDS) == _KIKE
    assert resolver_id("kike", _IDS) == _KIKE
    assert resolver_id("Kike ", _IDS) == _KIKE


def test_nombre_directo() -> None:
    assert resolver_id("Eduardo", _IDS) == _EDUARDO
    assert resolver_id("garay", _IDS) == _IDS["garay"]


def test_externos_quedan_none() -> None:
    assert resolver_id("Ruth", _IDS) is None
    assert resolver_id("Hebert", _IDS) is None


def test_blanco_es_none() -> None:
    assert resolver_id("", _IDS) is None
    assert resolver_id(None, _IDS) is None
    assert resolver_id("   ", _IDS) is None


def test_target_sin_freelancer_es_none() -> None:
    # "mairele" maps to "Mairelis", but if that freelancer is absent -> None
    assert resolver_id("Mairele", {"eduardo": _EDUARDO}) is None
