# Mapa del backend — Garay Tours

Este documento explica **cómo funciona el backend** de Garay Tours para no tener que explorar todo el código cada vez que hay que arreglar o extender algo. Está en dos capas:

- **Parte 1 — En criollo**: qué hace el sistema a simple vista (para entender el negocio y ubicarte).
- **Parte 2 — Técnico**: los módulos, sus responsabilidades y el flujo de datos entre ellos (para saber qué parte del código toca cuál).

> **Cómo usar este mapa.** Es un mapa **mental, no un GPS**. Te dice *en qué módulo* y *en qué capa* pasa cada cosa, y el **nombre de la función/símbolo** que la hace. Para la línea exacta, buscá ese símbolo con ripgrep (`rg "def calcular"`) — siempre está actualizado, aunque el código se mueva. Por eso acá **no hay números de línea**: se pudren; los nombres de módulo y de función, no.

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
- **Arquitectura hexagonal.** El "negocio" (dominio) no sabe nada de Telegram, SQL ni HTTP. Habla con el mundo a través de **puertos** (interfaces), y la infraestructura los implementa. Un solo lugar (composition root) arma todo.
- **Todo en `Decimal`.** La plata nunca es float — se usa el objeto `Dinero` para no tener errores de redondeo.

---

# PARTE 2 — Técnico (módulos, responsabilidades y flujo de datos)

## La arquitectura ES el mapa

Antes que cualquier índice: la estructura de carpetas ya te dice **dónde vive cada cosa**. Interná esto y encontrás casi todo sin buscar.

| Capa | Carpeta | Responsabilidad | Regla |
|---|---|---|---|
| **Dominio** | `dominio/` | Entidades, motor de comisiones/conciliación, `Dinero`. Lógica pura de negocio. | NO importa infraestructura (ni sqlalchemy, ni telegram, ni httpx). |
| **Puertos** | `dominio/puertos/` | Interfaces (ABC): lo que la app necesita del mundo (`repositorios.py` = 15 repos; `servicios_externos.py` = notificador, email, lector Excel, extractor IA). | Son las **costuras** donde se enchufa la infraestructura. |
| **Aplicación** | `aplicacion/` | Casos de uso: orquestan el dominio a través de puertos (FSM de tiquetera, registrar venta, conciliar, reportes, factura, import). | Depende de puertos, no de adapters concretos. |
| **Infraestructura** | `infraestructura/` | Implementa los puertos: adapters SQLA, handlers Telegram, webhook FastAPI, Resend, openpyxl. | Único lugar que toca SQL/HTTP/Telegram. |
| **Composition root** | `infraestructura/telegram/main.py` (bot) · `infraestructura/webhook/main.py` (webhook) · `dashboard/app.py` | Instancia los adapters concretos y los inyecta. | Único lugar donde se "arma" todo (DI). |

**Reglas prácticas para ubicar una línea:**
- ¿Regla de negocio (cómo se calcula/valida algo)? → `dominio/`
- ¿Orquestación de un caso de uso? → `aplicacion/`
- ¿Toca SQL, Telegram, HTTP, email, Excel? → `infraestructura/`
- ¿La interfaz entre app y mundo? → `dominio/puertos/`
- **Para la línea exacta**: `rg "<nombre_de_función>"`.

## Los procesos y su composition root

| Proceso | Módulo raíz | Arma |
|---|---|---|
| bot-worker | `infraestructura/telegram/main.py` | los 15 repos + todos los servicios + FSM (con roster de freelancers cargado al arranque) → `app.bot_data` → `run_polling` |
| webhook | `infraestructura/webhook/main.py` → `aplicacion/webhook/app.py` (`crear_app`) | solo `ingreso_repo`, `egreso_repo`, `correo_repo`, `notificador` |
| dashboard | `dashboard/app.py` | repos read-only por request, cacheados (`@st.cache_resource`) |

`Procfile`: `web` corre `alembic upgrade head` antes de uvicorn (el webhook **es dueño de las migraciones**); `worker` NO migra.

## Flujo 1 — Registrar venta + comisión + factura

Cada paso nombra el **módulo** y la **función** responsable (buscá el símbolo con `rg`).

```
Telegram msg → _make_handler(estado)                    [telegram/handlers.py]
  → FSMTiquetera.procesar_foto(estado, entrada, ctx)    [aplicacion/tiquetera/fsm.py]  (acumula ContextoVenta, puro)
  → si salida.listo:
    → _contexto_a_comando(update, ctx)                  [telegram/handlers.py]
        buscar_por_telegram_id(user.id) → freelancer.id (registrante)
        resuelve servicio_ids, pdv_id; crea Cliente; arma Participantes(vendedor_id/cerrador_id + nombres)
        → RegistrarVentaComando
    → RegistrarVentaService.ejecutar(cmd)               [aplicacion/tiquetera/servicio.py]
        1. Venta(...)                                   [dominio/ventas/entidades.py]  (invariantes: valor>0, neto≤valor…)
        2. reglas_repo.buscar_por_tipo_cliente(tipo)    → ReglasComision
        3. puntos_repo.buscar_por_id(pdv_id)            → PuntoDeVenta.porcentaje_capa
        4. MotorComisiones.calcular(venta, reglas, punto, %referido)   [dominio/comisiones/motor.py]
             SnapshotReglas.desde_reglas(reglas, punto)  (congela % )
             ganancia = valor − neto
             punto = ganancia×capa · vendedor = ganancia×%v · cerrador = ganancia×%c
             agencia = ganancia − punto − vendedor − cerrador   (residual)
             referido = valor × %referido                        (sobre bruto, aparte)
             assert punto+vendedor+cerrador+agencia == ganancia
             → DesgloseComision
        5. ventas_repo.guardar(venta)                   → tabla ventas
        6. comisiones_repo.guardar(ComisionRegistrada)  → tabla comisiones_registradas (snapshot en JSON)
        7. [si foto] tiqueteras_repo.guardar(...)
        8. notificador.notificar(html, grupo_id)        [telegram/notificador.py] → api.telegram.org
        → ResultadoRegistrarVenta(venta_id, desglose)
  → GenerarYGuardarFacturaService.ejecutar(ctx, resultado)  [aplicacion/factura/generar_y_guardar.py]
        persist-first: Factura(PENDIENTE) → guardar → ResendAdapter.enviar → estado ENVIADO/ERROR → guardar
```

## Flujo 2 — Webhook: correo bancario → movimiento (+ cuarentena/reproceso)

```
Forward Email → POST /webhook/email?secret=…            [webhook/rutas.py → función de la ruta]
  validar_secret (hmac)  ·  message_id vacío → 200
  detectar_banco(remitente, cuerpo)  → Bancolombia/Nequi/PSE | None→200  [webhook/parser/base.py]
  detectar_direccion(cuerpo)         → INGRESO | EGRESO                    [webhook/parser/base.py]
  existe_referencia(msgid)?          → 200 (idempotencia)
  fabrica.obtener_parser[_egreso](banco).parsear(html, texto)  [webhook/parser/fabrica.py]
    ok   → guardar_ingreso / guardar_egreso(...)  [aplicacion/webhook/servicio.py] → repo.guardar → tabla ingresos/egresos
    fail (ErrorParseoBanco) → _quarantine_and_alert()  [webhook/rutas.py]
             CorreoNoParseado → correo_repo.guardar (add(); IntegrityError = no-op)
             alerta dev (dev_telegram_ids) + alerta grupo (grupo_id)   [webhook/alertas.py]
  → siempre 200

Reproceso (tras arreglar un parser):
  reprocesar_pendientes()            [webhook/reproceso.py]
    listar_pendientes(max_intentos) → re-parsea → recuperado / ya_existía / falló(intentos++)
```

## Flujo 3 — Conciliación (ingreso ↔ venta)

```
/conciliar (dueño)                   [telegram/handlers_conciliacion.py]
  → ConciliarIngresosService.ejecutar()   [aplicacion/conciliacion/conciliar_ingresos.py]
      ingresos_repo.listar_sin_clasificar()  ·  ventas_repo.listar_por_periodo(rango)  (sin N+1)
      MotorConciliacion.conciliar(ingreso, candidatas)    [dominio/conciliacion/motor.py]
        score = 0.6·similitud_monto + 0.4·similitud_fecha   (tolerancia 5%, ventana 3d)
        score ≥ 0.90 → MATCHEADO · si no → PENDIENTE (sugiere) · sin candidatos → SIN_MATCH
      conciliaciones_repo.guardar(...)
/pendientes → botones [✅ Match | 👤 Personal | ❓ Sin match] → actualiza estado
```
Params en `config/settings.py` (`GARAY_CONCILIACION_*`). Egresos NO pasan por conciliación.

## Flujo 4 — Identidad → reportes

```
Freelancer.id (uuid)  →  VentaModel.vendedor_id / cerrador_id (FK nullable)   ← ventas nuevas
                      →  VentaModel.vendedor_nombre / cerrador_nombre (str)    ← snapshot + legacy

ResumenVentasService.ejecutar(mes, año)      [aplicacion/reportes/resumen_ventas.py]
  display_por_id = {f.id: f.display or f.nombre for f in freelancers_repo.listar_todos()}   (1 solo load, sin N+1)
  bucket por venta:  vendedor_id ? UUID→display  :  nombre snapshot→snapshot
  → ResumenVentas(por_vendedor con freelancer_id, por_canal, por_dia)

/mis_ventas (freelancer)             [telegram/handlers.py]
  buscar_por_telegram_id(user.id) → (id, nombre)
  ventas_repo.listar_por_freelancer_y_periodo(id, nombre, desde, hasta)   [persistencia/repositorios/ventas.py]
    WHERE vendedor_id=id OR cerrador_id=id
       OR (vendedor_id IS NULL AND vendedor_nombre=nombre)   ← name-match SOLO en filas sin id (no cruza personas)
       OR (cerrador_id IS NULL AND cerrador_nombre=nombre)
```

Otros reportes (sin dependencia de freelancer): `WaterfallVentasService`, `RankingTourService`, `RankingCanalService`, `FlujoCajaService`, `MovimientosRecientesService`, `ReconciliacionVentasIngresosService` — todos en `aplicacion/reportes/`.

## Flujo 5 — Import Excel

```
ImportarVentasExcelService.ejecutar(ruta, mes, año)     [aplicacion/importacion/importar_ventas_excel.py]
  LectorVentasExcelOpenpyxl.leer(ruta) → 4 hojas (Hotel/Externas/Crespo×2), dedup, Externas es maestro
  PASS 1 (sin escribir): resuelve cada nombre por listar_por_nombre; junta no_encontrados/ambiguos
     si hay alguno → raise ImportacionConNombresNoResueltos   (ABORT-ALL, nada se persiste)
  PASS 2 (si limpio): Venta(id=uuid5 determinista) + ComisionRegistrada → guardar  (idempotente)
```

## Roles y menús

En `infraestructura/telegram/bot.py`:
- `es_admin` es una **columna en `freelancers`** → define el menú admin en el arranque (`_post_init`).
- `propietario_telegram_ids` / `dev_telegram_ids` son **env vars**.
- **Menús** (`set_my_commands`, cosmético) vs **guards** (`infraestructura/telegram/auth.py`, se chequean en CADA comando): `@requiere_rol`, `@requiere_admin[_conv]`, `@requiere_propietario`.

## Índice: responsabilidad → módulo (+ símbolo a buscar con `rg`)

| Necesitás tocar… | Módulo | Símbolo (`rg`) |
|---|---|---|
| El "cerebro" de la conversación de venta | `aplicacion/tiquetera/fsm.py` | `class FSMTiquetera`, `procesar_foto` |
| Traducir Telegram → comando de venta | `infraestructura/telegram/handlers.py` | `_contexto_a_comando`, `_make_handler` |
| Orquestar el registro de venta | `aplicacion/tiquetera/servicio.py` | `RegistrarVentaService` |
| El cálculo de comisiones | `dominio/comisiones/motor.py` | `MotorComisiones`, `calcular` |
| El % del punto de venta | `dominio/puntos_venta/entidades.py` | `porcentaje_capa` |
| Las reglas por tipo de cliente | `dominio/comisiones/reglas.py` | `ReglasComision`, `SnapshotReglas` |
| El webhook (ruta + parseo + cuarentena) | `infraestructura/webhook/rutas.py`, `webhook/parser/` | ruta `/webhook/email`, `_quarantine_and_alert` |
| El motor de conciliación | `dominio/conciliacion/motor.py` | `MotorConciliacion`, `conciliar` |
| Identidad del freelancer | `dominio/freelancers/entidades.py`, `validaciones.py` | `class Freelancer`, `validar_cedula`, `derivar_display` |
| Reportes agrupados por id | `aplicacion/reportes/resumen_ventas.py`, `consulta_ventas.py` | `ResumenVentasService`, `ConsultaVentasService` |
| La query id-o-nombre | `infraestructura/persistencia/repositorios/ventas.py` | `listar_por_freelancer_y_periodo` |
| Factura (persist-first + Resend) | `aplicacion/factura/generar_y_guardar.py`, `infraestructura/email/adaptador_resend.py` | `GenerarYGuardarFacturaService`, `ResendAdapter` |
| Import Excel | `aplicacion/importacion/importar_ventas_excel.py` | `ImportarVentasExcelService` |
| **Dónde se arma TODO (DI)** | `infraestructura/telegram/main.py` | `crear_aplicacion`, `bot_data` |
| Todos los puertos (interfaces) | `dominio/puertos/repositorios.py`, `servicios_externos.py` | `class *Repository` |
| Todos los modelos ORM | `infraestructura/persistencia/modelos.py` | `class *Model` (15 tablas) |
| Engine + sesiones | `infraestructura/persistencia/motor.py` | `crear_engine`, `crear_fabrica_sesiones` |
| Tipo `Dinero` en SQL | `infraestructura/persistencia/tipos.py` | `TipoDinero` |
| Todas las env vars | `config/settings.py` | prefijo `GARAY_` |
| Split de procesos | `Procfile` | — |

## Cadena de migraciones (Alembic)

`0000` esquema inicial → `0001` es_admin → `0002` precio_neto → `0003` categoría servicios → `0004` facturas → `0005` correos_no_parseados → `0006` identidad freelancer (nombre_completo/cedula/display, drop unique nombre, add unique cedula) → `0007` ventas.vendedor_id/cerrador_id (FK). (+ algunas revisiones auto entre medio: canal_origen, score conciliación, timestamps ingresos/egresos.)

---

## Cómo mantener este mapa

- Actualizá **las dos partes** (criollo y técnico) del subsistema que toques.
- Referí siempre a **módulos y funciones**, nunca a números de línea — se pudren y te mandan al lugar equivocado con falsa confianza.
- Si movés o renombrás una función que está en el índice, actualizá el símbolo. Para todo lo demás, `rg` sobre el nombre te lleva a la línea exacta al instante.
