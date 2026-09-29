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

## Roles operativos y contables

Los tres actores siempre presentes en cualquier flujo contable y administrativo del bot:

| Rol | Nombre | Telegram ID | Cédula |
|-----|--------|-------------|--------|
| dev | Ryan | `5870211102` | — |
| admin | Sharimel | `8710698734` | — |
| propietario | Julio César Garay Manzur | `1379898979` | `1128049588` |

- Estos IDs son los únicos autorizados para operaciones financieras, liquidaciones y reportes contables.
- Los IDs viven en config/entorno, no hardcodeados. Esta tabla es referencia documental.

### Datos de contacto — Julio César Garay Manzur (propietario)

| Campo | Valor |
|-------|-------|
| Cédula | 1128049588 |
| Teléfono | 3223789349 |
| Correo | agenciagaraytour1@gmail.com |
| Dirección | Hotel Marie Real Centro |
| Cuenta Bancolombia | — (ver cuenta Sharimel) |

### Grupos de Telegram

| Grupo | Variable env | Chat ID actual | Tipo |
|-------|-------------|----------------|------|
| Admins (Ryan + Sharimel + Garay) | `GRUPO_ADMINS_ID` | `-5497775663` | Regular — si se convierte a supergrupo el ID cambia a `-1005497775663` |

- Si el bot recibe un update de un chat_id distinto al configurado para este grupo, loguear warning.

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

## UX de flujos con botones inline (OBLIGATORIO en todos los flujos)

- Todo flujo con pasos intermedios debe tener botón **« Atrás** que regrese al paso anterior.
- Todo flujo debe tener botón **✖ Cancelar** visible en cada paso, que aborte y limpie el estado.
- Al finalizar un flujo (éxito o cancelación), **eliminar o editar el mensaje con botones** para que no queden botones colgados sin función.
- Estas tres reglas aplican sin excepción a todos los handlers con `InlineKeyboardMarkup`.

## SDD (Spec-Driven Development)

- Modo de ejecucion predeterminado: **interactivo**.
- Artifact store predeterminado: **engram**.
