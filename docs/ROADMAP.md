# Garay Tours — Roadmap de desarrollo

> Leyenda: ✅ completo · 🔄 en curso · ⬜ pendiente
> Actualizar manualmente al cerrar cada fase.

---

## Etapa 0 — Fundaciones ✅
*Commits: `215acfd` (UW1) · `6d9b3d3` (UW2)*

| # | Fase | Estado |
|---|------|--------|
| 0.1 | Layout hexagonal: 3 capas, src-layout, py.typed, naming español/inglés | ✅ |
| 0.2 | Tooling: uv · mypy strict · ruff · pytest · ESTANDARES.md | ✅ |
| 0.3 | Config sin hardcoding: pydantic-settings, prefijo `GARAY_`, env.example | ✅ |
| 0.4 | Persistencia base: SQLAlchemy 2.0 · Alembic · TipoDinero (NUMERIC↔Dinero) | ✅ |
| 0.5 | Mensajería centralizada: catálogo key-based, i18n-ready | ✅ |
| 0.6 | Observabilidad: FormateadorJson, jerarquía de errores tipada | ✅ |

---

## Etapa 1 — Modelo de Dominio Central ✅
*Commits: `9c3a31d` (UW1) · `f5f99d3` (UW2)*

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 1.1 | Lenguaje ubicuo + glosario | ✅ | Formalizado en ESTANDARES.md y entidades |
| 1.2 | Value Objects: Dinero, Participantes, DatosExtraidos, DesgloseComision | ✅ | |
| 1.3 | Entidades core: Freelancer · PuntoDeVenta · Servicio · Cliente + TipoCliente | ✅ | |
| 1.4 | Agregados transaccionales: Venta · Tiquetera · Ingreso · Egreso · Conciliacion | ✅ | |
| 1.5 | Puertos del dominio: 9 repositorios + ExtractorIA + NotificadorGrupo | ✅ | |
| 1.6 | Servicios de dominio (esqueleto): MotorComisionesBase · MotorConciliacionBase | ✅ | Stubs — lógica en Etapas 2 y 6 |

---

## Etapa 2 — Motor de Comisiones ✅
*Commit: `8c723e2`*

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 2.1 | Reglas como datos: `ReglasComision` en DB · `SnapshotReglas` por venta | ✅ | Históricos inmutables |
| 2.2 | Pipeline: capa punto → splits vendedor/cerrador → agencia residual → referido (bruto) | ✅ | |
| 2.3 | Comisión por participación: rol vacío → 0, agencia absorbe el residuo | ✅ | |
| 2.4 | Redondeo: agencia = ganancia − resto (invariante exacto, sin pérdida de centavos) | ✅ | |
| 2.5 | Tests TDD: caso Garay real (1M/900k) · digital · participación parcial · referido · invariante | ✅ | 23 tests |

---

## Etapa 3 — Tiquetera / Registro de ventas (Telegram) ✅
*Hito 2 de pago (30%). Mata el Excel de Sharimel.*
*Commits: `fdf42aa` (UW0.5) · `6ccd8cc` (UW1) · `9b9da7a` (UW2) · `137269d` (UW3) · `6054569` (UW4) · `76dc0d0` `ff19627` `37df9ec` `cbedaf2` `19103ba` `fe31784` (UW post-testing)*

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 3.0 | Extensión dominio con campos reales (cantidad, abono, numero_ticket, telefono, hotel, habitacion) | ✅ | Extraído del Excel + fotos tiqueteras |
| 3.1 | Flujo determinista con botones: 18 estados, FSMTiquetera pura + adaptador PTB | ✅ | 15 tests, python-telegram-bot v21 |
| 3.2 | Extracción IA (foto→campos): ExtractorOllama (llava), parser robusto, confirmación humana | ✅ | 6 tests, urllib puro, fallback confianza=0 |
| 3.3 | Registro venta + MotorComisiones + snapshot de regla aplicada | ✅ | RegistrarVentaService, 5 tests |
| 3.4 | Notificación grupo Telegram: NotificadorGrupoTelegram (Telegram por ahora, WhatsApp en Etapa 8) | ✅ | 5 tests, urllib puro |
| 3.5 | Wiring real (repos SQLAlchemy + inyección deps en main.py + handler foto AI) | ✅ | Commit `9169722` — 9 pasos, 257 tests |
| 3.6 | Comandos Telegram `/mis_ventas` + `/resumen_empresa`, es_admin, repos periodo | ✅ | 272 tests |
| 3.7 | Correcciones UX/dominio: METODO_INPUT, hotel skip, neto auto-calc, editar desde resumen, seed parsing, notificación format | ✅ | 316 tests |
| 3.8 | Correcciones post-testing manual: freeze FSM (abono loop), typo hotel fuzzy (rapidfuzz), formato fechas unificado, validación neto≤valor, seed neto×1000 | ✅ | 354 tests |
| 3.9 | Fix input montos: "500" → $500.000 (miles-de-pesos en valor/abono/neto), fix import ContextoVenta | ✅ | 362 tests |
| 3.10 | Estado ESPERANDO_FOTO, fix foto button, fix abono display, format date unificado | ✅ | 372 tests |
| 3.11 | Migración catálogo completa: ~40 strings eliminados de fsm.py, 25 claves nuevas/actualizadas, `_construir_resumen` wired, Judgment Day pre-ejecución | ✅ | 400 tests |
| 3.12 | Extracción foto mejorada: prompt con layout físico del tiquete, `numero_ticket` str (alphanumérico), `vendedor_nombre` mapeado desde `servicio_nombre`, `foto_modo` flag (salta wizard), Alembic migration `numero_fisico` BigInteger→String | ✅ | 405 tests · commits `494b540` `e3ce4d3` |
| 3.13 | Validación confirmación + catálogo `cmd_foto`: bloquea "✅ Confirmar" si faltan campos obligatorios (hotel/hab solo para INTERNO), `foto_modo`→`PARTICIPANTE_ROL`, 18 claves catálogo nuevas, formato `$260.000` en resumen inicial | ✅ | 427 tests · commit `443ff10` |
| 3.14 | Fix edit flow foto: `procesar_foto` respeta `modo_edicion`, "Adultos/Niños" edita ambos campos, "Habitación" en selector, nuevos estados EDITAR_VENDEDOR/CERRADOR reemplazan PARTICIPANTE_ROL en edición | ✅ | 440 tests · commit `3712bc0` |
| 3.15 | Edit prompts muestran valor actual: 8 claves de catálogo con `{actual}`, `_mensaje_para_estado` ctx-aware (nombre, teléfono, hotel, habitación, fecha, adultos/niños, valor, abono) | ✅ | 449 tests · commit `c2f00fd` |
| 3.16 | Fix neto recálculo en edición: `_parse_neto` reconoce "NO INGRESAN NIÑOS"/"NO SE ACEPTAN" → 0; `_calcular_neto` siempre recalcula al editar destino, pax o foto mode (elimina condición `ctx.neto is None`) | ✅ | 455 tests |
| 3.17 | Sync catálogo precios desde Google Sheet: `precio_sugerido` (97 servicios) y `neto_adulto` (4 correcciones por match 100%); fix `_parse_neto` para aceptar `int`/`float` además de `str` | ✅ | 455 tests |

---

## Etapa 4 — Ingresos bancarios (FastAPI / webhook) ✅

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 4.1 | Webhook Forward Email: POST /webhook/email + HMAC secret | ✅ | FastAPI single-tenant, `GARAY_FORWARD_EMAIL_SECRET` |
| 4.2 | Parsers Bancolombia / Nequi → `PagoExtraido` normalizado | ✅ | Regex probados con correos reales, edge cases 12am/12pm |
| 4.3 | Persistencia + idempotencia: deduplicación por `messageId` | ✅ | `SQLAIngresoRepository`, `existe_referencia()` |
| 4.4 | Clasificación inicial: todo ingreso nace "sin clasificar" | ✅ | Listo para Etapa 6 — conciliación |
| 4.5 | `/verificar_pago`: pagos recibidos en últimos 5 min | ✅ | Disponible para todos los freelancers |
| 4.6 | `/start` muestra menú de comandos, `set_my_commands()` al arrancar | ✅ | `/nueva_venta` como entry point del flujo de tiquetera |

---

## Etapa 5 — Egresos / Salidas ✅

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 5.1 | Egresos automáticos: correos salientes Bancolombia/Nequi | ✅ | 5 patrones (3 BC + 2 Nequi + Kushki); `_parsear_monto_bilingue`; `SQLAEgresoRepository` |
| 5.2 | Egresos manuales: categorías en DB, `/nuevo_egreso` Telegram | ✅ | `CategoriaEgreso` dataclass + repo; `RegistrarEgresoManualService`; seed 7 categorías |
| 5.3 | Recurrencia: gastos fijos como catálogo, `/gastos_fijos`, `/generar_mes` | ✅ | `GastoRecurrente` entity; `GenerarGastosRecurrentesService` idempotente |
| 5.4 | Persistencia adicional: listar egresos por período | ⬜ | Diferido a Etapa 6 — el motor de conciliación lo necesitará |

---

## Etapa 6 — Motor de Conciliación ✅

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 6.1 | Estrategia de match: venta↔ingreso por monto + ventana fecha con tolerancia | ✅ | `MotorConciliacion`, scoring 100% Decimal, pesos en Settings |
| 6.2 | Estados: matcheado · sin match · personal/sin clasificar · pendiente | ✅ | `EstadoConciliacion` completo, callbacks inline por estado |
| 6.3 | Resolución manual asistida: sugerencias rankeadas, humano confirma | ✅ | `/pendientes` con botones Match/Personal/Sin match |
| 6.4 | Permisos propietario: `/conciliar` y `/pendientes` solo Garay + dev | ✅ | `requiere_propietario`, `GARAY_PROPIETARIO_TELEGRAM_IDS` |
| 6.5 | Tests: match exacto · tolerancia · ambiguo · sin candidatos · idempotencia | ✅ | 45 tests nuevos |

---

## Etapa 7 — Cupos / Reservas de tours ⬜
*Prioridad baja. Ocasional. Paralelizable con Etapas 4-6.*

| # | Fase | Estado |
|---|------|--------|
| 7.1 | Modelo disponibilidad: tour + fecha + cupos | ⬜ |
| 7.2 | Reglas de confirmación data-driven (horarios en config, no hardcoded) | ⬜ |
| 7.3 | Recordatorios automáticos por cupo | ⬜ |

---

## Etapa 8 — Dashboards + WhatsApp 🔄

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 8.1 | Dashboard ventas/comisiones: `/dashboard_ventas` por vendedor, período, navegación meses | ✅ | `ResumenVentasService`; reemplaza `/resumen_empresa` |
| 8.2 | Dashboard flujo de caja: `/flujo_caja` ingresos vs egresos, conciliado vs pendiente | ✅ | `FlujoCajaService`; solo propietario |
| 8.3 | Reporte automático al grupo WhatsApp | ⬜ | Pendiente — proveedor WhatsApp sin definir |
| 8.4 | Dashboard Streamlit (`dashboard/app.py`): KPIs + gráficos Plotly ventas y flujo | ⬜ | Implementado local; pendiente deploy en Railway como tercer servicio |

---

## Etapa 9 — Atribución digital WhatsApp ⬜
*Mejora. Canal en pañales. Baja prioridad.*

| # | Fase | Estado |
|---|------|--------|
| 9.1 | QR con atribución: mensaje inicial "vengo de la tarjeta de X" | ⬜ |
| 9.2 | Captura del lead: de qué vendedor vino el cliente digital | ⬜ |
| 9.3 | Comisión digital: conectar al motor | ⬜ |

---

## Etapa 10 — Deployment Railway + Operación 🔄
*Railway (ex VPS). Desplegado en producción desde 2026-07-29.*

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 10.1 | Provisioning: Postgres + servicio web (FastAPI) + servicio worker (bot) + HTTPS automático | ✅ | Railway project `resourceful-wonder`; repo `ex4cto/ex4ctoreservas` en `main` |
| 10.2 | Migraciones y seed: `alembic upgrade head` en Railway + `scripts/demo_data.py` | ✅ | Migración base `0000` creada; cadena completa aplicada |
| 10.3 | Backups automáticos Postgres | ⬜ | Railway Pro incluye backups; configurar retención |
| 10.4 | Monitoreo: healthchecks + alertas caída bot / webhook | ⬜ | Pendiente |
| 10.5 | Secrets y seguridad: tokens en Railway env vars, HMAC webhook, roles por Telegram ID | ✅ | `GARAY_PROPIETARIO_TELEGRAM_IDS`, `GARAY_DEV_TELEGRAM_IDS`, `GARAY_FORWARD_EMAIL_SECRET` |

---

## Progreso global

```
Etapa 0   ████████████████████  100%  ✅
Etapa 1   ████████████████████  100%  ✅
Etapa 2   ████████████████████  100%  ✅
Etapa 3   ████████████████████  100%  ✅
Etapa 4   ████████████████████  100%  ✅  (prod Railway ✅)
Etapa 5   ████████████████████  100%  ✅
Etapa 6   ████████████████████  100%  ✅
Etapa 7   ░░░░░░░░░░░░░░░░░░░░    0%  ⬜
Etapa 8   ████████████░░░░░░░░   60%  🔄  (8.1 8.2 ✅ · 8.3 8.4 ⬜)
Etapa 9   ░░░░░░░░░░░░░░░░░░░░    0%  ⬜
Etapa 10  ████████████░░░░░░░░   60%  🔄  (10.1 10.2 10.5 ✅ · 10.3 10.4 ⬜)
```

**Tests:** 707 · **mypy:** strict clean · **ruff:** clean
