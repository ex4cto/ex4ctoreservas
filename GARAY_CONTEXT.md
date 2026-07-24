# Garay Tours — Contexto del Proyecto

> Archivo puente para no perder contexto mientras Engram se activa desde este repo.
> Cuando se abra una sesión parada en `C:/bots/garay tours`, migrar este contenido a Engram
> (topic keys sugeridos indicados en cada sección).

---

## 1. Charter — qué es este proyecto

`topic_key: garay/architecture/charter`

Nuevo sistema para la agencia de turismo **Garay Tours**. Reutiliza **dos proyectos existentes fusionados en UN solo sistema**:

- **jewelry_invoice_bot** (`C:/bots/joyeria bot/jewelry_invoice_bot_limpio`, repo `facturacionjoyeriasbot`) → se convierte en el sistema de **TIQUETERA**: registro de venta por vendedor/cerrador + comisiones + dashboard que hoy llena Sharimel a mano en un Excel local (`C:/bots/garay tours/Reservas Julio.xlsx`).
- **comprobante de pago** (`C:/bots/comprobante de pago`, repo `ex4ctopagos`, FastAPI, intercepta correos Bancolombia/Nequi) → se convierte en el control de **ENTRADAS/SALIDAS** de la cuenta personal de Garay.

**Por qué:** Garay Tours no tiene cuenta de empresa. Garay recibe pagos en su **Bancolombia y Nequi personales** (mezcla plata de agencia con plata personal). Sharimel llena un Excel local a mano, con errores. El contratista (el usuario) fue contratado para automatizar tiquetera + control de plata con dashboards.

Stack fuente:
- jewelry_invoice_bot = python-telegram-bot + SQLAlchemy + SQLite/Postgres, flujo por **botones/lógica** (no IA), extracción local ya migrada a faster-whisper (audio) + ollama/visión (foto).
- comprobante = FastAPI + Jinja2 + Postgres + Forward Email webhook, parsers Bancolombia/Nequi, dashboards operador + negocio.

---

## 2. Decisiones de arquitectura acordadas (en debate, NO en código aún)

`topic_key: garay/architecture/decisions`

1. **UN SOLO MOTOR / base compartida, DOS dashboards** en pantalla (facturación interna vs entradas/salidas). Tratarlos como dos apps sueltas NO sirve.
2. **La CONCILIACIÓN es el verdadero valor**: cada tiquetera (venta) se valida contra la plata real que entra a la cuenta de Garay. Ingreso que matchea tiquetera = plata de agencia; ingreso que no matchea = personal/sin clasificar (se marca a mano). Ninguno de los dos proyectos fuente hace esto hoy.
3. **Cuenta personal MEZCLADA → conciliación OBLIGATORIA desde el día uno** (no un lujo). No se sabe cuándo abrirán cuenta de empresa, pero es acción primordial pendiente de la empresa.
4. **IA SOLO para EXTRACCIÓN** (foto/audio/texto → campos estructurados; reusa faster-whisper + visión de la joyería). El **FLUJO** (elegir rol, confirmar montos, partir comisiones) va con **lógica determinista + botones Telegram**, NO IA — por costo y por seguridad (un número mal parseado en una comisión = plata real perdida). Patrón: **AI extrae, la lógica decide**.
5. Hay que **CONSTRUIR el módulo de SALIDAS/egresos** — el comprobante solo ve lo que ENTRA. Salidas: parte automática (correos bancarios de transferencias salientes) + parte carga manual (arriendo, nómina Sharimel, uniformes, proveedores).
6. Los **cupos/reservas de tours** no existen en ningún proyecto fuente — feature nuevo de cero.

---

## 3. Modelo de negocio y comisiones (con correcciones del usuario)

`topic_key: garay/business/model`

### Servicios (7)
1. Hospedajes — frenado, no administran apartamentos, solo alquiler por encargo.
2. Transportes — hay una van, administración frenada por flujo de caja.
3. Guianzas — conseguir guías de cualquier idioma para grupos.
4. Organización de eventos — logística de eventos.
5. Tours y alquiler de botes — **137 tours en total**.
6. Tiquetes de avión — bajo pedido.
7. Organización de operaciones turísticas — itinerarios completos.

### Puntos de venta (4)
- **Punto 1 — Hotel Marie Real**: vendedor/cerrador Tania y Eduardo. Arriendo 2M/mes.
- **Punto 2 — Mama Waldi**: David, Yolimar y Mairelis. Arriendo 1.5M/mes.
- **Punto 3 — Dora Hostal**: Máximo y Zaida. Arriendo 800k/mes.
- **Punto 4 — Crespo** (dentro de un restaurante): vendedor/cerrador **Kike**. Arriendo 0 (no se paga lugar). El **dueño del restaurante** recibe **20% de las ventas TOTALES del punto** (capa del punto, off the top). Nota: Kike es la persona; el 20% es del dueño del restaurante, NO de Kike.

**Generalmente los 8 freelancers son vendedores Y cerradores a la vez.**

### Splits por tipo de cliente
- **Interno** (cliente dentro del hotel/restaurante): agencia 60% / vendedor 20% / cerrador 20%.
- **Externo** (fuera del hotel/restaurante): agencia 40% / vendedor 30% / cerrador 30%.
- **Digital** (WhatsApp/redes, muy en pañales): agencia 80–100% / vendedor+cerrador 20–30%. En redes sociales quien cierre tour: 30% él / 70% agencia.
- **Referido** externo: 10% de la venta a quien recomendó.
- **Ocasionales**: ajustar % a mano.

### Reglas de comisión que impactan el diseño de la tiquetera
- El bot debe preguntar **"¿sos vendedor, cerrador o ambos?"** y asignar % según eso. Si una persona es **ambos** se lleva las dos tajadas (externo: 30+30 = 60%).
- **Caso a cubrir**: cuando vendedor y cerrador son personas DISTINTAS (típico en digital: uno captó, otro cerró), la tiquetera debe registrar a los **dos** con su rol, no solo "quién soy yo" — si no, se pierde la comisión del otro.
- Referencia de la joyería: da comisión **no hardcodeada, generalmente 2%** al asesor que hizo la venta. Garay es mucho más complejo (roles + tipos de cliente + capa de punto) → **motor de comisiones a construir casi de cero**.

### Modelo WhatsApp / atribución digital
- Cada freelancer entrega su **tarjeta física con QR** al WhatsApp oficial de la empresa (Meta verificado, IA responde hasta el cierre y pide intervención humana).
- Problema actual: al escanear el QR nadie sabe de qué vendedor vino el cliente.
- **Cambio propuesto y aceptado por el usuario**: modificar el QR para que el mensaje inicial diga **"vengo de la tarjeta de X vendedor"** → atribución automática del lead.
- El % del vendedor digital depende de cuánto intervino en el chat; hoy Garay lo decide subjetivamente.

### Salida de la venta
- Cuando se hace una venta con la tiquetera, se envía **toda la info a un grupo de WhatsApp** donde se ven todas las reservas y ventas hechas.

### Gastos fijos (mensuales salvo indicado)
- Papelería: 35k / millar de tarjetas.
- 10 tiqueteras: 170k.
- Uniformes: 16 camisas = 1.120.000; 8 pantalones = 400k.
- Carnets: 10k c/u × 8 vendedores = 80k.
- Arriendos: punto 1 = 2M, punto 2 = 1.5M, punto 3 = 800k, punto 4 = 0.
- Pasante Sharimel: 400k/mes (asistente de Garay, llena el Excel de ventas diarias).
- IA de WhatsApp: 30k/mes.
- Plan teléfono empresarial: 50k/mes.
- Teléfono a cuotas: 260k/mes.
- Ocasionales: meriendas, cumpleaños, días especiales, ayudas a vendedores.

### Reservas / cupos de tours
- Tours que requieren confirmar cupo/disponibilidad: **tour bahía, chivas rumberas, city tours, cualquier tour a Barú** → confirmar de 1h (máx) a 3h antes del inicio.
- Tours a **clubs de playa e islas privadas** → confirmar el **día anterior**.
- Salidas en bote/lancha/bus son en la **mañana**, excepto city tours / chivas rumberas / actividades dentro de la ciudad. Tour bahía puede ser de noche.

### Contexto legal/bancario
- La empresa es agencia **OPERADORA** de turismo (según RTN), no solo intermediaria.
- **NO tiene cuenta de banco** → Garay usa Bancolombia y Nequi personales para recibir el dinero de la empresa. Abrir cuenta de empresa es acción primordial pendiente.

---

## 4. Assets de referencia en la carpeta

`topic_key: garay/reference/assets`

- `Reservas Julio.xlsx` — Excel local que Sharimel llena a mano con las ventas diarias (no usan Google Sheets).
- `WhatsApp Image 2026-07-21 at 12.24.10 PM.jpeg` — tiquetera llenada de forma **correcta**.
- `WhatsApp Image 2026-07-21 at 12.24.11 PM.jpeg` — tiquetera llenada de forma **correcta**.
- `WhatsApp Image 2026-07-21 at 12.28.19 PM.jpeg` — tiquetera llenada de forma **incorrecta**.
- `situacion problema` — archivo de contexto crudo original del usuario.

---

## 5. Preguntas abiertas / próximos pasos

`topic_key: garay/open-questions`

- ¿Cuándo abren cuenta de empresa? (define cuán crítica es la conciliación — hoy: obligatoria).
- Confirmar modelo de datos de comisiones de la joyería antes de decidir cuánto se reusa vs se construye.
- Diseñar el módulo de salidas/egresos (no existe en comprobante).
- Diseñar el motor de conciliación tiquetera ↔ ingreso bancario.
- Diseñar cupos/reservas de tours.
- Definir arquitectura de fusión: comprobante es FastAPI (webhook) y la tiquetera es bot Telegram (polling) — decidir monolito único vs dos procesos sobre una base compartida.
