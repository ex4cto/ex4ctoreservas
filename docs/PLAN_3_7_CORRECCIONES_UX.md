# Plan Etapa 3.7 — Correcciones UX / Dominio Tiquetera

> Incorpora todos los hallazgos del Judgment Day (Judge A + Judge B).
> Orden de WUs respeta dependencias. Cada WU sigue ciclo estricto:
> **RED → GREEN → mypy strict → ruff → commit (conventional)**

---

## Cambios eliminados por JD

| Paso original | Decisión | Razón |
|---|---|---|
| Paso E — Audio (Whisper) | **ELIMINADO** | Ollama no tiene API de audio. `/api/generate` acepta imágenes (base64), no audio. Bloqueante técnico confirmado por ambos jueces. |

---

## Estándares obligatorios (toda modificación de archivo)

1. `from __future__ import annotations` en la primera línea de código de CADA archivo modificado o creado.
2. Ciclo TDD: escribir el test que falla → implementar mínimo para pasar → mypy strict limpio → ruff limpio.
3. Commits atómicos por WU en formato `feat(scope): ...` / `fix(scope): ...` / `refactor(scope): ...`.
4. Sin `# noqa`, sin `type: ignore` sin justificación documentada.
5. Docstrings de una línea máximo. Sin comentarios que expliquen el "qué" (los nombres lo hacen).

---

## WU-1 — Servicio: campos precio neto + ORM + Alembic migration

### Alcance
`src/garay/dominio/servicios/entidades.py`, `src/garay/infraestructura/persistencia/modelos.py`,
`src/garay/infraestructura/persistencia/repositorios/servicios.py`, nueva migración Alembic.

### Por qué
Judge B C-1: `Servicio` no tiene campos de precio. 3-layer change (dominio, ORM, repositorio) con migration.
Judge B C-8/A C-8: columnas NOT NULL sobre tabla con datos existentes fallan en Postgres —
agregar nullable, luego poblar con seed, luego decidir constraint.

### Tests (RED primero)
```
tests/dominio/servicios/test_entidades.py
  - test_servicio_con_precios: Servicio(..., precio_neto_adulto=Decimal("100"), precio_neto_nino=Decimal("50")) OK
  - test_servicio_sin_precio_nino: Servicio(..., precio_neto_adulto=Decimal("100"), precio_neto_nino=None) OK
  - test_servicio_sin_ningun_precio: ambos None — válido (servicio legacy sin datos de neto)

tests/infraestructura/persistencia/test_repositorios_servicios.py
  - test_listar_incluye_neto: guardar servicio con precios, listar, verificar campos presentes
  - test_listar_neto_null: guardar servicio sin precios, listar, verificar None
```

### Implementación
**`entidades.py`** — añadir al dataclass `Servicio`:
```python
precio_neto_adulto: Decimal | None = None
precio_neto_nino: Decimal | None = None
```

**`modelos.py`** — añadir a `ServicioModel`:
```python
precio_neto_adulto: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
precio_neto_nino: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
```

**`repositorios/servicios.py`** — mapear campos nuevos en `_to_domain()` y `_from_domain()`.

**Migration** — nueva revisión Alembic:
```sql
ALTER TABLE servicios ADD COLUMN precio_neto_adulto NUMERIC(14,2);
ALTER TABLE servicios ADD COLUMN precio_neto_nino NUMERIC(14,2);
```
Ambas nullable — sin NOT NULL, sin DEFAULT. Las filas existentes quedan NULL hasta que el seed
poblé los valores.

### Commit
`feat(dominio): add precio_neto_adulto/nino to Servicio + ORM + migration`

---

## WU-2 — Seed: parsing robusto de strings de neto

### Alcance
`scripts/seed.py`, `servicios_seed.json` (sin tocar el JSON — el parsing absorbe los strings sucios).

### Por qué
Judge B C-4: 15+ filas tienen `neto_nino` con strings no parseables como `"80.000 ( 2-3 años)"`,
`"NO INGRESAN NIÑOS"`, `"195 (3-8AÑOS )"`, `"50 MIL"`, `null`. `Decimal(str(...))` crashea.

### Tests (RED primero)
```
tests/scripts/test_seed_parsing.py
  - test_parse_neto_decimal_limpio: "100000" → Decimal("100000")
  - test_parse_neto_puntos_miles: "80.000" → Decimal("80000")
  - test_parse_neto_con_rango_edad: "80.000 ( 2-3 años)" → Decimal("80000")
  - test_parse_neto_sin_ninos: "NO INGRESAN NIÑOS" → None
  - test_parse_neto_con_letra_mil: "50 MIL" → Decimal("50000")
  - test_parse_neto_null: None → None
  - test_parse_neto_vacio: "" → None
  - test_parse_neto_dos_precios: "250 (4-8 años) 168 (5-10 AÑOS)" → Decimal("250") (primer número)
  - test_parse_neto_sin_numero: "4 años en adelante pagán" → None
  - test_parse_neto_no_pagan: "(0-12 AÑOS) No pagan" → Decimal("0")
```

### Implementación
```python
import re

_MIL_RE = re.compile(r'(\d[\d.,]*)\s*MIL', re.IGNORECASE)
_NUM_RE = re.compile(r'\d[\d.,]*')

def _parse_neto(texto: str | None) -> Decimal | None:
    if texto is None:
        return None
    texto = texto.strip()
    if not texto:
        return None
    # "NO INGRESAN NIÑOS" y similares — ningún dígito
    if not re.search(r'\d', texto):
        return None
    # "No pagan" con dígito de año — tratar como 0
    if re.search(r'no\s+pagan', texto, re.IGNORECASE):
        return Decimal("0")
    # "50 MIL" → "50000"
    mil_match = _MIL_RE.search(texto)
    if mil_match:
        base = mil_match.group(1).replace(".", "").replace(",", "")
        return Decimal(base) * 1000
    # Primer número que aparezca (ignora rangos de edad, paréntesis, etc.)
    num_match = _NUM_RE.search(texto)
    if num_match:
        limpio = num_match.group(0).replace(".", "").replace(",", "")
        try:
            return Decimal(limpio)
        except InvalidOperation:
            return None
    return None
```

Actualizar `seed_servicios()` para usar `_parse_neto`:
```python
ServicioModel(
    ...,
    precio_neto_adulto=_parse_neto(entry.get("neto_adulto")),
    precio_neto_nino=_parse_neto(entry.get("neto_nino")),
)
```

### Commit
`fix(seed): robust Decimal parsing for dirty neto strings in servicios_seed.json`

---

## WU-3 — FSM estados: remover NUMERO_TICKET + MONTO_NETO

### Alcance
`fsm.py`, `estados.py`, `bot.py`, `handlers.py`, `tests/aplicacion/tiquetera/test_fsm.py`

### Por qué
Judge A C-3/C-4, Judge B C-5: eliminar NUMERO_TICKET requiere 5 archivos (el plan original: 1 bullet).
MONTO_NETO se elimina como estado OBLIGATORIO (WU-5 lo hace condicional — solo aparece cuando
no se puede auto-calcular).

**Archivos y cambios específicos — 5 archivos, no 1:**

| Archivo | Cambio |
|---|---|
| `fsm.py` — `EstadoFSM` | Eliminar `NUMERO_TICKET`, `MONTO_NETO` |
| `fsm.py` — `_ESTADOS_FOTO_AVANZAR` | Eliminar ambos del frozenset |
| `fsm.py` — `_get_valor_prefilled` | Eliminar ramas de ambos estados |
| `fsm.py` — `procesar()` dispatch | Eliminar entradas del dict |
| `fsm.py` — handlers | Eliminar `_handle_numero_ticket`, `_handle_monto_neto` |
| `fsm.py` — `_handle_pax_ninos` | Transición → `MONTO_VALOR` (era `NUMERO_TICKET`) |
| `fsm.py` — `_handle_monto_abono` | Transición → placeholder que WU-5 reemplaza |
| `estados.py` | Eliminar `NUMERO_TICKET: 10`, `MONTO_NETO: 13` |
| `bot.py` | Eliminar entradas de state dict para ambos |
| `handlers.py` | Eliminar `handle_numero_ticket` + su import en bot.py |

### Tests (actualizar antes de tocar código)
```
ELIMINAR de test_fsm.py:
  - TestNumeroTicket (3 tests: test_numero_valido_avanza_a_monto_valor,
    test_cero_guarda_none, test_texto_invalido_devuelve_error)
  - TestMonto.test_monto_neto_supera_valor_devuelve_error

ACTUALIZAR:
  - TestFlujoCompleto.test_flujo_completo_feliz:
    Eliminar el paso "NUMERO_TICKET" → "MONTO_VALOR"
    La secuencia ahora es: PAX_NINOS → MONTO_VALOR → MONTO_ABONO → CONFIRMACION (WU-5 agrega la lógica)

  - TestMonto: conservar test_monto_abono_* (el estado MONTO_ABONO permanece)
```

### Commit
`refactor(fsm): remove NUMERO_TICKET and MONTO_NETO states — 5 files`

---

## WU-4 — FSMTiquetera constructor 4-tuple + todos los call sites

### Alcance
`fsm.py`, `main.py`, `tests/aplicacion/tiquetera/test_fsm.py`,
`tests/infraestructura/telegram/test_handlers.py`

### Por qué
Judge B C-2: el cambio de 2-tuple a 4-tuple rompe 6+ call sites que el plan original ignoraba.

### Command-Field Trace (obligatorio antes de implementar)
| Campo nuevo | Tipo | Fuente | Método repo |
|---|---|---|---|
| `neto_adulto` | `Decimal \| None` | `Servicio.precio_neto_adulto` | `SQLAServicioRepository.listar()` — verificado WU-1 |
| `neto_nino` | `Decimal \| None` | `Servicio.precio_neto_nino` | `SQLAServicioRepository.listar()` — verificado WU-1 |

### Tests (RED primero)
```
test_fsm.py:
  SERVICIOS_TEST debe cambiar a:
  SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None]] = [
      (1, "Tour Playa",    Decimal("100000"), Decimal("50000")),
      (2, "Tour Montaña",  Decimal("150000"), None),
      (3, "Tour Sin Neto", None,              None),
  ]

  Todos los FSMTiquetera(servicios=SERVICIOS_TEST, ...) se actualizan automáticamente.

test_handlers.py — cambiar TODAS las instancias (4 ubicaciones):
  FSMTiquetera(servicios=[(1, "Tour")], ...) → FSMTiquetera(servicios=[(1, "Tour", Decimal("100"), None)], ...)
  Líneas aproximadas: 96-98, 302-303, 320-322, 338-340 (verificar con grep antes de editar)
```

### Implementación
```python
class FSMTiquetera:
    def __init__(
        self,
        servicios: list[tuple[int, str, Decimal | None, Decimal | None]],
        puntos_venta: list[str],
    ) -> None:
        # dict para O(1) lookup: numero → (nombre, neto_adulto, neto_nino)
        self._servicios: dict[int, tuple[str, Decimal | None, Decimal | None]] = {
            n: (nombre, neto_a, neto_n) for n, nombre, neto_a, neto_n in servicios
        }
        self._puntos_venta = puntos_venta
```

**`main.py` línea 55** — actualizar listcomp:
```python
servicios = [
    (s.numero, s.nombre, s.precio_neto_adulto, s.precio_neto_nino)
    for s in servicio_repo.listar()
]
```

**`_destinos_mensaje`** — actualizar lookup:
```python
num_map = {n: info[0] for n, info in self._servicios.items()}
```

**`_handle_punto_de_venta`** — actualizar loop:
```python
for numero, (nombre, _, _) in self._servicios.items():
    if nombre.lower().strip() in nombres_norm and numero not in ctx.destinos_numeros:
        ctx.destinos_numeros.append(numero)
```

**`_handle_destino`** — actualizar set:
```python
numeros_validos = set(self._servicios.keys())
```

### Commit
`refactor(fsm): FSMTiquetera accepts 4-tuple servicios (nombre, neto_adulto, neto_nino)`

---

## WU-5 — FSM UX: hotel skip, fecha yy, destino deselección, neto auto-calc, resumen, editar

### Alcance
`fsm.py`, `src/garay/dominio/ventas/contexto.py`, `tests/aplicacion/tiquetera/test_fsm.py`

### Cambios en ContextoVenta
Agregar campo centinela para "sin hotel":
```python
sin_hotel: bool = False
```
Esto distingue "no preguntado" (None) de "respondido: sin hotel" (sin_hotel=True + hotel=None).

### Tests (RED primero — uno por subtema)

**Hotel skip:**
```
test_hotel_no_salta_habitacion: "no" → SalidaFSM.nuevo_estado == FECHA_SALIDA
test_hotel_variantes_sin_hotel: "No", "no hotel", "sin hotel", "no hay" → FECHA_SALIDA
test_hotel_con_nombre_avanza_a_habitacion: "Grand Hyatt" → CLIENTE_HABITACION
test_habitacion_entry_normal: estado CLIENTE_HABITACION, entrada normal → FECHA_SALIDA
```

**Fecha yy:**
```
test_fecha_dd_mm_yy_valida: "25/12/26" → datetime(2026, 12, 25)
test_fecha_dd_mm_yy_4_digitos_sigue_funcionando: "25/12/2026" → datetime(2026, 12, 25)
```

**Destino deselección:**
```
test_destino_deselecion_quita_numero: ctx con [15], entrada "-15" → destinos_numeros == []
test_destino_deselecion_numero_no_en_lista: ctx con [15], entrada "-99" → error + lista intacta
test_destino_deselecion_varios: "-15, -23" → elimina ambos
```

**Opciones destino contexto-dependientes:**
```
test_opciones_destino_sin_seleccion_no_tiene_confirmar: ctx sin destinos → opciones == []
test_opciones_destino_con_seleccion_tiene_confirmar: ctx con destinos → opciones == ["confirmar"]
```

**Neto auto-calculado:**
```
test_neto_auto_calcula_un_servicio: (1, "Tour", Decimal("100"), Decimal("50")) × 2 adultos 1 niño
  → ctx.neto == Decimal("250"), nuevo_estado == CONFIRMACION

test_neto_auto_calcula_multi_servicio: servicios 1+2 seleccionados, 2 adultos
  → neto = (100+150) * 2 = Decimal("500"), nuevo_estado == CONFIRMACION

test_neto_sin_precio_pide_manual: servicio con neto_adulto=None
  → nuevo_estado == MONTO_NETO (fallback manual)

test_neto_nino_none_usa_adulto_como_proxy: neto_nino=None, 1 niño
  → usa neto_adulto como proxy (documentar regla de negocio en comentario)

test_neto_abono_supera_calculado_error: abono > neto calculado → error (W-2 de JD)
  _handle_monto_abono valida abono <= valor antes de avanzar (ya existía)
  agregar validación en transición a CONFIRMACION: if abono > neto_calculado → volver a MONTO_ABONO con mensaje
```

**Resumen con nombres:**
```
test_resumen_muestra_nombre_tour_no_numero: destinos=[1], servicios={1: ("Tour Playa", ...)}
  → "Destinos: Tour Playa" (no "1")
test_resumen_sin_ticket_fisico: sin campo "Ticket N°" en el string
```

**Editar desde confirmación:**
```
test_confirmacion_editar_vuelve_a_tipo_reserva: entrada "✏️ Editar" → nuevo_estado == TIPO_RESERVA
test_confirmacion_confirmar_termina: entrada "✅ Confirmar" → listo=True
test_confirmacion_cancelar_cancela: entrada "❌ Cancelar" → CANCELADO
```

### Implementación

**`_handle_cliente_hotel` — hotel skip:**
```python
_SIN_HOTEL_TOKENS: frozenset[str] = frozenset({"no", "no hotel", "sin hotel", "no hay", "ninguno"})

def _handle_cliente_hotel(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
    ctx = _clonar(contexto)
    if entrada.strip().lower() in _SIN_HOTEL_TOKENS:
        ctx.sin_hotel = True
        ctx.cliente_hotel = None
        ctx.cliente_habitacion = None
        return SalidaFSM(
            nuevo_estado=EstadoFSM.FECHA_SALIDA,
            mensaje="¿Cuál es la fecha de salida? (formato: DD/MM, DD/MM/YY o DD/MM/YYYY)",
            contexto=ctx,
        )
    ctx.sin_hotel = False
    ctx.cliente_hotel = entrada.strip()
    return SalidaFSM(
        nuevo_estado=EstadoFSM.CLIENTE_HABITACION,
        mensaje="¿Cuál es el número de habitación?",
        contexto=ctx,
    )
```

**`_get_valor_prefilled` — branch de hotel:**
```python
if estado == EstadoFSM.CLIENTE_HOTEL:
    if ctx.sin_hotel:
        return "no"  # triggers auto-advance, _handle_cliente_hotel detects "no"
    return ctx.cliente_hotel
if estado == EstadoFSM.CLIENTE_HABITACION:
    return ctx.cliente_habitacion
```

**`_parsear_fecha` — agregar `%d/%m/%y`:**
```python
formatos_con_año = ["%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%m/%y"]
# %y: 00-68 → 20xx, 69-99 → 19xx (comportamiento C stdlib)
```

**`_handle_destino` — deselección:**
```python
# Detectar prefijo de deselección: "-15" o "- 15"
if texto.startswith("-"):
    partes_quitar = [p.strip().lstrip("-") for p in texto.replace(",", " ").split() if p.strip().lstrip("-")]
    for parte in partes_quitar:
        try:
            n = int(parte)
            if n in ctx.destinos_numeros:
                ctx.destinos_numeros.remove(n)
            else:
                # Devolver error pero no bloquear el estado
                ...
        except ValueError:
            ...
    return SalidaFSM(nuevo_estado=EstadoFSM.DESTINO, mensaje=self._destinos_mensaje(ctx),
                     opciones=self._opciones_destino(ctx), contexto=ctx)
```

**`_opciones_destino(ctx)` — context-aware:**
```python
def _opciones_destino(self, ctx: ContextoVenta) -> list[str]:
    return ["confirmar"] if ctx.destinos_numeros else []
```
Actualizar todos los call sites de `_opciones_destino()` → `_opciones_destino(ctx)`.

**`_calcular_neto` — método privado:**
```python
def _calcular_neto(self, ctx: ContextoVenta) -> Decimal | None:
    """Sum neto across all selected services. Returns None if any service lacks pricing."""
    if not ctx.destinos_numeros or ctx.adultos is None:
        return None
    total = Decimal("0")
    for numero in ctx.destinos_numeros:
        info = self._servicios.get(numero)
        if info is None:
            return None
        _, neto_adulto, neto_nino = info
        if neto_adulto is None:
            return None
        total += neto_adulto * ctx.adultos
        if ctx.ninos and ctx.ninos > 0:
            # Business rule: neto_nino=None → use neto_adulto as proxy price
            efectivo_nino = neto_nino if neto_nino is not None else neto_adulto
            total += efectivo_nino * ctx.ninos
    return total
```

**`_handle_monto_abono` — condicional:**
```python
def _handle_monto_abono(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
    ctx = _clonar(contexto)
    monto = _parsear_monto(entrada)
    if monto is None:
        return SalidaFSM(nuevo_estado=EstadoFSM.MONTO_ABONO,
                         mensaje="Monto inválido. Ingresá 0 si no hubo abono.", contexto=ctx)
    ctx.abono = monto
    neto = self._calcular_neto(ctx)
    if neto is not None:
        if ctx.abono > neto:
            return SalidaFSM(nuevo_estado=EstadoFSM.MONTO_ABONO,
                             mensaje=f"El abono ({monto}) no puede superar el neto calculado ({neto}).",
                             contexto=ctx)
        ctx.neto = neto
        return SalidaFSM(
            nuevo_estado=EstadoFSM.PARTICIPANTE_ROL,
            mensaje="¿Cuál fue tu rol en esta venta?",
            opciones=["Ambos", "Solo vendedor", "Solo cerrador"],
            contexto=ctx,
        )
    return SalidaFSM(
        nuevo_estado=EstadoFSM.MONTO_NETO,
        mensaje="¿Cuál es el monto neto? (no se encontró precio en el catálogo para algún tour seleccionado)",
        contexto=ctx,
    )
```
> Nota: MONTO_NETO **permanece** en el FSM como estado de fallback cuando no hay datos de neto en
> los servicios seleccionados. No se elimina — se vuelve condicional.

**`_construir_resumen` — de @staticmethod a método de instancia + nombres:**
```python
def _construir_resumen(self, ctx: ContextoVenta) -> str:
    if ctx.destinos_numeros:
        nombres = [self._servicios[n][0] for n in ctx.destinos_numeros if n in self._servicios]
        destinos_str = ", ".join(nombres) if nombres else ", ".join(str(n) for n in ctx.destinos_numeros)
    elif ctx.destinos_nombres:
        destinos_str = ", ".join(ctx.destinos_nombres) + " (pendiente confirmar)"
    else:
        destinos_str = "—"
    fecha_str = ctx.fecha_salida.strftime("%d/%m/%Y") if ctx.fecha_salida else "—"
    hotel_str = "Sin hotel" if ctx.sin_hotel else (ctx.cliente_hotel or "—")
    hab_str = "—" if ctx.sin_hotel else (ctx.cliente_habitacion or "—")
    return (
        "📋 *Resumen de la venta:*\n"
        f"Tipo: {ctx.tipo_cliente or '—'}\n"
        f"Punto de venta: {ctx.punto_de_venta_nombre or 'Sin punto'}\n"
        f"Destinos: {destinos_str}\n"
        f"Cliente: {ctx.cliente_nombre or '—'}\n"
        f"Teléfono: {ctx.cliente_telefono or '—'}\n"
        f"Hotel: {hotel_str}\n"
        f"Habitación: {hab_str}\n"
        f"Fecha salida: {fecha_str}\n"
        f"Adultos: {ctx.adultos or 0} | Niños: {ctx.ninos or 0}\n"
        f"Valor: {ctx.valor or '—'}\n"
        f"Abono: {ctx.abono or '—'}\n"
        f"Neto: {ctx.neto or '—'}\n"
        f"Vendedor: {ctx.vendedor_nombre or _tú_si(ctx.rol_registrante, 'ambos', 'vendedor')}\n"
        "Cerrador: "
        f"{ctx.cerrador_nombre or _tú_si(ctx.rol_registrante, 'ambos', 'cerrador')}\n\n"
        "¿Confirmamos?"
    )
```
> Eliminar `Ticket N°` del resumen (estado removido). Actualizar todos los call sites de
> `self._construir_resumen(ctx)` (ya tenían `self.` — solo remover `@staticmethod`).

**`_handle_confirmacion` — agregar "✏️ Editar":**
```python
def _handle_confirmacion(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
    ctx = _clonar(contexto)
    if entrada.strip() == "✅ Confirmar":
        return SalidaFSM(nuevo_estado=EstadoFSM.TERMINADO, mensaje="¡Venta registrada con éxito!",
                         listo=True, contexto=ctx)
    if entrada.strip() == "✏️ Editar":
        return SalidaFSM(
            nuevo_estado=EstadoFSM.TIPO_RESERVA,
            mensaje="¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO, DIGITAL",
            opciones=["INTERNO", "EXTERNO", "DIGITAL"],
            contexto=ctx,
        )
    return SalidaFSM(nuevo_estado=EstadoFSM.CANCELADO,
                     mensaje="Operación cancelada. Escribí /start para comenzar de nuevo.",
                     contexto=ctx)
```
> CRITICAL B-C7 fix: "✏️ Editar" retorna TIPO_RESERVA con opciones explícitas.
> El PTB handler para TIPO_RESERVA llama `fsm.procesar(TIPO_RESERVA, entrada, ctx)` — **no** `procesar_foto`.
> `procesar_foto` solo se llama desde `cmd_foto`. El loop infinito no existe en la ruta de edición.

Agregar "✏️ Editar" a opciones en estados que llegan a CONFIRMACION:
- `_handle_participante_rol` (rama "Ambos") → `opciones=["✅ Confirmar", "✏️ Editar", "❌ Cancelar"]`
- `_handle_participante_otro` → mismo set de opciones
- `iniciar()` no cambia (llega a CONFIRMACION eventualmente por el flujo)

### Commit
`feat(fsm): hotel skip, 2-digit date, destino deselection, auto-neto, editar from summary`

---

## WU-6 — METODO_INPUT: nuevo primer estado + bot wiring

### Alcance
`fsm.py`, `estados.py`, `bot.py`, `handlers.py`,
`tests/aplicacion/tiquetera/test_fsm.py`, `tests/infraestructura/telegram/test_handlers.py`

### Por qué
Judge B C-6: METODO_INPUT sin integer asignado → colisión de estados. Integer: **20** (siguiente libre
después de CANCELADO=19). Asignación hardcodeada aquí para evitar ambigüedad.
Judge A C-6: `cmd_foto` debe ser transición interna, no entry_point.
Judge B W-5: `iniciar()` hardcodeado a TIPO_RESERVA → debe retornar METODO_INPUT.
Judge B W-6: VOICE en entry_points contradice METODO_INPUT → no agregar.

### Tests (RED primero)
```
test_fsm.py:
  - test_iniciar_devuelve_estado_metodo_input (renombrar test existente)
  - test_metodo_input_manual_avanza_a_tipo_reserva: entrada "Manual" → TIPO_RESERVA
  - test_metodo_input_foto_avanza_a_tipo_reserva: entrada "Foto" → TIPO_RESERVA
    (misma transición — la diferencia es que el handler PTB usará cmd_foto internamente)
  - test_metodo_input_invalido_repite: entrada "Audio" → METODO_INPUT + mensaje error
  - test_metodo_input_muestra_mensaje_edicion_disponible: opciones incluyen ["Manual", "Foto"]
    y el mensaje menciona que se puede editar en el resumen

test_handlers.py:
  - test_cmd_start_retorna_metodo_input: PTB state == ESTADO_PTB[EstadoFSM.METODO_INPUT]
```

### Implementación

**`EstadoFSM`** — agregar:
```python
METODO_INPUT = "metodo_input"
```

**`ESTADO_PTB`** — agregar:
```python
EstadoFSM.METODO_INPUT: 20,
```

**`iniciar()`** — cambiar retorno:
```python
def iniciar(self) -> SalidaFSM:
    return SalidaFSM(
        nuevo_estado=EstadoFSM.METODO_INPUT,
        mensaje=(
            "¿Cómo querés registrar la venta?\n\n"
            "_Podés modificar cualquier dato en el resumen antes de confirmar._"
        ),
        opciones=["Manual", "Foto"],
        contexto=ContextoVenta(),
    )
```

**`_handle_metodo_input`** — nuevo handler:
```python
def _handle_metodo_input(self, entrada: str, contexto: ContextoVenta) -> SalidaFSM:
    ctx = _clonar(contexto)
    opcion = entrada.strip()
    if opcion in ("Manual", "Foto"):
        return SalidaFSM(
            nuevo_estado=EstadoFSM.TIPO_RESERVA,
            mensaje="¿Qué tipo de reserva es?\nOpciones: INTERNO, EXTERNO, DIGITAL",
            opciones=["INTERNO", "EXTERNO", "DIGITAL"],
            contexto=ctx,
        )
    return SalidaFSM(
        nuevo_estado=EstadoFSM.METODO_INPUT,
        mensaje="Opción inválida. Elegí Manual o Foto.",
        opciones=["Manual", "Foto"],
        contexto=ctx,
    )
```
Agregar al dict de `procesar()`:
```python
EstadoFSM.METODO_INPUT: self._handle_metodo_input,
```

**`bot.py`** — wiring PTB:
- Agregar `estados[EstadoFSM.METODO_INPUT]` con `handle_metodo_input`
- Mover `cmd_foto` de `entry_points` a handler interno de METODO_INPUT:
  - Cuando el usuario clickea "Foto" en METODO_INPUT → PTB recibe callback "Foto" → `handle_metodo_input` retorna TIPO_RESERVA
  - El handler foto (`cmd_foto`) se registra en el estado TIPO_RESERVA como `MessageHandler(filters.PHOTO, cmd_foto)`
  - `cmd_foto` llama `fsm.procesar_foto(EstadoFSM.TIPO_RESERVA, ..., ctx)` para auto-avanzar con los datos extraídos
- Sin `MessageHandler(filters.VOICE, ...)` en entry_points ni en ningún estado (Paso E eliminado)

**`handlers.py`** — agregar:
```python
handle_metodo_input = _make_handler(EstadoFSM.METODO_INPUT)
```

### Commit
`feat(telegram): add METODO_INPUT as first FSM state, internalize cmd_foto`

---

## WU-7 — Notificación grupo: formato ítem por ítem + sin UUID

### Alcance
`src/garay/aplicacion/tiquetera/servicio.py` (verificar líneas 101-109 para UUID)

### Por qué
Judge A W-5: el UUID se genera en `servicio.py`, no en `notificador.py`.
`NotificadorGrupoTelegram` solo envía el string. El formato lo construye `RegistrarVentaService`.

### Tests (RED primero)
```
tests/aplicacion/tiquetera/test_servicio.py:
  - test_mensaje_notificacion_sin_uuid: el mensaje enviado al notificador no contiene un UUID
  - test_mensaje_notificacion_formato_item_por_item: mensaje contiene líneas separadas
    por campo ("Tipo:", "Tours:", "Cliente:", "Valor:", "Neto:", "Comisiones:")
    (verificar qué campos son relevantes para el grupo leyendo el mensaje actual antes de implementar)
```

### Implementación
1. Leer `servicio.py` para ver el mensaje actual en el notificador (líneas ~95-115)
2. Remover UUID del mensaje
3. Reformatear a item-por-item con los campos que le interesan al grupo

### Commit
`fix(servicio): remove UUID from group notification, format message item-by-item`

---

## Checklist de validación final

Antes de mergear a `main`:

- [ ] `pytest` — todos los tests pasan (objetivo: 290+ tests)
- [ ] `mypy --strict src/` — 0 errores
- [ ] `ruff check src/ tests/` — 0 warnings
- [ ] `from __future__ import annotations` en TODOS los archivos modificados
- [ ] `alembic upgrade head` corre limpio en DB local
- [ ] `python scripts/seed.py` corre sin crash (datos sucios parseados correctamente)
- [ ] Bot arranca: `python -m garay.infraestructura.telegram.main` sin errores
- [ ] Prueba manual mínima:
  - [ ] `/start` → muestra METODO_INPUT con botones Manual/Foto
  - [ ] Flujo manual completo: cliente sin hotel → salta habitación
  - [ ] Fecha en formato `dd/mm/yy` aceptada
  - [ ] Destino: agregar número, quitar con `-N`, confirmar
  - [ ] Neto auto-calculado → llega a CONFIRMACIÓN sin preguntar neto
  - [ ] Editar desde confirmación → vuelve a inicio, NO loop infinito
  - [ ] Foto: flujo IA auto-avanza correctamente

---

## Resumen de decisiones de dominio tomadas

| Decisión | Detalle |
|---|---|
| `neto_nino=None` + niños > 0 | Usar `neto_adulto` como precio proxy. Documentado en `_calcular_neto`. |
| `neto_adulto=None` (ej: COCOTERA CLASSIC) | `_calcular_neto` retorna None → fallback a MONTO_NETO manual. |
| MONTO_NETO | No eliminado. Se vuelve condicional: aparece solo cuando falla el auto-cálculo. |
| "sin hotel" sentinel | `ctx.sin_hotel: bool = False` en ContextoVenta. Distingue "no respondido" de "respondido: sin hotel". |
| Integer METODO_INPUT | `20` — siguiente libre después de CANCELADO=19. |
| VOICE (audio) | No implementado en esta etapa. Bloqueante técnico (Ollama sin API audio). |
| Editar desde resumen | Retorna a TIPO_RESERVA via `procesar`, NO via `procesar_foto`. Sin loop. |
| Neto multi-servicio | SUM de los netos de todos los servicios seleccionados. |
