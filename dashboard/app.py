"""Garay Tours — Local Streamlit Dashboard.

Run with:
    uv run streamlit run dashboard/app.py
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import plotly.graph_objects as go
import streamlit as st

import garay.infraestructura.persistencia.tipos  # noqa: F401
from garay.aplicacion.reportes.flujo_caja import FlujoCaja, FlujoCajaService
from garay.aplicacion.reportes.resumen_ventas import ResumenCanal, ResumenVentas, ResumenVentasService
from garay.config.settings import obtener_settings
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.conciliaciones import (
    SQLAConciliacionRepository,
)
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

st.set_page_config(
    page_title="Garay Tours",
    page_icon="🌴",
    layout="wide",
)


@st.cache_resource
def _get_session_factory():
    settings = obtener_settings()
    engine = crear_engine(settings.database_url)
    return crear_fabrica_sesiones(engine)


def _cop(monto: Decimal) -> str:
    return f"${monto:,.0f}"


def _cop_k(monto: Decimal) -> str:
    if monto >= Decimal("1000000"):
        return f"${monto / Decimal('1000000'):.1f}M"
    if monto >= Decimal("1000"):
        return f"${monto / Decimal('1000'):.1f}K"
    return _cop(monto)


# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("🌴 Garay Tours")
st.sidebar.markdown("---")

hoy = date.today()
año_sel = st.sidebar.selectbox(
    "Año",
    options=list(range(hoy.year, hoy.year - 3, -1)),
    index=0,
)
mes_sel = st.sidebar.selectbox(
    "Mes",
    options=list(range(1, 13)),
    index=hoy.month - 1,
    format_func=lambda m: MESES[m],
)

pagina = st.sidebar.radio(
    "Vista",
    options=["Ventas", "Flujo de caja"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Período: {MESES[mes_sel]} {año_sel}")


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def cargar_ventas(mes: int, año: int) -> ResumenVentas:
    sf = _get_session_factory()
    servicio = ResumenVentasService(
        ventas=SQLAVentaRepository(sf),
        comisiones=SQLAComisionRegistradaRepository(sf),
    )
    return servicio.ejecutar(mes, año)


@st.cache_data(ttl=30)
def cargar_flujo(mes: int, año: int) -> FlujoCaja:
    sf = _get_session_factory()
    servicio = FlujoCajaService(
        ingresos=SQLAIngresoRepository(sf),
        egresos=SQLAEgresoRepository(sf),
        conciliaciones=SQLAConciliacionRepository(sf),
    )
    return servicio.ejecutar(mes, año)


# ── Pages ─────────────────────────────────────────────────────────────────────

def pagina_ventas(mes: int, año: int) -> None:
    st.title(f"📊 Ventas — {MESES[mes]} {año}")

    resumen = cargar_ventas(mes, año)

    if resumen.total_ventas == 0:
        st.info("No hay ventas registradas para este período.")
        return

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total ventas", resumen.total_ventas)
    c2.metric("Valor vendido", _cop(resumen.total_valor.monto))
    c3.metric("Ganancia agencia", _cop(resumen.ganancia_agencia.monto))
    c4.metric("Ticket promedio", _cop(resumen.total_valor.monto / Decimal(str(resumen.total_ventas))))

    if resumen.por_dia:
        st.markdown("---")
        st.subheader("Tendencia del mes")
        dias = [str(d.day).zfill(2) for d, _, _ in resumen.por_dia]
        conteos_dia = [cnt for _, cnt, _ in resumen.por_dia]
        fig_dia = go.Figure(go.Bar(
            x=dias,
            y=conteos_dia,
            marker_color="#4C9BE8",
            text=conteos_dia,
            textposition="outside",
        ))
        fig_dia.update_layout(
            xaxis_title="Día",
            yaxis_title="Ventas",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig_dia, use_container_width=True)

    st.markdown("---")

    vendedores = [v for v in resumen.por_vendedor if v.ventas > 0]
    if not vendedores:
        return

    nombres = [v.nombre for v in vendedores]
    valores = [float(v.valor_total.monto) for v in vendedores]
    comisiones = [float(v.comision.monto) for v in vendedores]
    conteos = [v.ventas for v in vendedores]

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("Ventas por vendedor")
        fig = go.Figure(go.Bar(
            x=nombres,
            y=conteos,
            marker_color="#4C9BE8",
            text=conteos,
            textposition="outside",
        ))
        fig.update_layout(
            yaxis_title="Cantidad de ventas",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.subheader("Valor vendido por vendedor (COP)")
        fig2 = go.Figure(go.Bar(
            x=nombres,
            y=valores,
            marker_color="#27AE60",
            text=[_cop(Decimal(str(v))) for v in valores],
            textposition="outside",
        ))
        fig2.update_layout(
            yaxis_title="COP",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Comisiones por vendedor (COP)")
    fig3 = go.Figure(go.Bar(
        x=nombres,
        y=comisiones,
        marker_color="#E67E22",
        text=[_cop(Decimal(str(c))) for c in comisiones],
        textposition="outside",
    ))
    fig3.update_layout(
        yaxis_title="COP",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")
    st.subheader("Detalle por vendedor")
    st.dataframe(
        {
            "Vendedor": nombres,
            "Ventas": conteos,
            "Valor total": [_cop(v.valor_total.monto) for v in vendedores],
            "Comisión": [_cop(v.comision.monto) for v in vendedores],
        },
        use_container_width=True,
        hide_index=True,
    )

    if resumen.por_canal:
        st.markdown("---")
        st.subheader("Ventas por canal (DIGITAL)")
        canales_nombres = [c.canal for c in resumen.por_canal]
        canales_conteos = [c.cantidad for c in resumen.por_canal]
        canales_valores = [float(c.valor_total.monto) for c in resumen.por_canal]

        col_canal_izq, col_canal_der = st.columns(2)

        with col_canal_izq:
            fig_canal = go.Figure(go.Bar(
                x=canales_nombres,
                y=canales_conteos,
                marker_color="#9B59B6",
                text=canales_conteos,
                textposition="outside",
            ))
            fig_canal.update_layout(
                yaxis_title="Cantidad de ventas",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig_canal, use_container_width=True)

        with col_canal_der:
            fig_canal_valor = go.Figure(go.Pie(
                labels=canales_nombres,
                values=canales_valores,
                hole=0.4,
                textinfo="label+percent",
            ))
            fig_canal_valor.update_layout(
                margin=dict(t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig_canal_valor, use_container_width=True)

        st.dataframe(
            {
                "Canal": canales_nombres,
                "Ventas": canales_conteos,
                "Valor total": [_cop(c.valor_total.monto) for c in resumen.por_canal],
            },
            use_container_width=True,
            hide_index=True,
        )


def pagina_flujo(mes: int, año: int) -> None:
    st.title(f"💵 Flujo de caja — {MESES[mes]} {año}")

    flujo = cargar_flujo(mes, año)

    if flujo.total_ingresos.monto == 0 and flujo.total_egresos.monto == 0:
        st.info("No hay movimientos registrados para este período.")
        return

    # KPIs
    balance_pos = flujo.balance.monto >= 0
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Ingresos", _cop_k(flujo.total_ingresos.monto))
    c2.metric("Egresos", _cop_k(flujo.total_egresos.monto))
    c3.metric(
        "Balance",
        _cop_k(abs(flujo.balance.monto)),
        delta=f"{'positivo' if balance_pos else 'negativo'}",
        delta_color="normal" if balance_pos else "inverse",
    )
    c4.metric("Ingresos conciliados", flujo.ingresos_conciliados)
    c5.metric("Pendientes / sin match", flujo.ingresos_pendientes)

    st.markdown("---")

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("Ingresos vs Egresos")
        fig = go.Figure(go.Bar(
            x=["Ingresos", "Egresos"],
            y=[float(flujo.total_ingresos.monto), float(flujo.total_egresos.monto)],
            marker_color=["#27AE60", "#E74C3C"],
            text=[
                _cop(flujo.total_ingresos.monto),
                _cop(flujo.total_egresos.monto),
            ],
            textposition="outside",
        ))
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        if flujo.egresos_por_categoria:
            st.subheader("Egresos por categoría")
            cats = [cat for cat, _ in flujo.egresos_por_categoria]
            montos = [float(m.monto) for _, m in flujo.egresos_por_categoria]
            fig2 = go.Figure(go.Pie(
                labels=cats,
                values=montos,
                hole=0.4,
                textinfo="label+percent",
            ))
            fig2.update_layout(
                margin=dict(t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)

    if flujo.egresos_por_categoria:
        st.markdown("---")
        st.subheader("Detalle de egresos")
        st.dataframe(
            {
                "Categoría": [cat for cat, _ in flujo.egresos_por_categoria],
                "Monto": [_cop(m.monto) for _, m in flujo.egresos_por_categoria],
            },
            use_container_width=True,
            hide_index=True,
        )

    if flujo.ingresos_por_banco:
        st.markdown("---")
        st.subheader("Ingresos por banco")
        col_banco_izq, col_banco_der = st.columns(2)
        with col_banco_izq:
            fig_banco = go.Figure(go.Bar(
                x=[r.banco for r in flujo.ingresos_por_banco],
                y=[float(r.monto_total.monto) for r in flujo.ingresos_por_banco],
                marker_color="#4C9BE8",
                text=[_cop(r.monto_total.monto) for r in flujo.ingresos_por_banco],
                textposition="outside",
            ))
            fig_banco.update_layout(
                yaxis_title="COP",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig_banco, use_container_width=True)
        with col_banco_der:
            st.dataframe(
                {
                    "Banco": [r.banco for r in flujo.ingresos_por_banco],
                    "Ingresos": [r.cantidad for r in flujo.ingresos_por_banco],
                    "Monto total": [_cop(r.monto_total.monto) for r in flujo.ingresos_por_banco],
                },
                use_container_width=True,
                hide_index=True,
            )

    if flujo.ingresos_por_estado:
        st.markdown("---")
        st.subheader("Estado de conciliación")
        etiquetas = {
            "matcheado": "✅ Matcheado",
            "pendiente": "⏳ Pendiente",
            "sin_match": "❌ Sin match",
            "personal": "👤 Personal",
        }
        st.dataframe(
            {
                "Estado": [etiquetas.get(r.estado, r.estado) for r in flujo.ingresos_por_estado],
                "Cantidad": [r.cantidad for r in flujo.ingresos_por_estado],
                "Monto total": [_cop(r.monto_total.monto) for r in flujo.ingresos_por_estado],
            },
            use_container_width=True,
            hide_index=True,
        )


# ── Router ────────────────────────────────────────────────────────────────────

if pagina == "Ventas":
    pagina_ventas(mes_sel, año_sel)
else:
    pagina_flujo(mes_sel, año_sel)
