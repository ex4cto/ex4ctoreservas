# Garay Tours — Plan de Wiring Detallado

> Objetivo: conectar todas las capas para que el bot Telegram corra en producción.
> Estado al 2026-07-24: Etapas 0-3 completadas (150 tests). Este plan cubre el wiring.

---

## PASO 0 — Prerrequisitos manuales (sin código)

- 0.1 BotFather: crear/obtener token del bot Telegram
- 0.2 Crear grupo Telegram para notificaciones de ventas → anotar `grupo_id` (número negativo, ej: `-100123456789`)
- 0.3 Crear `.env` en la raíz del proyecto:
  ```
  GARAY_DATABASE_URL=postgresql+psycopg://user:pass@localhost/garay
  GARAY_TELEGRAM_BOT_TOKEN=...
  GARAY_GRUPO_NOTIFICACIONES_ID=-100...
  GARAY_WEBHOOK_SECRET=...
  GARAY_MONEDA_PREDETERMINADA=COP
  ```
- 0.4 Verificar Postgres corriendo y base de datos `garay` creada

---

## PASO 1 — Cambios de dominio (TDD estricto: RED → GREEN → mypy → ruff)

### 1.0 Arreglar tests existentes del FSM (hacerlos compilar primero)

Archivo: `tests/aplicacion/tiquetera/test_fsm.py`

- Cambiar fixture `fsm` para pasar args:
  ```python
  SERVICIOS_TEST = [(1, "Tour Playa Blanca"), (2, "Tour Isla"), (3, "City Tour")]
  PUNTOS_TEST = ["Marie Real", "Mama Waldi", "Sin punto"]

  @pytest.fixture()
  def fsm() -> FSMTiquetera:
      return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)
  ```
- Cambiar import de `ContextoVenta`: ahora viene de `garay.dominio.ventas.contexto`
  (o dejar el import desde `fsm` — funciona igual porque Python re-exporta)
- Cambiar `destinos=["playa_blanca"]` → `destinos_numeros=[1]`
- Cambiar `"toggle:playa_blanca"` → `"toggle:1"` (ahora son enteros)
- Agregar los tests para los 4 estados faltantes (ver §1.3)

### 1.1 ContextoVenta — agregar campos faltantes

Archivo: `src/garay/dominio/ventas/contexto.py`

Campos a agregar:
```python
numero_ticket: int | None = None
rol_registrante: str | None = None  # "vendedor" | "cerrador" | "ambos"
```

### 1.2 Venta aggregate — actualizar campos

Archivo: `src/garay/dominio/ventas/entidades.py`

- `servicio_id: UUID` → `servicio_ids: list[UUID]` (una venta puede cubrir varios destinos)
- Agregar `adultos: int = 1`
- Agregar `ninos: int = 0`
- Validación: `adultos >= 1`, `ninos >= 0`
- Actualizar `__post_init__` y tests de Venta

### 1.3 FSMTiquetera — agregar 4 estados faltantes

Archivo: `src/garay/aplicacion/tiquetera/fsm.py`

Agregar a `EstadoFSM`:
```python
NUMERO_TICKET = "numero_ticket"
PARTICIPANTE_NOMBRE = "participante_nombre"
PARTICIPANTE_ROL = "participante_rol"
PARTICIPANTE_OTRO = "participante_otro"
```

Flujo completo actualizado:
```
TIPO_RESERVA → PUNTO_DE_VENTA → DESTINO → CLIENTE_NOMBRE → CLIENTE_TELEFONO
→ CLIENTE_HOTEL → CLIENTE_HABITACION → FECHA_SALIDA → PAX_ADULTOS → PAX_NINOS
→ NUMERO_TICKET → MONTO_VALOR → MONTO_ABONO → MONTO_NETO
→ PARTICIPANTE_NOMBRE → PARTICIPANTE_ROL → [PARTICIPANTE_OTRO] → CONFIRMACION → TERMINADO
```

Implementar handlers:

**`_handle_pax_ninos`** — cambiar destino de `MONTO_VALOR` a `NUMERO_TICKET`

**`_handle_numero_ticket`**:
- Parsear int o aceptar "sin número" / "0" como None
- Guardar en `ctx.numero_ticket`
- Avanzar a `MONTO_VALOR`

**`_handle_monto_neto`** — cambiar destino de `CONFIRMACION` a `PARTICIPANTE_NOMBRE`

**`_handle_participante_nombre`**:
- Guardar nombre del registrante en `ctx.vendedor_nombre` (provisionalmente)
- Avanzar a `PARTICIPANTE_ROL`
- Mensaje: "¿Cuál es tu nombre?"
- Opciones de rol en el siguiente estado, no aquí

**`_handle_participante_rol`**:
- Opciones: `["Ambos", "Solo vendedor", "Solo cerrador"]`
- `"Ambos"` → `ctx.cerrador_nombre = ctx.vendedor_nombre`, avanzar a `CONFIRMACION`
- `"Solo vendedor"` → `ctx.rol_registrante = "vendedor"`, avanzar a `PARTICIPANTE_OTRO`
- `"Solo cerrador"` → `ctx.rol_registrante = "cerrador"`, avanzar a `PARTICIPANTE_OTRO`

**`_handle_participante_otro`**:
- Si `rol_registrante == "vendedor"`: pedir nombre del cerrador → guardar en `ctx.cerrador_nombre`
- Si `rol_registrante == "cerrador"`: pedir nombre del vendedor → swap: `ctx.cerrador_nombre = ctx.vendedor_nombre`, `ctx.vendedor_nombre = entrada`
- Avanzar a `CONFIRMACION`

**`_construir_resumen`** — agregar `numero_ticket`, `adultos`, `ninos` al resumen

### 1.4 ComisionRegistrada — nueva entidad persistible

Archivo nuevo: `src/garay/dominio/comisiones/entidades.py`

```python
@dataclass(eq=False)
class ComisionRegistrada:
    venta_id: UUID          # PK 1:1 con Venta
    desglose: DesgloseComision
    fecha: datetime.date
```

> IMPORTANTE: no confundir con `DesgloseComision` (VO inmutable de cálculo).
> `ComisionRegistrada` es la entidad persistida en DB.

### 1.5 Freelancer — agregar telegram_user_id

Archivo: `src/garay/dominio/freelancers/entidades.py`

```python
telegram_user_id: int | None = None
# Un admin puede registrar al freelancer antes de que inicie el bot
```

### 1.6 Puertos — agregar interfaces nuevas

Archivo: `src/garay/dominio/puertos/repositorios.py`

Agregar:
```python
class ComisionRegistradaRepository(ABC):
    @abstractmethod
    def guardar(self, comision: ComisionRegistrada) -> None: ...
    @abstractmethod
    def buscar_por_venta_id(self, venta_id: UUID) -> ComisionRegistrada | None: ...
```

Archivo: `src/garay/dominio/puertos/servicios_externos.py`

Agregar:
```python
class ExtractorReserva(ABC):
    @abstractmethod
    def extraer_de_foto(self, foto_bytes: bytes) -> ContextoVenta: ...
```

### 1.7 RegistrarVentaComando — actualizar

Archivo: `src/garay/aplicacion/tiquetera/comandos.py`

- `servicio_id: UUID` → `servicio_ids: list[UUID]`
- Agregar `adultos: int`
- Agregar `ninos: int`
- Agregar `numero_ticket: int | None = None`

### 1.8 RegistrarVentaService — actualizar

Archivo: `src/garay/aplicacion/tiquetera/servicio.py`

- Agregar `clientes_repo: ClienteRepository` al `__init__`
- Agregar `comisiones_repo: ComisionRegistradaRepository` al `__init__`
- En `ejecutar()`: después de calcular `DesgloseComision`, crear y persistir `ComisionRegistrada`
- Pasar `servicio_ids`, `adultos`, `ninos` al construir `Venta`

---

## PASO 2 — ORM Models

Archivo nuevo: `src/garay/infraestructura/persistencia/modelos.py`

Un modelo por aggregate/entidad. Todos usan `Base` de `persistencia/base.py`.
Usar `TipoDinero` para columnas monetarias.

| Modelo ORM | Tabla | Campos clave |
|---|---|---|
| `VentaModel` | `ventas` | id, valor_venta, neto, abono, servicio_ids (JSON — compatible SQLite/Postgres), cliente_id FK, tipo_cliente, fecha, adultos, ninos, vendedor_nombre, cerrador_nombre, punto_de_venta_id FK nullable, referido_nombre, estado |
| `ClienteModel` | `clientes` | id, nombre, tipo, telefono, hotel, numero_habitacion |
| `FreelancerModel` | `freelancers` | id, nombre, activo, telegram_user_id (BIGINT nullable) |
| `ServicioModel` | `servicios` | id, numero (INT, unique), nombre, descripcion, activo (BOOLEAN) |
| `PuntoDeVentaModel` | `puntos_venta` | id, nombre, porcentaje_capa |
| `ReglasComisionModel` | `reglas_comision` | id, tipo_cliente, porcentaje_vendedor, porcentaje_cerrador, porcentaje_referido_maximo |
| `TiqueteraModel` | `tiqueteras` | id, venta_id FK, foto_referencia, numero_fisico (BIGINT nullable — papel físico ingresado por usuario), numero_ticket (BIGINT — Sequence "ticket_seq", asignado por DB), procesada, datos_extraidos (JSON) |
| `ComisionRegistradaModel` | `comisiones_registradas` | venta_id (PK=FK), vendedor, cerrador, punto_de_venta, referido, agencia (todos TipoDinero), snapshot_json (JSON — serialización de SnapshotReglas para historial inmutable), fecha |
| `IngresoModel` | `ingresos` | id, banco, monto, fecha, referencia, remitente, clasificado, venta_id FK nullable |
| `EgresoModel` | `egresos` | id, descripcion, monto, fecha, categoria, tipo |
| `ConciliacionModel` | `conciliaciones` | id, ingreso_id FK, venta_id FK nullable, estado, notas |

> CRÍTICO: `Sequence("ticket_seq")` debe declararse explícitamente con `CreateSequence` en Alembic.
> NO confiar en autogenerate para esto.
>
> DECISIONES TOMADAS:
> - `servicio_ids` usa JSON (no ARRAY de Postgres) → compatible con SQLite para tests de repos
> - `TiqueteraModel.numero_fisico` = papel físico (usuario); `numero_ticket` = sistema (Sequence DB)
> - `ComisionRegistradaModel.snapshot_json` guarda el SnapshotReglas serializado para inmutabilidad histórica
> - `ServicioModel.numero` es UNIQUE (un número por tour)

---

## PASO 3 — Repositorios concretos (SQLAlchemy)

Directorio nuevo: `src/garay/infraestructura/persistencia/repositorios/`

Un archivo por repositorio. Patrón obligatorio:

```python
class VentaRepositorySQLAlchemy(VentaRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, venta: Venta) -> None:
        with self._sf.begin() as session:   # ← SIEMPRE begin(), nunca sf()
            session.merge(to_orm(venta))    # auto-rollback en excepción
```

> BUG CONOCIDO: `with self._sf()` NO hace rollback automático. Siempre `self._sf.begin()`.

Repositorios a implementar:
- `VentaRepositorySQLAlchemy`
- `ClienteRepositorySQLAlchemy`
- `FreelancerRepositorySQLAlchemy` — agregar método `buscar_por_telegram_id(telegram_user_id: int)`
- `ServicioRepositorySQLAlchemy`
- `PuntoDeVentaRepositorySQLAlchemy`
- `ReglasComisionRepositorySQLAlchemy`
- `TiqueteraRepositorySQLAlchemy`
- `ComisionRegistradaRepositorySQLAlchemy`

Cada repo necesita dos funciones helpers locales:
- `to_orm(entidad) -> Modelo`
- `to_domain(modelo) -> Entidad`

Tests: usar SQLite en memoria (`sqlite:///:memory:`) para tests de repositorios.

---

## PASO 4 — Alembic + Seed

### 4.1 Configurar Alembic

Archivo: `alembic/env.py`

Importar todos los modelos antes del `run_migrations_*`:
```python
from garay.infraestructura.persistencia import modelos  # noqa: F401
```
Esto es NECESARIO para que autogenerate los detecte.

### 4.2 Primera migración

```bash
alembic revision --autogenerate -m "initial schema"
```

Luego editar el archivo generado y verificar/agregar manualmente:
```python
from sqlalchemy import Sequence

def upgrade():
    op.execute(CreateSequence(Sequence("ticket_seq")))
    # ... resto de tablas
```

```bash
alembic upgrade head
```

### 4.3 Script de seed

Archivo: `scripts/seed.py`

Orden obligatorio (por FKs):
1. `servicios` — leer de `servicios_seed.json` (137 tours, precios como strings ×1000 COP)
2. `puntos_venta` — insertar los 4 físicos:
   - Marie Real (porcentaje_capa=0)
   - Mama Waldi (porcentaje_capa=0)
   - Dora Hostal (porcentaje_capa=0)
   - Crespo (porcentaje_capa=20) ← dueño restaurante cobra 20% off the top
3. `reglas_comision` — una por TipoCliente:
   - INTERNO: vendedor=20, cerrador=20, referido_max=10
   - EXTERNO: vendedor=30, cerrador=30, referido_max=10
   - DIGITAL: vendedor=15, cerrador=15, referido_max=10 ← confirmar % con Ryan
4. `freelancers` — los 8 vendedores (sin telegram_user_id por ahora)

> "Sin punto" es opción VIRTUAL del FSM. NO se persiste. punto_de_venta_id queda NULL en Venta.

---

## PASO 5 — Extractores concretos

### 5.1 ExtractorReservaOllama

Archivo nuevo: `src/garay/infraestructura/ia/extractor_reserva_ollama.py`

Implementa `ExtractorReserva`:
```python
class ExtractorReservaOllama(ExtractorReserva):
    def extraer_de_foto(self, foto_bytes: bytes) -> ContextoVenta:
        # Guarda bytes en temp file, llama ExtractorOllama, mapea DatosExtraidos → ContextoVenta
        ...
```

El mapeo `DatosExtraidos → ContextoVenta` pre-llena el contexto para el FSM
(si el usuario manda foto primero, el bot pre-rellena campos y pide confirmación).

---

## PASO 6 — Auth

### 6.1 Decorator `requiere_rol`

Archivo nuevo: `src/garay/infraestructura/telegram/auth.py`

```python
def requiere_rol(handler):
    async def wrapper(update, context):
        telegram_id = update.effective_user.id
        freelancer_repo: FreelancerRepository = context.bot_data["freelancer_repo"]
        if not freelancer_repo.buscar_por_telegram_id(telegram_id):
            await update.message.reply_text("No estás registrado como freelancer.")
            return ConversationHandler.END   # ← NUNCA None
        return await handler(update, context)
    return wrapper
```

> CRÍTICO: retornar `ConversationHandler.END`, no `None`. Si retorna `None` la conversación queda en estado zombie.

### 6.2 Hook de inyección de dependencias

En `bot.py`, usar `post_init`:
```python
async def setup_bot_data(app: Application) -> None:
    app.bot_data["fsm"] = app.bot_data["_fsm_instance"]
    app.bot_data["servicio"] = app.bot_data["_servicio_instance"]
    # etc.

app = Application.builder().token(token).post_init(setup_bot_data).build()
```

---

## PASO 7 — Reescribir handlers.py

Archivo: `src/garay/infraestructura/telegram/handlers.py`

### 7.1 Eliminar el singleton global

```python
# ELIMINAR esto:
_fsm = FSMTiquetera()  # BUG: sin args, falla en runtime
```

Reemplazar por:
```python
def _get_fsm(context: CallbackContext) -> FSMTiquetera:
    return context.bot_data["fsm"]
```

### 7.2 Implementar el bloque `salida.listo`

En `_enviar_salida` (o en el handler de CONFIRMACION), cuando `salida.listo is True`:
```python
if salida.listo:
    servicio: RegistrarVentaService = context.bot_data["servicio"]
    cmd = _contexto_a_comando(salida.contexto, context)
    try:
        resultado = servicio.ejecutar(cmd)
        await update.message.reply_text(f"Venta registrada. ID: {resultado.venta_id}")
    except ReglasComisionNoEncontradas:
        await update.message.reply_text("Error: reglas de comisión no configuradas.")
        return ConversationHandler.END
```

### 7.3 Función `_contexto_a_comando`

Mapea `ContextoVenta` → `RegistrarVentaComando`:
- Crea o busca `Cliente` vía `ClienteRepository`
- Resuelve `servicio_ids` a partir de `destinos_numeros` (buscar Servicios por numero)
- Resuelve `punto_de_venta_id` si `punto_de_venta_nombre` no es None
- Construye `Participantes`

### 7.4 Handlers con 4 nuevos estados

Agregar handlers PTB para: `handle_numero_ticket`, `handle_participante_nombre`, `handle_participante_rol`, `handle_participante_otro`.
Ya están en `estados.py` y `bot.py` los registra, pero los handlers deben existir en este archivo.

---

## PASO 8 — Wiring main.py

Archivo: `src/garay/infraestructura/telegram/main.py`

```python
def main() -> None:
    settings = obtener_settings()
    configurar_logging()

    engine = crear_engine(settings.database_url)
    sf = crear_fabrica_sesiones(engine)

    # Repos concretos
    ventas_repo = VentaRepositorySQLAlchemy(sf)
    clientes_repo = ClienteRepositorySQLAlchemy(sf)
    freelancers_repo = FreelancerRepositorySQLAlchemy(sf)
    servicios_repo = ServicioRepositorySQLAlchemy(sf)
    puntos_repo = PuntoDeVentaRepositorySQLAlchemy(sf)
    reglas_repo = ReglasComisionRepositorySQLAlchemy(sf)
    tiqueteras_repo = TiqueteraRepositorySQLAlchemy(sf)
    comisiones_repo = ComisionRegistradaRepositorySQLAlchemy(sf)

    # Cargar datos de DB para FSM (listas dinámicas, NO hardcodeadas)
    servicios_para_fsm = [
        (s.numero, s.nombre) for s in servicios_repo.listar()
    ]
    puntos_para_fsm = [p.nombre for p in puntos_repo.listar()] + ["Sin punto"]

    # Servicios de aplicación
    motor = MotorComisiones()
    notificador = NotificadorGrupoTelegram(settings.telegram_bot_token)
    servicio = RegistrarVentaService(
        ventas=ventas_repo,
        clientes=clientes_repo,
        reglas_repo=reglas_repo,
        tiqueteras=tiqueteras_repo,
        puntos_repo=puntos_repo,
        comisiones_repo=comisiones_repo,
        motor=motor,
        notificador=notificador,
        grupo_id=settings.grupo_notificaciones_id,
    )
    fsm = FSMTiquetera(servicios=servicios_para_fsm, puntos_venta=puntos_para_fsm)

    # Arrancar bot
    app = crear_aplicacion(settings.telegram_bot_token, servicio)
    app.bot_data["fsm"] = fsm
    app.bot_data["servicio"] = servicio
    app.bot_data["freelancer_repo"] = freelancers_repo
    app.run_polling()


if __name__ == "__main__":
    main()
```

### Smoke test final

```bash
python -m garay.infraestructura.telegram.main
```

Debe arrancar sin errores. Verificar en Telegram que `/start` abre la conversación.

---

## Orden de ejecución recomendado

```
Paso 0 (manual, 15 min)
  ↓
Paso 1 (TDD, ~3h) ← ESTAMOS AQUÍ (40% hecho)
  ↓
Paso 2 (ORM Models, ~1.5h)
  ↓
Paso 3 (Repos, ~2h)
  ↓
Paso 4 (Alembic + Seed, ~1h)
  ↓
Paso 5 (Extractor, ~30min)
  ↓
Paso 6 (Auth, ~45min)
  ↓
Paso 7 (Handlers, ~1.5h)
  ↓
Paso 8 (main.py, ~30min)
```

**Estado actual del Paso 1:**
- ✅ ContextoVenta movida al dominio
- ✅ FSMTiquetera constructor dinámico (servicios + puntos_venta)
- ✅ destinos_numeros: list[int]
- ❌ Tests del FSM no actualizados (fixture sin args, destinos viejo)
- ❌ 4 estados FSM faltantes (NUMERO_TICKET, PARTICIPANTE_*)
- ❌ Venta.servicio_ids (sigue siendo servicio_id singular)
- ❌ ComisionRegistrada entity
- ❌ telegram_user_id en Freelancer
- ❌ Puertos nuevos (ComisionRegistradaRepository, ExtractorReserva)
- ❌ RegistrarVentaComando/Service actualizados
