# Mapa del backend — Garay Tours

Este documento explica **cómo funciona el backend** de Garay Tours de dos formas, para no tener que explorar todo el código cada vez que hay que arreglar o extender algo:

- **Parte 1 — En criollo**: qué hace el sistema a simple vista (para entender el negocio y ubicarte).
- **Parte 2 — Técnico**: las dependencias y el flujo de datos en términos de código (para saber qué archivo enlaza con cuál).

Ambas partes cubren los mismos subsistemas, así que podés leer el "qué" en criollo y bajar al "cómo" técnico del mismo tema.

> Convención: `archivo:línea` es clickeable. Los caminos son relativos a `src/garay/` salvo que se indique otra cosa.

---

# PARTE 1 — En criollo (a simple vista)

## Qué es el sistema

Garay Tours es una agencia de tours. El backend es **un solo código** que corre como **cuatro procesos** distintos en Railway, todos conectados a la **misma base Postgres**:

| Proceso (Railway) | Qué es | Para qué |
|---|---|---|
| **bot-worker** | Bot de Telegram (polling) | Toda la interacción: registrar ventas, egresos, freelancers, ver reportes |
| **ex4ctoreservas** (`web`) | Webhook FastAPI (uvicorn) | Recibe los correos del banco y los convierte en movimientos. **Corre las migraciones al desplegar.** |
| **dashboard** | App Streamlit | Pantalla visual de reportes (solo lectura) para el dueño |
| **Postgres** | Base de datos | Todo se guarda acá |

Los procesos **no se llaman entre sí**: comparten la base de datos (y el webhook usa el token del bot para mandar alertas al grupo).

## Los 6 flujos principales

**1. Registrar una venta** 🎫
El vendedor conversa con el bot paso a paso (o manda una foto de la reserva que la IA lee). Al confirmar, el sistema: crea la venta, **calcula las comisiones** (quién se lleva qué), guarda todo, manda un aviso al grupo, y **genera + emaila la factura**.

**2. Comisiones** 💰
La ganancia de cada venta (valor − neto) se reparte en: **punto de venta** (ej. el 20% de Hebert en Crespo) → **vendedor** → **cerrador** → y lo que sobra es de la **agencia**. Los porcentajes de vendedor/cerrador dependen del tipo de cliente (INTERNO/EXTERNO/DIGITAL). El **referido** va aparte, sobre el valor total. Se guarda una "foto" de los porcentajes usados, así el histórico no cambia si mañana cambian las reglas.

**3. Movimientos bancarios** 🏦
Cada transferencia que entra o sale del banco (Bancolombia/Nequi/PSE) genera un correo. Un servicio de reenvío lo manda al webhook, que lo parsea y lo guarda como **ingreso** o **egreso**. Si el parser no entiende el correo (formato nuevo), lo manda a **cuarentena** y avisa por Telegram (una alerta técnica al dev, una en criollo al grupo). Después de arreglar el parser, un **reproceso** recupera lo que quedó en cuarentena.

**4. Conciliación** 🔗
El sistema intenta **matchear cada ingreso bancario con una venta**, puntuando por monto (60%, tolerancia 5%) y fecha (40%, ventana 3 días). Si el match es muy bueno (>90%) lo confirma solo; si no, lo deja pendiente para que el dueño lo revise con botones.

**5. Freelancers e identidad** 🧑
Cada persona que vende se registra como freelancer con **cédula + nombre + Telegram**. Su `id` (interno) es el ancla que une a la persona con sus ventas — así los reportes son exactos aunque haya dos personas con el mismo nombre o alguien cambie de nombre. Se crean/editan con `/nuevo_freelancer` y `/editar_freelancer`.

**6. Reportes + dashboard** 📊
Cada freelancer ve sus ventas con `/mis_ventas`. El dueño ve todo: resumen por vendedor, tours que más rinden, flujo de caja, y si el banco cuadra con lo que las comisiones dicen. El **dashboard** (Streamlit, aparte) lo muestra todo visual.

## Tres conceptos que atraviesan todo

- **Identidad por id, no por nombre.** El nombre es una etiqueta que se muestra; lo que identifica de verdad es el `id` (y la cédula). Por eso las ventas guardan `vendedor_id`/`cerrador_id`.
- **Arquitectura hexagonal.** El "negocio" (dominio) no sabe nada de Telegram, SQL ni HTTP. Habla con el mundo a través de **puertos** (interfaces), y la infraestructura los implementa. Un solo lugar (`main.py`) arma todo.
- **Todo en `Decimal`.** La plata nunca es float — se usa el objeto `Dinero` para no tener errores de redondeo.

---

# PARTE 2 — Técnico (dependencias y flujo de datos)

## Arquitectura hexagonal (las capas)

| Capa | Dónde | Regla |
|---|---|---|
| **Dominio** | `dominio/**` (entidades, motor de comisiones/conciliación, `Dinero`) | Lógica pura de negocio. NO importa infraestructura. |
| **Puertos** | `dominio/puertos/repositorios.py` (15 repos), `servicios_externos.py` (notificador, email, lector Excel, extractor IA) | Interfaces (ABC): lo que la app necesita del mundo. Son las **costuras**. |
| **Aplicación** | `aplicacion/**` (FSM de tiquetera, servicios: registrar venta, conciliar, reportes, factura, import) | Orquesta el dominio a través de puertos. |
| **Infraestructura** | `infraestructura/**` (adapters SQLA, Telegram, webhook FastAPI, Resend, openpyxl) | Implementa los puertos. Toca SQL/HTTP/Telegram. |
| **Composition root** | `infraestructura/telegram/main.py` (bot) · `infraestructura/webhook/main.py` (webhook) · `dashboard/app.py` | Único lugar donde se instancian los adapters concretos y se inyectan. |

Ningún código de dominio/aplicación importa `sqlalchemy`, `httpx`, `telegram` ni `openpyxl`.

## Los procesos y su composition root

| Proceso | Entry point | Arma |
|---|---|---|
| bot-worker | `infraestructura/telegram/main.py:64` | los 15 repos + todos los servicios + FSM (con roster de freelancers cargado al arranque) → `app.bot_data` (24 claves) → `run_polling` |
| webhook | `infraestructura/webhook/main.py` → `aplicacion/webhook/app.py:crear_app` | solo `ingreso_repo`, `egreso_repo`, `correo_repo`, `notificador` |
| dashboard | `dashboard/app.py` | repos read-only por request, cacheados (`@st.cache_resource`) |

`Procfile`: `web` corre `alembic upgrade head` antes de uvicorn (el webhook **es dueño de las migraciones**); `worker` NO migra.

## Flujo 1 — Registrar venta + comisión + factura

```
Telegram msg → _make_handler(estado)                    [telegram/handlers.py:429]
  → FSMTiquetera.procesar_foto(estado, entrada, ctx)    [aplicacion/tiquetera/fsm.py:269]  (acumula ContextoVenta, puro)
  → si salida.listo:
    → _contexto_a_comando(update, ctx)                  [telegram/handlers.py:119]
        buscar_por_telegram_id(user.id) → freelancer.id (registrante)
        resuelve servicio_ids, pdv_id; crea Cliente; arma Participantes(vendedor_id/cerrador_id + nombres)
        → RegistrarVentaComando
    → RegistrarVentaService.ejecutar(cmd)               [aplicacion/tiquetera/servicio.py:52]
        1. Venta(...)                                   [dominio/ventas/entidades.py:23]  (invariantes: valor>0, neto≤valor…)
        2. reglas = reglas_repo.buscar_por_tipo_cliente(tipo)   → ReglasComision
        3. punto = puntos_repo.buscar_por_id(pdv_id)            → PuntoDeVenta.porcentaje_capa
        4. motor.calcular(venta, reglas, punto, %referido)      [dominio/comisiones/motor.py:20]
             SnapshotReglas.desde_reglas(reglas, punto)  (congela % )
             ganancia = valor − neto
             punto = ganancia×capa · vendedor = ganancia×%v · cerrador = ganancia×%c
             agencia = ganancia − punto − vendedor − cerrador   (residual)
             referido = valor × %referido                        (sobre bruto, aparte)
             assert punto+vendedor+cerrador+agencia == ganancia
             → DesgloseComision(vendedor,cerrador,punto,referido,agencia,snapshot)
        5. ventas.guardar(venta)                        → tabla ventas
        6. comisiones.guardar(ComisionRegistrada)       → tabla comisiones_registradas (snapshot en JSON)
        7. [si foto] tiqueteras.guardar(...)
        8. notificador.notificar(html, grupo_id)        [telegram/notificador.py:21] → api.telegram.org
        → ResultadoRegistrarVenta(venta_id, desglose)
  → GenerarYGuardarFacturaService.ejecutar(ctx, resultado)  [aplicacion/factura/generar_y_guardar.py:41]
        persist-first: Factura(PENDIENTE) → guardar → ResendAdapter.enviar → estado ENVIADO/ERROR → guardar
```

## Flujo 2 — Webhook: correo bancario → movimiento (+ cuarentena/reproceso)

```
Forward Email → POST /webhook/email?secret=…            [webhook/rutas.py:129]
  validar_secret (hmac)  ·  message_id vacío → 200
  detectar_banco(remitente, cuerpo)  → Bancolombia/Nequi/PSE | None→200  [parser/base.py:98]
  detectar_direccion(cuerpo)         → INGRESO | EGRESO             [parser/base.py:121]
  existe_referencia(msgid)?          → 200 (idempotencia)
  obtener_parser[_egreso](banco).parsear(html, texto)  [parser/fabrica.py]
    ok   → guardar_ingreso/egreso(...)  [aplicacion/webhook/servicio.py:15/41] → repo.guardar → tabla ingresos/egresos
    fail (ErrorParseoBanco) → _quarantine_and_alert()  [webhook/rutas.py:59]
             CorreoNoParseado → correo_repo.guardar (add(); IntegrityError = no-op)
             alerta dev (dev_telegram_ids) + alerta grupo (grupo_id)   [webhook/alertas.py]
  → siempre 200

Reproceso (tras arreglar un parser):
  reprocesar_pendientes()            [webhook/reproceso.py:40]
    listar_pendientes(max_intentos) → re-parsea → recuperado / ya_existía / falló(intentos++)
```

## Flujo 3 — Conciliación (ingreso ↔ venta)

```
/conciliar (dueño)                   [telegram/handlers_conciliacion.py:38]
  → ConciliarIngresosService.ejecutar()   [aplicacion/conciliacion/conciliar_ingresos.py:42]
      ingresos.listar_sin_clasificar()  ·  ventas.listar_por_periodo(rango)  (sin N+1)
      motor.conciliar(ingreso, candidatas)    [dominio/conciliacion/motor.py:29]
        score = 0.6·similitud_monto + 0.4·similitud_fecha   (tolerancia 5%, ventana 3d)
        score ≥ 0.90 → MATCHEADO · si no → PENDIENTE (sugiere) · sin candidatos → SIN_MATCH
      conciliaciones.guardar(...)
/pendientes → botones [✅ Match | 👤 Personal | ❓ Sin match] → actualiza estado
```
Params en `config/settings.py` (`GARAY_CONCILIACION_*`). Egresos NO pasan por conciliación.

## Flujo 4 — Identidad → reportes

```
Freelancer.id (uuid)  →  VentaModel.vendedor_id / cerrador_id (FK nullable)   ← ventas nuevas
                      →  VentaModel.vendedor_nombre / cerrador_nombre (str)    ← snapshot + legacy

ResumenVentasService.ejecutar(mes, año)      [aplicacion/reportes/resumen_ventas.py]
  display_por_id = {f.id: f.display or f.nombre for f in freelancers.listar_todos()}   (1 solo load, sin N+1)
  bucket por venta:  vendedor_id ? UUID→display  :  nombre snapshot→snapshot
  → ResumenVentas(por_vendedor con freelancer_id, por_canal, por_dia)

/mis_ventas (freelancer)             [telegram/handlers.py:554]
  buscar_por_telegram_id(user.id) → (id, nombre)
  venta_repo.listar_por_freelancer_y_periodo(id, nombre, desde, hasta)   [repositorios/ventas.py:82]
    WHERE vendedor_id=id OR cerrador_id=id
       OR (vendedor_id IS NULL AND vendedor_nombre=nombre)   ← name-match SOLO en filas sin id (no cruza personas)
       OR (cerrador_id IS NULL AND cerrador_nombre=nombre)
```

Otros reportes (sin dependencia de freelancer): `WaterfallVentas`, `RankingTour`, `RankingCanal`, `FlujoCaja`, `MovimientosRecientes`, `ReconciliacionVentasIngresos`.

## Flujo 5 — Import Excel

```
ImportarVentasExcelService.ejecutar(ruta, mes, año)     [aplicacion/importacion/importar_ventas_excel.py:65]
  LectorVentasExcelOpenpyxl.leer(ruta) → 4 hojas (Hotel/Externas/Crespo×2), dedup, Externas es maestro
  PASS 1 (sin escribir): resuelve cada nombre por listar_por_nombre; junta no_encontrados/ambiguos
     si hay alguno → raise ImportacionConNombresNoResueltos   (ABORT-ALL, nada se persiste)
  PASS 2 (si limpio): Venta(id=uuid5 determinista) + ComisionRegistrada → guardar  (idempotente)
```

## Roles y menús (bot.py)

- `es_admin` es una **columna en `freelancers`** → define el menú admin en el arranque (`_post_init` en `bot.py:203`).
- `propietario_telegram_ids` / `dev_telegram_ids` son **env vars**.
- **Menús** (`set_my_commands`, cosmético) vs **guards** (`auth.py`, se chequean en CADA comando): `@requiere_rol`, `@requiere_admin[_conv]`, `@requiere_propietario`.

## Índice de archivos clave

| Necesitás… | Archivo:línea |
|---|---|
| El "cerebro" de la conversación de venta | `aplicacion/tiquetera/fsm.py:22` (estados), `:269` (procesar) |
| Traducir Telegram → comando de venta | `infraestructura/telegram/handlers.py:119` (`_contexto_a_comando`), `:429` (factory de handlers) |
| Orquestar el registro de venta | `aplicacion/tiquetera/servicio.py:52` |
| El cálculo de comisiones | `dominio/comisiones/motor.py:20` |
| El % del punto de venta | `dominio/puntos_venta/entidades.py` (`porcentaje_capa`) |
| Las reglas por tipo de cliente | `dominio/comisiones/reglas.py` |
| El webhook (ruta + parseo + cuarentena) | `infraestructura/webhook/rutas.py:129`, `parser/`, `:59` (cuarentena) |
| El motor de conciliación | `dominio/conciliacion/motor.py:29` |
| Identidad del freelancer | `dominio/freelancers/entidades.py:12`, `validaciones.py:8` |
| Reportes agrupados por id | `aplicacion/reportes/resumen_ventas.py`, `consulta_ventas.py` |
| La query id-o-nombre | `infraestructura/persistencia/repositorios/ventas.py:82` |
| Factura (persist-first + Resend) | `aplicacion/factura/generar_y_guardar.py:30`, `infraestructura/email/adaptador_resend.py:10` |
| Import Excel | `aplicacion/importacion/importar_ventas_excel.py:65` |
| **Dónde se arma TODO (DI)** | `infraestructura/telegram/main.py:64`, `:189` (`bot_data`) |
| Todos los puertos (interfaces) | `dominio/puertos/repositorios.py`, `servicios_externos.py` |
| Todos los modelos ORM | `infraestructura/persistencia/modelos.py` (15 tablas) |
| Engine + sesiones | `infraestructura/persistencia/motor.py:16` |
| Tipo `Dinero` en SQL | `infraestructura/persistencia/tipos.py:22` (`TipoDinero`) |
| Todas las env vars | `config/settings.py:24` (prefijo `GARAY_`) |
| Split de procesos | `Procfile` |

## Cadena de migraciones (Alembic)

`0000` esquema inicial → `0001` es_admin → `0002` precio_neto → `0003` categoría servicios → `0004` facturas → `0005` correos_no_parseados → `0006` identidad freelancer (nombre_completo/cedula/display, drop unique nombre, add unique cedula) → `0007` ventas.vendedor_id/cerrador_id (FK). (+ algunas revisiones auto entre medio: canal_origen, score conciliación, timestamps ingresos/egresos.)

---

## Cómo mantener este mapa

Cuando agregues un flujo o cambies una dependencia importante, actualizá **las dos partes** (el criollo y el técnico) del subsistema que tocaste, y el índice de archivos si movés algo clave. La idea es que este doc te ahorre explorar todo el código la próxima vez.
