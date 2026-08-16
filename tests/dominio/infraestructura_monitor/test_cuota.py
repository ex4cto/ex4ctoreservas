"""Tests for pure Resend quota domain functions in garay.dominio.infraestructura_monitor.cuota.

Covers:
- bandas_absolutas: fraction-to-absolute conversion, dedup, sort
- banda_mensual_cruzada: crossing detection (exact-cross, no-cross, already-above)
- supera_umbral_diario: simple threshold check
"""

from __future__ import annotations

from garay.dominio.infraestructura_monitor.cuota import (
    banda_mensual_cruzada,
    bandas_absolutas,
    supera_umbral_diario,
)


class TestBandasAbsolutas:
    def test_convierte_fracciones_estandar(self) -> None:
        """(0.80, 0.95, 1.0) x 3000 -> (2400, 2850, 3000)."""
        result = bandas_absolutas(3000, (0.80, 0.95, 1.0))
        assert result == (2400, 2850, 3000)

    def test_redondea_hacia_abajo_en_enteros(self) -> None:
        """cap=100, fraction=0.33 -> floor(33.0)=33."""
        result = bandas_absolutas(100, (0.33,))
        assert result == (33,)

    def test_ordena_ascendente(self) -> None:
        """Fractions given out of order should yield sorted output."""
        result = bandas_absolutas(1000, (1.0, 0.5, 0.8))
        assert result == (500, 800, 1000)

    def test_deduplica_umbrales_identicos(self) -> None:
        """Two fractions mapping to the same int are deduplicated."""
        # cap=10: 0.80->8, 0.81->8 (floor), 1.0->10
        result = bandas_absolutas(10, (0.80, 0.81, 1.0))
        assert result == (8, 10)

    def test_bandas_vacias_retorna_tuple_vacia(self) -> None:
        result = bandas_absolutas(3000, ())
        assert result == ()

    def test_cap_cero_retorna_ceros_deduplicados(self) -> None:
        """With cap 0 all fractions yield 0; deduplicated to single element."""
        result = bandas_absolutas(0, (0.8, 0.95, 1.0))
        assert result == (0,)

    def test_fraccion_unitaria(self) -> None:
        """Single fraction at 1.0 yields the cap itself."""
        result = bandas_absolutas(3000, (1.0,))
        assert result == (3000,)


class TestBandaMensualCruzada:
    # --- Exact crossing: previo < T <= actual ---

    def test_cruza_primera_banda(self) -> None:
        """Crossing from 2399 to 2400 hits the 2400 band."""
        result = banda_mensual_cruzada(2400, 2399, (2400, 2850, 3000))
        assert result == 2400

    def test_cruza_segunda_banda_directamente(self) -> None:
        """Jump from 2400 to 2850 hits 2850 (highest band crossed)."""
        result = banda_mensual_cruzada(2850, 2400, (2400, 2850, 3000))
        assert result == 2850

    def test_cruza_multiples_bandas_devuelve_la_mas_alta(self) -> None:
        """Jump from 0 to 3000 crosses all three; returns 3000."""
        result = banda_mensual_cruzada(3000, 0, (2400, 2850, 3000))
        assert result == 3000

    def test_cruza_exactamente_en_limite_superior(self) -> None:
        """actual == T and previo < T is a valid crossing."""
        result = banda_mensual_cruzada(2850, 2849, (2400, 2850, 3000))
        assert result == 2850

    # --- No crossing below threshold ---

    def test_no_cruza_por_debajo_de_primera_banda(self) -> None:
        """Both actual and previo below all thresholds: no crossing."""
        result = banda_mensual_cruzada(2300, 2200, (2400, 2850, 3000))
        assert result is None

    def test_no_cruza_cuando_actual_igual_previo(self) -> None:
        """No movement: no crossing."""
        result = banda_mensual_cruzada(2400, 2400, (2400, 2850, 3000))
        assert result is None

    # --- Already above: previo >= T → no new crossing ---

    def test_ya_estaba_por_encima_no_dispara(self) -> None:
        """previo already at 2400: next check at 2410 should not re-fire 2400."""
        result = banda_mensual_cruzada(2410, 2400, (2400, 2850, 3000))
        assert result is None

    def test_previo_mayor_al_umbral_no_dispara(self) -> None:
        """previo already above 2850 (2900): moving to 2950 should not re-fire 2850."""
        result = banda_mensual_cruzada(2950, 2900, (2400, 2850, 3000))
        assert result is None

    # --- Off-by-one: actual just below threshold ---

    def test_actual_justo_debajo_no_cruza(self) -> None:
        """actual == T - 1 with previo below: no crossing."""
        result = banda_mensual_cruzada(2399, 2300, (2400, 2850, 3000))
        assert result is None

    # --- Empty thresholds ---

    def test_umbrales_vacios_retorna_none(self) -> None:
        result = banda_mensual_cruzada(3000, 0, ())
        assert result is None

    # --- Month reset: previo = 0 (fresh month) ---

    def test_primer_dia_del_mes_cruzando_banda(self) -> None:
        """If previo=0 (month boundary reset) and actual crosses 2400, fires."""
        result = banda_mensual_cruzada(2450, 0, (2400, 2850, 3000))
        assert result == 2400

    def test_primer_dia_del_mes_sin_cruzar(self) -> None:
        """If previo=0 and actual < 2400, no crossing."""
        result = banda_mensual_cruzada(100, 0, (2400, 2850, 3000))
        assert result is None


class TestSuperaUmbralDiario:
    def test_igual_al_umbral_dispara(self) -> None:
        assert supera_umbral_diario(80, 80) is True

    def test_mayor_al_umbral_dispara(self) -> None:
        assert supera_umbral_diario(100, 80) is True

    def test_menor_al_umbral_no_dispara(self) -> None:
        assert supera_umbral_diario(79, 80) is False

    def test_cero_no_dispara(self) -> None:
        assert supera_umbral_diario(0, 80) is False

    def test_umbral_cero_siempre_dispara(self) -> None:
        """Threshold of 0: any count >= 0 fires."""
        assert supera_umbral_diario(0, 0) is True
