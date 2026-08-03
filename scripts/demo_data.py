#!/usr/bin/env python
"""Insert demo data for live dashboard testing.

Run with:
    uv run python scripts/demo_data.py

Idempotent via deterministic UUIDs — safe to re-run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import garay.infraestructura.persistencia.tipos  # noqa: F401 — registers TipoDinero
from garay.config import obtener_settings
from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.persistencia.modelos import (
    ClienteModel,
    ComisionRegistradaModel,
    ConciliacionModel,
    EgresoModel,
    IngresoModel,
    VentaModel,
)
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones

NS = uuid.UUID("d3e0d4a0-0000-0000-0000-000000000000")
AÑO, MES = 2026, 7


def did(key: str) -> uuid.UUID:
    return uuid.uuid5(NS, key)


def dinero(monto: int | Decimal) -> Dinero:
    return Dinero(Decimal(str(monto)))


# (key, cliente, vendedor, cerrador, valor, neto, dia, adultos, tipo_cliente, canal_origen)
VENTAS: list[tuple] = [
    # ── Semana 1 ─────────────────────────────────────────────────────────
    ("v1",  "Carlos Pérez",       "Juan",   "Juan",   260_000, 200_000,  3, 2, "INTERNO",  None),
    ("v2",  "Ana Gómez",          "María",  "María",  310_000, 240_000,  5, 1, "INTERNO",  None),
    ("v3",  "Luis Herrera",       "Juan",   "Pedro",  520_000, 410_000,  8, 3, "INTERNO",  None),
    ("v13", "Roberto Sánchez",    "Ana",    "Ana",    450_000, 350_000,  2, 3, "INTERNO",  None),
    ("v14", "Paola Cifuentes",    "Carlos", "Carlos", 280_000, 210_000,  3, 2, "INTERNO",  None),
    ("v15", "Eduardo Reyes",      "Juan",   "María",  600_000, 470_000,  4, 4, "INTERNO",  None),
    ("v16", "Natalia Ortega",     "Ana",    "Ana",    150_000, 110_000,  5, 1, "EXTERNO",  None),
    ("v17", "Santiago García",    "María",  "Juan",   720_000, 570_000,  6, 5, "INTERNO",  None),
    ("v18", "Laura Acosta",       "Carlos", "Pedro",  330_000, 250_000,  7, 2, "INTERNO",  None),
    # ── Semana 2 ─────────────────────────────────────────────────────────
    ("v4",  "Sofia Martínez",     "María",  "María",  180_000, 140_000, 10, 1, "INTERNO",  None),
    ("v5",  "Daniel Torres",      "Pedro",  "Pedro",  650_000, 510_000, 12, 4, "INTERNO",  None),
    ("v6",  "Valentina Cruz",     "Juan",   "Juan",   290_000, 220_000, 14, 2, "INTERNO",  None),
    ("v19", "Diego Ramírez",      "Ana",    "Carlos", 490_000, 380_000,  9, 3, "DIGITAL",  "WhatsApp"),  # noqa: E501
    ("v20", "Mariana López",      "Juan",   "Juan",   200_000, 150_000,  9, 1, "INTERNO",  None),
    ("v21", "Ricardo Aguirre",    "María",  "María",  560_000, 440_000, 10, 4, "INTERNO",  None),
    ("v22", "Catalina Peña",      "Pedro",  "Ana",    380_000, 290_000, 11, 2, "EXTERNO",  None),
    ("v23", "Julián Medina",      "Carlos", "Carlos", 440_000, 340_000, 12, 3, "INTERNO",  None),
    ("v24", "Patricia Vargas",    "Ana",    "María",  270_000, 200_000, 13, 2, "DIGITAL",  "Instagram"),  # noqa: E501
    ("v25", "Hernán Castro",      "Juan",   "Pedro",  810_000, 640_000, 14, 6, "INTERNO",  None),
    # ── Semana 3 ─────────────────────────────────────────────────────────
    ("v7",  "Andrés Vargas",      "María",  "Pedro",  480_000, 370_000, 16, 3, "INTERNO",  None),
    ("v8",  "Camila Ríos",        "Pedro",  "Pedro",  220_000, 170_000, 18, 1, "INTERNO",  None),
    ("v26", "Alejandra Rios",     "María",  "Juan",   350_000, 270_000, 15, 2, "INTERNO",  None),
    ("v27", "Nelson Gómez",       "Carlos", "Carlos", 190_000, 140_000, 15, 1, "EXTERNO",  None),
    ("v28", "Monica Torres",      "Ana",    "Ana",    630_000, 500_000, 16, 4, "INTERNO",  None),
    ("v29", "Sergio Molina",      "Juan",   "María",  290_000, 220_000, 17, 2, "DIGITAL",  "TikTok"),  # noqa: E501
    ("v30", "Claudia Vega",       "Pedro",  "Pedro",  520_000, 410_000, 18, 3, "INTERNO",  None),
    ("v31", "Mauricio Álvarez",   "María",  "Carlos", 420_000, 330_000, 19, 3, "INTERNO",  None),
    ("v32", "Diana Muñoz",        "Carlos", "Juan",   175_000, 130_000, 20, 1, "EXTERNO",  None),
    # ── Semana 4 ─────────────────────────────────────────────────────────
    ("v9",  "Felipe Morales",     "Juan",   "Juan",   390_000, 300_000, 20, 2, "INTERNO",  None),
    ("v10", "Isabella Castillo",  "María",  "María",  710_000, 560_000, 22, 5, "INTERNO",  None),
    ("v11", "Mateo Jiménez",      "Pedro",  "Juan",   340_000, 260_000, 24, 2, "INTERNO",  None),
    ("v12", "Lucía Mendoza",      "Juan",   "María",  560_000, 435_000, 26, 4, "INTERNO",  None),
    ("v33", "Gustavo Ospina",     "Ana",    "Ana",    680_000, 540_000, 21, 5, "INTERNO",  None),
    ("v34", "Carolina Pinto",     "Juan",   "Pedro",  310_000, 240_000, 22, 2, "DIGITAL",  "Facebook"),  # noqa: E501
    ("v35", "Wilson Cruz",        "Pedro",  "María",  450_000, 350_000, 22, 3, "INTERNO",  None),
    ("v36", "Yanira Soto",        "María",  "María",  590_000, 465_000, 23, 4, "INTERNO",  None),
    ("v37", "Rafael Bermúdez",    "Carlos", "Carlos", 240_000, 180_000, 24, 2, "INTERNO",  None),
    ("v38", "Elizabeth Mora",     "Ana",    "Juan",   860_000, 680_000, 24, 6, "INTERNO",  None),
    ("v39", "Gonzalo Duarte",     "Juan",   "María",  320_000, 245_000, 25, 2, "DIGITAL",  "Google"),  # noqa: E501
    ("v40", "Beatriz Salazar",    "Pedro",  "Pedro",  470_000, 370_000, 25, 3, "INTERNO",  None),
    # ── Últimos días ─────────────────────────────────────────────────────
    ("v41", "Harold Jiménez",     "María",  "Carlos", 130_000,  95_000, 26, 1, "EXTERNO",  None),
    ("v42", "Yolanda Cárdenas",   "Carlos", "Ana",    550_000, 435_000, 26, 4, "INTERNO",  None),
    ("v43", "Ivan Rojas",         "Ana",    "Pedro",  385_000, 300_000, 27, 2, "INTERNO",  None),
    ("v44", "Pilar Ávila",        "Juan",   "Juan",   700_000, 555_000, 27, 5, "INTERNO",  None),
    ("v45", "Oscar Suárez",       "María",  "María",  250_000, 190_000, 28, 2, "INTERNO",  None),
    ("v46", "Liliana Herrera",    "Pedro",  "Carlos", 430_000, 340_000, 28, 3, "INTERNO",  None),
    ("v47", "Elkin Palacios",     "Carlos", "Ana",    580_000, 460_000, 29, 4, "INTERNO",  None),
    ("v48", "Soraya Méndez",      "Ana",    "Juan",   295_000, 225_000, 29, 2, "INTERNO",  None),
    ("v49", "Camilo Nieto",       "Juan",   "Pedro",  760_000, 600_000, 30, 5, "INTERNO",  None),
    ("v50", "Esperanza Rueda",    "María",  "María",  340_000, 265_000, 30, 2, "INTERNO",  None),
]

INGRESOS: list[tuple] = [
    # (key, banco, monto, referencia, dia, clasificado)
    ("i1",  "Bancolombia", 260_000, "BC-2026-001",  4, True),
    ("i2",  "Nequi",       310_000, "NQ-2026-002",  6, True),
    ("i3",  "Bancolombia", 520_000, "BC-2026-003",  9, True),
    ("i4",  "Nequi",       180_000, "NQ-2026-004", 11, True),
    ("i5",  "Bancolombia", 650_000, "BC-2026-005", 13, True),
    ("i6",  "Bancolombia", 290_000, "BC-2026-006", 15, False),
    ("i7",  "Nequi",       480_000, "NQ-2026-007", 17, False),
    ("i8",  "Bancolombia", 220_000, "BC-2026-008", 19, True),
    ("i9",  "Nequi",       390_000, "NQ-2026-009", 21, True),
    ("i10", "Bancolombia", 710_000, "BC-2026-010", 23, True),
    ("i11", "Bancolombia", 145_000, "BC-2026-011", 25, False),
    ("i12", "Nequi",        85_000, "NQ-2026-012", 27, False),
    # Nuevos
    ("i13", "Nequi",       450_000, "NQ-2026-013",  3, True),
    ("i14", "Bancolombia", 280_000, "BC-2026-014",  4, True),
    ("i15", "Nequi",       600_000, "NQ-2026-015",  5, True),
    ("i16", "Bancolombia", 150_000, "BC-2026-016",  6, True),
    ("i17", "Nequi",       720_000, "NQ-2026-017",  7, True),
    ("i18", "Bancolombia", 330_000, "BC-2026-018",  8, True),
    ("i19", "Nequi",       490_000, "NQ-2026-019", 10, True),
    ("i20", "Bancolombia", 200_000, "BC-2026-020", 10, True),
    ("i21", "Nequi",       560_000, "NQ-2026-021", 11, True),
    ("i22", "Bancolombia", 380_000, "BC-2026-022", 12, True),
    ("i23", "Nequi",       440_000, "NQ-2026-023", 13, True),
    ("i24", "Bancolombia", 270_000, "BC-2026-024", 14, True),
    ("i25", "Nequi",       810_000, "NQ-2026-025", 15, True),
    ("i26", "Bancolombia", 350_000, "BC-2026-026", 16, True),
    ("i27", "Nequi",       190_000, "NQ-2026-027", 16, False),
    ("i28", "Bancolombia", 630_000, "BC-2026-028", 17, True),
    ("i29", "Nequi",       175_000, "NQ-2026-029", 19, False),
    ("i30", "Bancolombia", 680_000, "BC-2026-030", 22, True),
    ("i31", "Nequi",       310_000, "NQ-2026-031", 23, True),
    ("i32", "Bancolombia", 450_000, "BC-2026-032", 23, True),
    ("i33", "Nequi",       590_000, "NQ-2026-033", 24, True),
    ("i34", "Bancolombia", 240_000, "BC-2026-034", 25, True),
    ("i35", "Nequi",       860_000, "NQ-2026-035", 25, True),
    ("i36", "Bancolombia", 320_000, "BC-2026-036", 26, True),
    ("i37", "Nequi",       470_000, "NQ-2026-037", 26, True),
    ("i38", "Bancolombia", 130_000, "BC-2026-038", 27, False),
    ("i39", "Nequi",       550_000, "NQ-2026-039", 28, True),
    ("i40", "Bancolombia", 760_000, "BC-2026-040", 30, False),
]

EGRESOS: list[tuple] = [
    # (key, descripcion, categoria, monto, dia)
    ("e1",  "Arriendo oficina julio",         "Arriendos",    1_800_000,  1),
    ("e2",  "Nómina Juan",                    "Nómina",       1_200_000,  1),
    ("e3",  "Nómina María",                   "Nómina",       1_200_000,  1),
    ("e4",  "Nómina Pedro",                   "Nómina",         900_000,  1),
    ("e5",  "Internet y teléfono",            "Servicios",      120_000,  5),
    ("e6",  "Papelería y útiles",             "Papelería",       45_000,  8),
    ("e7",  "Mantenimiento computadores",     "Servicios",      180_000, 10),
    ("e8",  "Publicidad Facebook Ads",        "Marketing",      250_000, 12),
    ("e9",  "Almuerzo reunión equipo",        "Varios",          95_000, 15),
    ("e10", "Transporte cliente hotel",       "Transporte",      60_000, 18),
    ("e11", "Publicidad Instagram",           "Marketing",      150_000, 20),
    ("e12", "Servicios contabilidad",         "Servicios",      200_000, 25),
    # Nuevos
    ("e13", "Nómina Ana",                     "Nómina",         900_000,  1),
    ("e14", "Nómina Carlos",                  "Nómina",         900_000,  1),
    ("e15", "Hosting y dominio",              "Servicios",       80_000,  3),
    ("e16", "Publicidad Google Ads",          "Marketing",      320_000,  7),
    ("e17", "Impresión material publicitario","Marketing",      190_000,  9),
    ("e18", "Recarga combustible furgón",     "Transporte",     450_000, 10),
    ("e19", "Seguro vehículo",                "Varios",         380_000, 11),
    ("e20", "TikTok Ads julio",               "Marketing",      280_000, 14),
    ("e21", "Compra insumos cafetería",       "Varios",          72_000, 16),
    ("e22", "Recarga combustible furgón 2",   "Transporte",     480_000, 18),
    ("e23", "Licencia software gestión",      "Servicios",      160_000, 20),
    ("e24", "Publicidad Instagram 2",         "Marketing",      200_000, 21),
    ("e25", "Viáticos guía turístico",        "Transporte",     240_000, 22),
    ("e26", "Suministros oficina",            "Papelería",       55_000, 24),
    ("e27", "Recarga combustible furgón 3",   "Transporte",     460_000, 26),
    ("e28", "Cuota préstamo bancario",        "Varios",         750_000, 28),
    ("e29", "Publicidad Facebook Ads 2",      "Marketing",      300_000, 29),
    ("e30", "Servicios contador externo",     "Servicios",      250_000, 30),
]

# Conciliaciones: (ingreso_key, venta_key, estado)
CONCILIACIONES: list[tuple] = [
    ("i1",  "v1",  "matcheado"),
    ("i2",  "v2",  "matcheado"),
    ("i3",  "v3",  "matcheado"),
    ("i4",  "v4",  "matcheado"),
    ("i5",  "v5",  "matcheado"),
    ("i6",  "v6",  "pendiente"),
    ("i7",  "v7",  "pendiente"),
    ("i8",  "v8",  "matcheado"),
    ("i9",  "v9",  "matcheado"),
    ("i10", "v10", "matcheado"),
    ("i11", None,  "personal"),
    ("i12", None,  "sin_match"),
    ("i13", "v13", "matcheado"),
    ("i14", "v14", "matcheado"),
    ("i15", "v15", "matcheado"),
    ("i16", "v16", "matcheado"),
    ("i17", "v17", "matcheado"),
    ("i18", "v18", "matcheado"),
    ("i19", "v19", "matcheado"),
    ("i20", "v20", "matcheado"),
    ("i21", "v21", "matcheado"),
    ("i22", "v22", "matcheado"),
    ("i23", "v23", "matcheado"),
    ("i24", "v24", "matcheado"),
    ("i25", "v25", "matcheado"),
    ("i26", "v26", "matcheado"),
    ("i27", None,  "pendiente"),
    ("i28", "v28", "matcheado"),
    ("i29", None,  "pendiente"),
    ("i30", "v33", "matcheado"),
    ("i31", "v34", "matcheado"),
    ("i32", "v35", "matcheado"),
    ("i33", "v36", "matcheado"),
    ("i34", "v37", "matcheado"),
    ("i35", "v38", "matcheado"),
    ("i36", "v39", "matcheado"),
    ("i37", "v40", "matcheado"),
    ("i38", None,  "sin_match"),
    ("i39", "v45", "matcheado"),
    ("i40", None,  "pendiente"),
]

SNAPSHOT = {
    "tipo_cliente": "INTERNO",
    "porcentaje_vendedor": "0.10",
    "porcentaje_cerrador": "0.05",
    "porcentaje_referido_maximo": "0.03",
    "porcentaje_capa_punto": "0.05",
}


def comision(valor: int, neto: int) -> dict[str, Dinero]:
    ganancia = valor - neto
    vend = dinero(round(ganancia * 0.40))
    cerr = dinero(round(ganancia * 0.20))
    ref  = dinero(0)
    pv   = dinero(round(ganancia * 0.05))
    ag   = dinero(ganancia) - vend - cerr - ref - pv
    return {"vendedor": vend, "cerrador": cerr, "referido": ref, "punto_de_venta": pv, "agencia": ag}  # noqa: E501


def main() -> None:
    settings = obtener_settings()
    engine = crear_engine(settings.database_url)
    sesion = crear_fabrica_sesiones(engine)

    with sesion() as session:
        # Clientes
        clientes: dict[str, uuid.UUID] = {}
        for key, nombre, *_ in VENTAS:
            cid = did(f"cliente:{nombre}")
            clientes[key] = cid
            if not session.get(ClienteModel, cid):
                session.add(ClienteModel(
                    id=cid, nombre=nombre, tipo="INTERNO",
                    telefono=None, hotel="Hotel Demo", numero_habitacion="101",
                ))

        session.flush()

        # Ventas + Comisiones
        for key, _, vendedor, cerrador, valor, neto, dia, adultos, tipo_cli, canal in VENTAS:
            vid = did(f"venta:{key}")
            if not session.get(VentaModel, vid):
                session.add(VentaModel(
                    id=vid,
                    valor_venta=dinero(valor),
                    neto=dinero(neto),
                    abono=None,
                    servicio_ids=[],
                    cliente_id=clientes[key],
                    tipo_cliente=tipo_cli,
                    fecha=date(AÑO, MES, dia),
                    adultos=adultos,
                    ninos=0,
                    estado="PROCESADA",
                    vendedor_nombre=vendedor,
                    cerrador_nombre=cerrador,
                    punto_de_venta_id=None,
                    referido_nombre=None,
                    canal_origen=canal,
                    # Slice B: demo sales keep ids NULL — name→id resolution is out of scope
                    vendedor_id=None,
                    cerrador_id=None,
                ))
            if not session.get(ComisionRegistradaModel, vid):
                com = comision(valor, neto)
                session.add(ComisionRegistradaModel(
                    venta_id=vid,
                    vendedor=com["vendedor"],
                    cerrador=com["cerrador"],
                    punto_de_venta=com["punto_de_venta"],
                    referido=com["referido"],
                    agencia=com["agencia"],
                    snapshot_json=SNAPSHOT,
                    fecha=date(AÑO, MES, dia),
                ))

        session.flush()

        # Ingresos
        for key, banco, monto, ref, dia, clasificado in INGRESOS:
            iid = did(f"ingreso:{key}")
            if not session.get(IngresoModel, iid):
                session.add(IngresoModel(
                    id=iid,
                    banco=banco,
                    monto=dinero(monto),
                    fecha=date(AÑO, MES, dia),
                    referencia=ref,
                    remitente="Demo Cliente",
                    clasificado=clasificado,
                    venta_id=None,
                    fecha_recibido=datetime(AÑO, MES, dia, 10, 0, tzinfo=UTC),
                ))

        session.flush()

        # Egresos
        for key, desc, cat, monto, dia in EGRESOS:
            eid = did(f"egreso:{key}")
            if not session.get(EgresoModel, eid):
                session.add(EgresoModel(
                    id=eid,
                    descripcion=desc,
                    monto=dinero(monto),
                    fecha=date(AÑO, MES, dia),
                    categoria=cat,
                    tipo="manual",
                    referencia=None,
                    fecha_recibido=None,
                ))

        session.flush()

        # Conciliaciones
        for ing_key, venta_key, estado in CONCILIACIONES:
            iid = did(f"ingreso:{ing_key}")
            vid = did(f"venta:{venta_key}") if venta_key else None
            cid = did(f"conciliacion:{ing_key}")
            if not session.get(ConciliacionModel, cid):
                session.add(ConciliacionModel(
                    id=cid,
                    ingreso_id=iid,
                    venta_id=vid,
                    estado=estado,
                    notas="",
                    score=Decimal("0.95") if estado == "matcheado" else Decimal("0.45"),
                    confianza=Decimal("0.95") if estado == "matcheado" else Decimal("0.45"),
                ))

        session.commit()
        print(
            f"[OK] Demo data insertada: "
            f"{len(VENTAS)} ventas · "
            f"{len(INGRESOS)} ingresos · "
            f"{len(EGRESOS)} egresos · "
            f"{len(CONCILIACIONES)} conciliaciones"
        )


if __name__ == "__main__":
    main()
