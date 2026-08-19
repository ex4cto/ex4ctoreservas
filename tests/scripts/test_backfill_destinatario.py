"""Tests for the destinatario backfill extraction function.

These tests drive the pure function `extraer_destinatario(descripcion) -> str | None`
in scripts/backfill_destinatario_egresos.py.  Every pattern here corresponds
EXACTLY to the f-string template the live parser produces — if a template
changes, these tests catch the drift.

Pattern table (order matters — cuenta BEFORE generic transferencia):
  1. "Transferencia a cuenta *{digits}"  ->  "*{digits}"
  2. "Transferencia a {nombre}"          ->  nombre
  3. "Compra en {comercio}"              ->  comercio
  4. "Envio a {nombre}"                  ->  nombre
  5. "Pago en {comercio}"                ->  comercio
  6. "Pago PSE a {empresa}"              ->  empresa
  Skip-list (always None):
     "Pago factura Nequi"
  Non-match (free-form):                 ->  None
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

# ---------------------------------------------------------------------------
# Load the script module WITHOUT executing main()
# ---------------------------------------------------------------------------
_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "backfill_destinatario_egresos.py"
)
_spec = importlib.util.spec_from_file_location("backfill_destinatario_egresos", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

extraer_destinatario: Callable[[str], str | None] = _mod.extraer_destinatario


# ---------------------------------------------------------------------------
# Pattern 1 — "Transferencia a cuenta *{digits}"
# Must match BEFORE the generic "Transferencia a {nombre}" branch.
# ---------------------------------------------------------------------------


class TestExtraccionTransferenciaCuenta:
    def test_cuenta_digitos_cortos(self) -> None:
        assert extraer_destinatario("Transferencia a cuenta *4321") == "*4321"

    def test_cuenta_digitos_largos_prod(self) -> None:
        # Real prod sample: "Transferencia a cuenta *08600002475"
        assert (
            extraer_destinatario("Transferencia a cuenta *08600002475") == "*08600002475"
        )

    def test_cuenta_no_pierde_asterisco(self) -> None:
        result = extraer_destinatario("Transferencia a cuenta *3207904880")
        assert result is not None
        assert result.startswith("*")
        assert result == "*3207904880"

    def test_cuenta_no_interfiere_con_nombre(self) -> None:
        # A transferencia-nombre should NOT be caught by the cuenta pattern
        result = extraer_destinatario("Transferencia a NEIDA GARCIA")
        assert result == "NEIDA GARCIA"


# ---------------------------------------------------------------------------
# Pattern 2 — "Transferencia a {nombre}"  (Bancolombia Bre-B)
# ---------------------------------------------------------------------------


class TestExtraccionTransferenciaNombre:
    def test_nombre_simple(self) -> None:
        assert extraer_destinatario("Transferencia a NEIDA GARCIA") == "NEIDA GARCIA"

    def test_nombre_compuesto(self) -> None:
        assert (
            extraer_destinatario("Transferencia a Leonardo Hoyos Serna")
            == "Leonardo Hoyos Serna"
        )

    def test_nombre_una_palabra(self) -> None:
        assert extraer_destinatario("Transferencia a Maria") == "Maria"

    def test_no_captura_cuenta(self) -> None:
        # Descriptions with "cuenta *" must NOT fall through to nombre pattern
        result = extraer_destinatario("Transferencia a cuenta *4321")
        assert result == "*4321"


# ---------------------------------------------------------------------------
# Pattern 3 — "Compra en {comercio}"  (Bancolombia debit-purchase)
# ---------------------------------------------------------------------------


class TestExtraccionCompra:
    def test_comercio_simple(self) -> None:
        assert extraer_destinatario("Compra en EXITO S.A.") == "EXITO S.A."

    def test_comercio_prod_sample(self) -> None:
        assert (
            extraer_destinatario("Compra en MOVISTAR PAGOSEPAYCO")
            == "MOVISTAR PAGOSEPAYCO"
        )

    def test_comercio_una_palabra(self) -> None:
        assert extraer_destinatario("Compra en Rappi") == "Rappi"


# ---------------------------------------------------------------------------
# Pattern 4 — "Envio a {nombre}"  (Nequi Bre-B)
# ---------------------------------------------------------------------------


class TestExtraccionEnvio:
    def test_nombre_simple(self) -> None:
        assert extraer_destinatario("Envio a Leonardo Hoyos Serna") == "Leonardo Hoyos Serna"

    def test_nombre_prod_sample(self) -> None:
        # Real prod sample per task doc
        assert extraer_destinatario("Envio a Leonardo Hoyos Serna") == "Leonardo Hoyos Serna"

    def test_nombre_utf8(self) -> None:
        # UTF-8 special characters must pass through without encoding loss
        assert extraer_destinatario("Envio a José María Ñoño") == "José María Ñoño"


# ---------------------------------------------------------------------------
# Pattern 5 — "Pago en {comercio}"  (Nequi commerce payment)
# ---------------------------------------------------------------------------


class TestExtraccionPagoEn:
    def test_comercio_simple(self) -> None:
        assert extraer_destinatario("Pago en Rappi") == "Rappi"

    def test_comercio_multipalabra(self) -> None:
        assert (
            extraer_destinatario("Pago en Kushki Colombia SA") == "Kushki Colombia SA"
        )


# ---------------------------------------------------------------------------
# Pattern 6 — "Pago PSE a {empresa}"
# ---------------------------------------------------------------------------


class TestExtraccionPagoPSE:
    def test_empresa_simple(self) -> None:
        assert (
            extraer_destinatario("Pago PSE a Empresas Publicas de Medellin")
            == "Empresas Publicas de Medellin"
        )

    def test_empresa_con_siglas(self) -> None:
        assert extraer_destinatario("Pago PSE a WOMPI S.A.S") == "WOMPI S.A.S"


# ---------------------------------------------------------------------------
# Skip-list — always None
# ---------------------------------------------------------------------------


class TestSkipList:
    def test_pago_factura_nequi_es_none(self) -> None:
        # "Pago factura Nequi" is a known skip — no recipient
        assert extraer_destinatario("Pago factura Nequi") is None

    def test_viaje_uber_es_none(self) -> None:
        assert extraer_destinatario("Viaje Uber") is None

    def test_viaje_didi_es_none(self) -> None:
        assert extraer_destinatario("Viaje DiDi") is None


# ---------------------------------------------------------------------------
# Non-match / free-form — must return None, never fabricate
# ---------------------------------------------------------------------------


class TestNoMatch:
    def test_descripcion_libre_es_none(self) -> None:
        assert extraer_destinatario("Gasto operacional sin patron") is None

    def test_cadena_vacia_es_none(self) -> None:
        assert extraer_destinatario("") is None

    def test_solo_espacios_es_none(self) -> None:
        assert extraer_destinatario("   ") is None

    def test_texto_parcialmente_similar_es_none(self) -> None:
        # Must not partially match if pattern doesn't anchor correctly
        assert extraer_destinatario("compra en minuscula") is None


# ---------------------------------------------------------------------------
# Empty-string guard — result MUST be str or None, never ""
# ---------------------------------------------------------------------------


class TestGuardaCadenaVacia:
    def test_resultado_nunca_es_cadena_vacia(self) -> None:
        """No pattern should ever produce an empty string result."""
        casos = [
            "Transferencia a cuenta *4321",
            "Transferencia a NEIDA GARCIA",
            "Compra en EXITO S.A.",
            "Envio a Leonardo Hoyos Serna",
            "Pago en Rappi",
            "Pago PSE a WOMPI S.A.S",
            "Pago factura Nequi",
            "free-form text",
            "",
        ]
        for desc in casos:
            result = extraer_destinatario(desc)
            assert result != "", (
                f"extraer_destinatario({desc!r}) must not return '' — got {result!r}"
            )


# ---------------------------------------------------------------------------
# Idempotency — backfill never overwrites a non-NULL destinatario
# (this is enforced by the WHERE clause, but we verify the extraction
# function itself doesn't alter already-filled rows — the runner skips them
# at the SQL level; here we verify the pure function produces the same
# value consistently, so a re-run would produce the same output)
# ---------------------------------------------------------------------------


class TestIdempotencia:
    def test_misma_descripcion_produce_mismo_resultado(self) -> None:
        desc = "Transferencia a cuenta *08600002475"
        first = extraer_destinatario(desc)
        second = extraer_destinatario(desc)
        assert first == second == "*08600002475"

    def test_non_match_siempre_none(self) -> None:
        desc = "Gasto sin patron reconocido"
        assert extraer_destinatario(desc) is None
        assert extraer_destinatario(desc) is None
