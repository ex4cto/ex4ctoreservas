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
