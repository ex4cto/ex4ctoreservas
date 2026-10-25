"""Unit tests for calcular_diff — RED phase (TDD).

Tests for: garay.aplicacion._util.diff_campos.calcular_diff
"""

from __future__ import annotations

import json
from decimal import Decimal

from garay.aplicacion._util.diff_campos import calcular_diff


class TestCampoUnico:
    def test_un_campo_cambiado_devuelve_una_tupla(self) -> None:
        viejo = {"precio": "50000", "activo": "True"}
        nuevo = {"precio": "60000", "activo": "True"}
        resultado = calcular_diff(viejo, nuevo)
        assert len(resultado) == 1
        campo, anterior, siguiente = resultado[0]
        assert campo == "precio"
        assert anterior == "50000"
        assert siguiente == "60000"

    def test_sin_cambios_devuelve_lista_vacia(self) -> None:
        datos = {"nombre": "PLAYA BLANCA", "activo": "True"}
        assert calcular_diff(datos, datos.copy()) == []

    def test_multiples_campos_cambiados(self) -> None:
        viejo = {"precio": "50000", "activo": "True", "nombre": "TOUR A"}
        nuevo = {"precio": "60000", "activo": "False", "nombre": "TOUR A"}
        resultado = calcular_diff(viejo, nuevo)
        assert len(resultado) == 2
        campos = {t[0] for t in resultado}
        assert campos == {"precio", "activo"}

class TestSerializacionDecimal:
    def test_decimal_serializado_via_str(self) -> None:
        viejo = {"monto": Decimal("50000")}
        nuevo = {"monto": Decimal("60000")}
        resultado = calcular_diff(viejo, nuevo)
        assert len(resultado) == 1
        _, anterior, siguiente = resultado[0]
        assert anterior == "50000"
        assert siguiente == "60000"

    def test_decimal_igual_no_produce_diff(self) -> None:
        viejo = {"monto": Decimal("50000")}
        nuevo = {"monto": Decimal("50000")}
        assert calcular_diff(viejo, nuevo) == []

class TestCampoJson:
    def test_netos_por_horario_diff_como_json_canonico(self) -> None:
        viejo = {"netos_por_horario": {"08:00": Decimal("40000")}}
        nuevo = {
            "netos_por_horario": {
                "08:00": Decimal("40000"),
                "10:00": Decimal("45000"),
            }
        }
        resultado = calcular_diff(viejo, nuevo)
        assert len(resultado) == 1
        campo, anterior, siguiente = resultado[0]
        assert campo == "netos_por_horario"
        # canonical JSON: sort_keys=True, ensure_ascii=False
        assert anterior == json.dumps(
            {"08:00": "40000"}, sort_keys=True, ensure_ascii=False
        )
        assert siguiente == json.dumps(
            {"08:00": "40000", "10:00": "45000"}, sort_keys=True, ensure_ascii=False
        )

    def test_json_igual_no_produce_diff(self) -> None:
        viejo = {"netos_por_horario": {"08:00": Decimal("40000")}}
        nuevo = {"netos_por_horario": {"08:00": Decimal("40000")}}
        assert calcular_diff(viejo, nuevo) == []

    def test_none_serializado_como_cadena_none(self) -> None:
        viejo = {"precio": None}
        nuevo = {"precio": Decimal("30000")}
        resultado = calcular_diff(viejo, nuevo)
        assert len(resultado) == 1
        _, anterior, siguiente = resultado[0]
        assert anterior == "None"
        assert siguiente == "30000"
