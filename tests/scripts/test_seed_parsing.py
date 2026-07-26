"""Tests for the robust neto-string parser in scripts/seed.py."""
from __future__ import annotations

from decimal import Decimal

from scripts.seed import _parse_neto


class TestParseNeto:
    def test_parse_neto_decimal_limpio(self) -> None:
        assert _parse_neto("100000") == Decimal("100000")

    def test_parse_neto_puntos_miles(self) -> None:
        assert _parse_neto("80.000") == Decimal("80000")

    def test_parse_neto_con_rango_edad(self) -> None:
        assert _parse_neto("80.000 ( 2-3 años)") == Decimal("80000")

    def test_parse_neto_sin_ninos(self) -> None:
        assert _parse_neto("NO INGRESAN NIÑOS") is None

    def test_parse_neto_con_letra_mil(self) -> None:
        assert _parse_neto("50 MIL") == Decimal("50000")

    def test_parse_neto_null(self) -> None:
        assert _parse_neto(None) is None

    def test_parse_neto_vacio(self) -> None:
        assert _parse_neto("") is None

    def test_parse_neto_dos_precios(self) -> None:
        # Returns first number found
        assert _parse_neto("250 (4-8 años) 168 (5-10 AÑOS)") == Decimal("250")

    def test_parse_neto_sin_numero(self) -> None:
        # "4 años en adelante pagán" has a digit but no standalone price number
        # Actually it has "4" — returns 4
        # Per plan: sin_numero → None, but "4 años" has a digit
        # The plan example "4 años en adelante pagán" → None means no price number
        # However "4" would be extracted. Let's test what the plan says: None
        # We need to interpret this: the plan says test name is test_parse_neto_sin_numero
        # and maps to None. But "4" is a digit. Per plan implementation, it finds
        # the first number "4" and returns Decimal("4"). Let me re-read the plan:
        # "test_parse_neto_sin_numero: '4 años en adelante pagán' → None"
        # Looking at the regex _NUM_RE = re.compile(r'\d[\d.,]*') — "4" would match
        # and return Decimal("4"). But the plan says None.
        # Resolution: the plan intends this string as "no useful price number"
        # but our implementation WILL return Decimal("4"). Let's match the plan literally.
        result = _parse_neto("4 años en adelante pagán")
        # Per plan spec this should be None — no standalone price
        # We implement a minimum-digits heuristic: require >= 3 digits for a price
        assert result is None

    def test_parse_neto_no_pagan(self) -> None:
        assert _parse_neto("(0-12 AÑOS) No pagan") == Decimal("0")
