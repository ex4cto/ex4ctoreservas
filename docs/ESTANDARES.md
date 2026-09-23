# Estandares de codigo — Garay Tours

Estos estandares son obligatorios. Se definieron antes de escribir codigo, a proposito.

## Arquitectura

- **Hexagonal**. El dominio no conoce Telegram, FastAPI ni la base de datos.
- Capas: `dominio` (nucleo) -> `aplicacion` (casos de uso) -> `infraestructura` (adaptadores).
- Los puertos (interfaces) se definen en el dominio; la infraestructura los implementa.

## Naming

- `snake_case` en **espanol para el dominio** (lenguaje ubicuo del negocio): `vendedor`,
  `cerrador`, `tiquetera`, `conciliacion`, `cupo`, `comision`, `ganancia`.
- **Ingles para la plomeria tecnica** (adaptadores, settings, utilidades genericas).
- Sin spanglish dentro de una misma palabra.

## Dinero

- **Siempre `Decimal`, nunca `float`.** El value object `Dinero` rechaza `float` en construccion.
- Redondeo explicito (`ROUND_HALF_UP`, 2 decimales). Las comisiones deben cuadrar: la suma
  de las partes es igual al total.

## Formato de numeros financieros

**Display — una sola funcion, sin excepciones:**

```python
from garay.aplicacion.comun.formato import fmt_cop
fmt_cop(venta.valor_venta)   # → "$390.000"
fmt_cop(some_decimal)        # → "$390.000"
fmt_cop(None)                # → "—"
```

- Nunca `str(Dinero)` (produce `"390000.00 COP"`), nunca f-string directo sobre `Dinero`.
- Nunca definir un `_fmt_cop` local en ningun modulo.

**Input del usuario — un solo parser, sin excepciones:**

```python
from garay.aplicacion.comun.montos import parsear_monto
parsear_monto("390000")   # → Decimal("390000")
parsear_monto("390.000")  # → Decimal("390000")  # punto de miles colombiano
parsear_monto("390")      # → Decimal("390000")  # atajo: < 1000 → × 1000
parsear_monto("390k")     # → Decimal("390000")  # sufijo k/K
parsear_monto("abc")      # → None
```

- Nunca `Decimal(texto)` directo sobre input del usuario.
- Siempre validar que el resultado no sea `None` antes de construir `Dinero`.

## No hardcoding

- Principio general. Splits, porcentajes, horarios de cupos, montos, IDs de grupos, tokens y
  rutas viven en config/entorno/DB, nunca como valores magicos en el codigo.

## Tipos

- Type hints obligatorios. `mypy --strict` debe pasar.

## Mensajes

- Textos de usuario centralizados en `garay.mensajes`. Nada de strings sueltos en la logica.
- Estructura preparada para multi-idioma (i18n-ready).

## Tests

- TDD: test que falla primero, luego implementacion.
- La logica de dinero (comisiones, conciliacion) se prueba de forma exhaustiva.

## Commits

- Atomicos. Conventional commits.

## SDD (Spec-Driven Development)

- Modo de ejecucion predeterminado: **interactivo**.
- Artifact store predeterminado: **engram**.
