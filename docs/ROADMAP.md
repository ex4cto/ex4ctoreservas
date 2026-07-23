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

## Etapa 2 — Motor de Comisiones ⬜
*TDD obligatorio. El core del dinero — todo lo demás lo consume.*

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 2.1 | Reglas como datos: tabla splits por tipo cliente · capas de punto · excepciones | ⬜ | Versionado: snapshot por venta (históricos inmutables) |
| 2.2 | Pipeline por capas: punto (off-top) → referido (off-top) → split base → ajuste | ⬜ | Orden de capas a confirmar con Garay |
| 2.3 | Roles y multi-participante: vendedor/cerrador/ambos · caso digital | ⬜ | |
| 2.4 | Redondeo y cuadre: Decimal · invariante suma(comisiones)+agencia==total | ⬜ | Residuo de redondeo va a agencia |
| 2.5 | Tests exhaustivos TDD: un test por tipo cliente · combinaciones · invariante | ⬜ | |

> ⚠️ **Preguntas de negocio abiertas** (bloquean 2.2):
> - ¿20% punto 4 sale de bruto o de lo que queda para agencia?
> - ¿% digital es rango fijo o tecleado por venta?

---

## Etapa 3 — Tiquetera / Registro de ventas (Telegram) ⬜
*Hito 2 de pago (30%). Mata el Excel de Sharimel.*

| # | Fase | Estado |
|---|------|--------|
| 3.1 | Flujo determinista con botones: árbol de estados, máquina de estados explícita | ⬜ |
| 3.2 | Extracción IA (foto/audio→campos): puerto ExtractorIA, confirmación humana siempre | ⬜ |
| 3.3 | Registro venta + MotorComisiones + snapshot de regla aplicada | ⬜ |
| 3.4 | Salida a grupo WhatsApp: puerto NotificadorGrupo | ⬜ |
| 3.5 | Dashboard ventas: reemplaza Excel · comparar con Reservas Julio.xlsx | ⬜ |

---

## Etapa 4 — Ingresos bancarios (FastAPI / webhook) ⬜

| # | Fase | Estado |
|---|------|--------|
| 4.1 | Reusar webhook Forward Email: endpoint FastAPI + webhook secret | ⬜ |
| 4.2 | Parsers Bancolombia / Nequi → entidad Ingreso normalizada | ⬜ |
| 4.3 | Persistencia + idempotencia: deduplicación por correo | ⬜ |
| 4.4 | Clasificación inicial: todo ingreso nace "sin clasificar" | ⬜ |

---

## Etapa 5 — Egresos / Salidas ⬜

| # | Fase | Estado | Notas |
|---|------|--------|-------|
| 5.1 | Egresos automáticos: correos salientes Bancolombia/Nequi | ⬜ | Verificar si mandan correo en salientes |
| 5.2 | Egresos manuales: categorías en config/DB (nunca hardcodeadas) | ⬜ | |
| 5.3 | Recurrencia: gastos fijos como catálogo (arriendo, Sharimel, IA, plan, etc.) | ⬜ | |
| 5.4 | Persistencia: EgresoRepository | ⬜ | |

---

## Etapa 6 — Motor de Conciliación ⬜
*El valor central del proyecto. Depende de Etapas 3, 4 y 5.*

| # | Fase | Estado |
|---|------|--------|
| 6.1 | Estrategia de match: venta↔ingreso por monto + ventana fecha con tolerancia | ⬜ |
| 6.2 | Estados: matcheado · sin match · personal/sin clasificar · pendiente | ⬜ |
| 6.3 | Resolución manual asistida: sugerencias rankeadas, humano confirma | ⬜ |
| 6.4 | Cuenta mezclada: separar plata personal vs agencia | ⬜ |
| 6.5 | Tests: match exacto · tolerancia · ambiguo · duplicados mismo día | ⬜ |

---

## Etapa 7 — Cupos / Reservas de tours ⬜
*Prioridad baja. Ocasional. Paralelizable con Etapas 4-6.*

| # | Fase | Estado |
|---|------|--------|
| 7.1 | Modelo disponibilidad: tour + fecha + cupos | ⬜ |
| 7.2 | Reglas de confirmación data-driven (horarios en config, no hardcoded) | ⬜ |
| 7.3 | Recordatorios automáticos por cupo | ⬜ |

---

## Etapa 8 — Dashboards + WhatsApp ⬜

| # | Fase | Estado |
|---|------|--------|
| 8.1 | Dashboard ventas/comisiones: por vendedor, punto, período | ⬜ |
| 8.2 | Dashboard flujo de caja: ingresos vs egresos, conciliado vs sin clasificar | ⬜ |
| 8.3 | Reporte automático al grupo WhatsApp | ⬜ |

---

## Etapa 9 — Atribución digital WhatsApp ⬜
*Mejora. Canal en pañales. Baja prioridad.*

| # | Fase | Estado |
|---|------|--------|
| 9.1 | QR con atribución: mensaje inicial "vengo de la tarjeta de X" | ⬜ |
| 9.2 | Captura del lead: de qué vendedor vino el cliente digital | ⬜ |
| 9.3 | Comisión digital: conectar al motor | ⬜ |

---

## Etapa 10 — Deployment VPS + Operación ⬜
*Transversal. Se empieza a preparar en paralelo desde Etapa 3.*

| # | Fase | Estado |
|---|------|--------|
| 10.1 | Provisioning: Postgres · dos procesos · reverse proxy + HTTPS | ⬜ |
| 10.2 | Migraciones y seed: Alembic en deploy + seed de config inicial | ⬜ |
| 10.3 | Backups automáticos Postgres (la conciliación es plata, no se puede perder) | ⬜ |
| 10.4 | Monitoreo: healthchecks + alertas caída bot / webhook | ⬜ |
| 10.5 | Secrets y seguridad: tokens, webhook secret, acceso restringido | ⬜ |

---

## Progreso global

```
Etapa 0  ████████████████████  100%  ✅
Etapa 1  ████████████████████  100%  ✅
Etapa 2  ░░░░░░░░░░░░░░░░░░░░    0%  ⬜
Etapa 3  ░░░░░░░░░░░░░░░░░░░░    0%  ⬜
Etapas 4-10  ░░░░░░░░░░░░░░░░░  0%  ⬜
```

**Tests:** 87 · **mypy:** strict clean (78 archivos) · **ruff:** clean
