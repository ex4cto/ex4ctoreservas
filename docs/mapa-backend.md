# Mapa de backend — Garay Tours

Índice de capas, flujos principales y métodos clave. Actualizar al agregar o modificar flujos.

---

## Arquitectura

```
dominio/ (núcleo puro)
  ├── comisiones/     — ReglasComision, MotorComisiones, DesgloseComision, SnapshotReglas
  ├── ventas/         — Venta (agregado), Participantes, DigitalConPuntoDeVenta (invariante)
  ├── puntos_venta/   — PuntoDeVenta (porcentaje_capa)
  └── puertos/        — interfaces abstractas (repositorios, servicios externos)

aplicacion/
  └── tiquetera/      — RegistrarVentaService, _derivar_numero_personas, FSM Telegram

infraestructura/
  ├── persistencia/   — SQLAlchemy models, repositorios SQLA
  └── telegram/       — handlers, adaptadores
```

---

## Flujo principal — RegistrarVentaService.ejecutar

```
1. Crear Venta aggregate
   └─ Venta.__post_init__ dispara invariante DigitalConPuntoDeVenta si aplica

2. Resolver punto de venta (PRIMERO — necesario para selección de regla)
   └─ PuntoDeVentaRepository.buscar_por_id(participantes.punto_de_venta_id)

3. Derivar numero_personas
   └─ _derivar_numero_personas(participantes) → 1 | 2 | None
      • 1  : vendedor_id == cerrador_id (ambos non-None, misma persona)
      • 2  : vendedor_id != cerrador_id (ambos non-None, distintas personas)
      • None: cualquiera de los dos ids es None

4. Seleccionar regla de comisión
   └─ ReglasComisionRepository.buscar_regla(tipo, punto_nombre, numero_personas)
      • Si retorna None → raise ReglasComisionNoEncontradas (fail-fast, design S3)

5. Calcular desglose
   └─ MotorComisiones.calcular(venta, reglas, punto, porcentaje_referido)
      • Motor PURO: sin rama Crespo — la selección upstream entrega los %v/%c correctos
      • Invariante sagrado: capa + vendedor + cerrador + agencia == ganancia

6. Persistir Venta
7. Persistir ComisionRegistrada
8. Crear Tiquetera si hay foto_referencia
9. Notificar grupo Telegram
```

---

## ReglasComisionRepository — métodos

### `buscar_regla(tipo, punto_nombre, numero_personas) → ReglasComision | None`

Selector de dos pasos para la regla de comisión. Añadido en change `comision-crespo` (Slice 1b).

**C3 precondition**: `punto_nombre` y `numero_personas` deben ser ambos `None` o ambos
`non-None`; una combinación mixta levanta `ValueError`.

**Paso 1 — point-specific** (si ambos non-None):
```sql
WHERE punto_de_venta_nombre = :punto AND numero_personas = :n
```
Si encuentra fila → retorna. Si no → retorna `None` (NO cae a global; la capa de
aplicación falla ruidosamente con `ReglasComisionNoEncontradas` — design S3).

**Paso 2 — global fallback** (si ambos `None`):
```sql
WHERE tipo_cliente = :tipo
  AND punto_de_venta_nombre IS NULL   -- .is_(None) en ORM
  AND numero_personas IS NULL
```

**Por qué `IS NULL` y no `= NULL`**: en SQL, `= NULL` siempre es `FALSE`; se requiere
`IS NULL` para filtrar filas globales correctamente (design B3).

---

### `buscar_por_tipo_cliente(tipo) → ReglasComision | None`

Método legado mantenido. Endurecido en Slice 1a (change `comision-crespo`) para consultar
EXCLUSIVAMENTE filas globales:
```sql
WHERE tipo_cliente = :tipo
  AND punto_de_venta_nombre IS NULL
  AND numero_personas IS NULL
```
Sin los filtros `IS NULL`, `scalar_one_or_none()` levantaría `MultipleResultsFound` cuando
coexisten filas punto-específicas (Crespo) con el mismo `tipo_cliente` (design B1).

**Usar `buscar_regla` en todo código nuevo.** `buscar_por_tipo_cliente` se mantiene
para compatibilidad pero no se llama desde `RegistrarVentaService`.

---

## Reglas de comisión — esquema de datos

| Fila | tipo_cliente | punto_de_venta_nombre | numero_personas | Uso |
|------|--------------|-----------------------|-----------------|-----|
| Global INTERNO | INTERNO | NULL | NULL | ventas presenciales INTERNO no-Crespo |
| Global EXTERNO | EXTERNO | NULL | NULL | ventas presenciales EXTERNO no-Crespo |
| Global DIGITAL | DIGITAL | NULL | NULL | todas las ventas digitales |
| Crespo 1p | EXTERNO (centinela) | "Crespo" | 1 | Crespo: vendedor == cerrador |
| Crespo 2p | EXTERNO (centinela) | "Crespo" | 2 | Crespo: vendedor != cerrador |

**Centinela EXTERNO en filas Crespo**: el valor de `tipo_cliente` es irrelevante para la
selección punto-específica (Paso 1 no filtra por tipo). Se usa `EXTERNO` por convención.
La unicidad compuesta `(tipo_cliente, punto_de_venta_nombre, numero_personas)` garantiza que
no hay ambigüedad entre filas globales y Crespo.

---

## Invariante DigitalConPuntoDeVenta

`Venta.__post_init__` levanta `DigitalConPuntoDeVenta` si:
```python
tipo_cliente == TipoCliente.DIGITAL and participantes.punto_de_venta_id is not None
```
Añadido en change `comision-crespo` Slice 1a. La migración 0008 incluye un pre-check
que valida que no existen filas legacy violando este invariante antes de activarlo.

---

## Snapshot de comisiones

`SnapshotReglas` captura los porcentajes en el momento de la venta (inmutable).
Gana `numero_personas` y `punto_de_venta_nombre` desde Slice 1a.
Deserialización backward-compatible: usa `.get()` con default `None` para no romper
snapshots históricos que no tienen esas claves.
