"""GenerarFacturaService — builds a self-contained HTML invoice for Garay Tours."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

from garay.aplicacion.comun.fechas import formatear_fechas_compactas
from garay.dominio.servicios.horarios import render_horarios
from garay.dominio.ventas.contexto import ContextoVenta

_BOGOTA = ZoneInfo("America/Bogota")

# Cancellation policies as (heading, body) pairs, one list per language. The
# order is legally meaningful and must stay identical across languages.
_POLITICAS_ES: list[tuple[str, str]] = [
    (
        "1. CONFIRMACIÓN DE RESERVA",
        "Todas las reservas se confirman únicamente al recibir el pago del anticipo o el "
        "valor total del servicio.",
    ),
    (
        "2. CANCELACIONES",
        "Las cancelaciones deben solicitarse por escrito a través de nuestros canales "
        "oficiales. Cuando aplique reembolso, estará sujeto a cargos administrativos y las "
        "políticas de cancelación de nuestros operadores aliados.",
    ),
    (
        "3. CARGOS ADMINISTRATIVOS",
        "Garay Tours podrá deducir hasta el 35% del monto pagado, correspondiente a los "
        "costos administrativos, operativos y logísticos efectivamente incurridos en la "
        "gestión de la reserva.",
    ),
    (
        "4. REPROGRAMACIÓN",
        "Las solicitudes de reprogramación deben realizarse con al menos 72 horas de "
        "anticipación y están sujetas a disponibilidad y condiciones del operador turístico.",
    ),
    (
        "5. PLANES PROMOCIONALES",
        "Los planes promocionales, descuentos especiales, servicios de cortesía y tiquetes "
        "promocionales no son reembolsables. Cuando sea posible, podrán reprogramarse o "
        "cambiarse por un servicio de valor similar.",
    ),
    (
        "6. NO SHOW",
        "La inasistencia a la hora establecida o el abandono voluntario del servicio "
        "implicará la pérdida del derecho a reembolso.",
    ),
    (
        "7. FUERZA MAYOR / FORCE MAJEURE O CIRCUNSTANCIAS IMPREVISTAS",
        "Garay Tours podrá modificar, reprogramar o cancelar uno o más servicios turísticos "
        "cuando se presenten casos de fuerza mayor o circunstancias imprevistas que afecten "
        "las operaciones o pongan en riesgo la salud y seguridad de los clientes.",
    ),
    (
        "8. OPERADORES ALIADOS",
        "Garay Tours actúa como agencia intermediaria, por lo que algunas condiciones de "
        "cancelación y reembolso dependen de las políticas de nuestros operadores turísticos "
        "aliados.",
    ),
    (
        "9. OTRAS CONSIDERACIONES",
        "Garay Tours podrá solicitar soporte para contratación, cotizaciones, comprobantes "
        "de pago, conversaciones, correos electrónicos, mensajes y demás pruebas permitidas "
        "por la ley colombiana.",
    ),
]

_POLITICAS_EN: list[tuple[str, str]] = [
    (
        "1. BOOKING CONFIRMATION",
        "All bookings are confirmed only upon receipt of the deposit payment or the full "
        "value of the service.",
    ),
    (
        "2. CANCELLATIONS",
        "Cancellations must be requested in writing through our official channels. Where a "
        "refund applies, it will be subject to administrative charges and the cancellation "
        "policies of our partner operators.",
    ),
    (
        "3. ADMINISTRATIVE CHARGES",
        "Garay Tours may withhold up to 35% of the amount paid, corresponding to the "
        "administrative, operational and logistical costs actually incurred in managing the "
        "booking.",
    ),
    (
        "4. RESCHEDULING",
        "Rescheduling requests must be made at least 72 hours in advance and are subject to "
        "availability and the tour operator's conditions.",
    ),
    (
        "5. PROMOTIONAL PLANS",
        "Promotional plans, special discounts, complimentary services and promotional "
        "tickets are non-refundable. Where possible, they may be rescheduled or exchanged "
        "for a service of similar value.",
    ),
    (
        "6. NO SHOW",
        "Failure to attend at the established time or voluntary abandonment of the service "
        "will result in the loss of any right to a refund.",
    ),
    (
        "7. FORCE MAJEURE OR UNFORESEEN CIRCUMSTANCES",
        "Garay Tours may modify, reschedule or cancel one or more tourism services in cases "
        "of force majeure or unforeseen circumstances that affect operations or endanger the "
        "health and safety of clients.",
    ),
    (
        "8. PARTNER OPERATORS",
        "Garay Tours acts as an intermediary agency, so some cancellation and refund "
        "conditions depend on the policies of our partner tour operators.",
    ),
    (
        "9. OTHER CONSIDERATIONS",
        "Garay Tours may request supporting evidence for contracting, quotes, payment "
        "receipts, conversations, emails, messages and other proof permitted by Colombian "
        "law.",
    ),
]

_ACEPTACION_ES = (
    "<strong>ACEPTACIÓN DE CONDICIONES:</strong> Al realizar el pago total o parcial "
    "(anticipo), el cliente declara haber leído, comprendido y aceptado estas políticas y "
    "las condiciones del servicio contratado. Estas políticas se elaboran conforme a las "
    "leyes colombianas: Ley 300 de 1996 (Ley General de Turismo), Ley 1558 de 2012, Ley "
    "1480 de 2011 (Estatuto del Consumidor), Decreto 1074 de 2015 y demás normas que las "
    "modifiquen o sustituyan."
)

# English acceptance clause. Includes the language-precedence note: the Spanish
# version is the legally binding text, so a translated invoice does not weaken the
# policies under Colombian law.
_ACEPTACION_EN = (
    "<strong>ACCEPTANCE OF CONDITIONS:</strong> By making full or partial (deposit) "
    "payment, the client declares having read, understood and accepted these policies and "
    "the conditions of the contracted service. These policies are drafted under Colombian "
    "law: Law 300 of 1996 (General Tourism Law), Law 1558 of 2012, Law 1480 of 2011 "
    "(Consumer Statute), Decree 1074 of 2015 and any amending or superseding regulations. "
    "This English text is a courtesy translation; the Spanish version shall prevail for all "
    "legal purposes."
)

_TEXTOS: dict[str, dict[str, str]] = {
    "es": {
        "titulo_doc": "Factura",
        "agencia_sub": "AGENCIA TURÍSTICA",
        "titulo_factura": "FACTURA DE SERVICIO",
        "label_numero": "N°",
        "label_fecha": "Fecha",
        "empresa_encabezado": "GARAY TOURS — AGENCIA TURÍSTICA",
        "label_cliente": "Cliente",
        "label_detalle": "Detalle del servicio",
        "label_tour": "Tour",
        "label_fecha_tour": "Fecha del tour",
        "label_horario": "Horario",
        "label_adultos": "Adultos",
        "label_ninos": "Niños",
        "label_hotel": "Hotel",
        "sin_hotel": "Sin hotel",
        "label_concepto": "Concepto",
        "label_monto": "Monto",
        "concepto_valor": "Valor total del servicio",
        "concepto_abono": "Abono / anticipo",
        "concepto_saldo": "Saldo pendiente",
        "medios_pago": "Medios de pago:",
        "cta_ahorro": "Bancolombia cta. ahorro:",
        "llave": "Bancolombia llave BRE-B:",
        "referencia": "Referencia: número de factura",
        "footer_p1": (
            "Gracias por elegir Garay Tours. Este documento es una factura de servicio "
            "emitida conforme a la ley colombiana."
        ),
        "titulo_politicas": "POLÍTICAS DE CANCELACIÓN Y CONDICIONES",
        "politicas_sub": "GARAY TOURS — AGENCIA TURÍSTICA · NIT: 1128049588-6",
        "footer_politicas_1": "Documento correspondiente a la factura",
        "footer_politicas_2": "emitido el",
    },
    "en": {
        "titulo_doc": "Invoice",
        "agencia_sub": "TRAVEL AGENCY",
        "titulo_factura": "SERVICE INVOICE",
        "label_numero": "No.",
        "label_fecha": "Date",
        "empresa_encabezado": "GARAY TOURS — TRAVEL AGENCY",
        "label_cliente": "Client",
        "label_detalle": "Service details",
        "label_tour": "Tour",
        "label_fecha_tour": "Tour date",
        "label_horario": "Time",
        "label_adultos": "Adults",
        "label_ninos": "Children",
        "label_hotel": "Hotel",
        "sin_hotel": "No hotel",
        "label_concepto": "Description",
        "label_monto": "Amount",
        "concepto_valor": "Total service value",
        "concepto_abono": "Deposit / advance",
        "concepto_saldo": "Balance due",
        "medios_pago": "Payment methods:",
        "cta_ahorro": "Bancolombia savings acct.:",
        "llave": "Bancolombia BRE-B key:",
        "referencia": "Reference: invoice number",
        "footer_p1": (
            "Thank you for choosing Garay Tours. This document is a service invoice issued "
            "under Colombian law."
        ),
        "titulo_politicas": "CANCELLATION POLICIES AND CONDITIONS",
        "politicas_sub": "GARAY TOURS — TRAVEL AGENCY · NIT: 1128049588-6",
        "footer_politicas_1": "Document corresponding to invoice",
        "footer_politicas_2": "issued on",
    },
}


def _hoy_bogota() -> datetime.date:
    return datetime.datetime.now(_BOGOTA).date()


def _fmt_cop(valor: Decimal | None) -> str:
    """Format a Decimal as Colombian pesos. E.g.: 500000 → '$500.000'"""
    if valor is None:
        return "$0"
    return "$" + f"{int(valor):,}".replace(",", ".")


def _render_fecha_tour(ctx: ContextoVenta) -> str:
    """Render the tour-date cell: scalar for one tour, compact per-tour otherwise."""
    if ctx.fecha_salida is None:
        return "—"
    if len(ctx.destinos_numeros) > 1 and ctx.fechas_por_servicio:
        pares = [
            (nombre, ctx.fechas_por_servicio.get(numero, ctx.fecha_salida))
            for numero, nombre in zip(
                ctx.destinos_numeros, ctx.destinos_nombres, strict=False
            )
        ]
        return formatear_fechas_compactas(pares)
    return ctx.fecha_salida.strftime("%d/%m/%Y")


def _numero_factura(venta_id: uuid.UUID) -> str:
    hex_sin_guiones = str(venta_id).replace("-", "")
    codigo = hex_sin_guiones[:6].upper()
    fecha = _hoy_bogota().strftime("%Y%m%d")
    return f"GT-{fecha}-{codigo}"


class GenerarFacturaService:
    """Generates a 2-page HTML invoice: page 1 = invoice, page 2 = cancellation policies."""

    def __init__(self, logo_url: str = "") -> None:
        self._logo_url = logo_url

    def generar(self, ctx: ContextoVenta, venta_id: uuid.UUID, numero: str | None = None) -> str:
        idioma = ctx.factura_idioma if ctx.factura_idioma in ("es", "en") else "es"
        t = _TEXTOS[idioma]
        politicas = _POLITICAS_ES if idioma == "es" else _POLITICAS_EN
        aceptacion = _ACEPTACION_ES if idioma == "es" else _ACEPTACION_EN

        numero_final = numero if numero is not None else _numero_factura(venta_id)
        fecha_emision = _hoy_bogota().strftime("%d/%m/%Y")
        fecha_tour = _render_fecha_tour(ctx)
        saldo = (ctx.valor or Decimal("0")) - (ctx.abono or Decimal("0"))

        # Build horario row — conditional on whether any schedule is set
        horario_pares = list(
            zip(
                ctx.destinos_nombres,
                [ctx.horarios_por_servicio.get(n, "") for n in ctx.destinos_numeros],
                strict=False,
            )
        )
        horario_tour = render_horarios(horario_pares)
        fila_horario = (
            f'<tr><td style="color:#777;padding-bottom:3px;">{t["label_horario"]}</td>'
            f'<td style="text-align:right;font-weight:bold;">{horario_tour}</td></tr>'
            if horario_tour
            else ""
        )

        logo_html = (
            f'<img src="{self._logo_url}" alt="Garay Tours" style="height:70px;max-width:200px;">'
            if self._logo_url
            else '<span style="font-size:22px;font-weight:bold;color:#1B3B6B;">GARAY TOURS</span>'
        )

        filas_politicas = "".join(
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #eee;">'
            f'<strong style="color:#1B3B6B;">{encabezado}</strong><br>\n          {cuerpo}'
            f"</td></tr>"
            for encabezado, cuerpo in politicas
        )

        return f"""<!DOCTYPE html>
<html lang="{idioma}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t["titulo_doc"]} {numero_final}</title>
</head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;color:#333;background:#fff;">

<!-- PAGE 1: INVOICE -->
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:700px;margin:0 auto;border-collapse:collapse;">
  <tr>
    <td style="padding:24px 24px 0;">
      <!-- Header -->
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="vertical-align:middle;">
            {logo_html}
            <div style="font-size:11px;color:#555;margin-top:6px;">{t["agencia_sub"]}</div>
          </td>
          <td style="text-align:right;vertical-align:top;">
            <div style="font-size:22px;font-weight:bold;color:#1B3B6B;">{t["titulo_factura"]}</div>
            <div style="font-size:13px;color:#555;margin-top:4px;">{t["label_numero"]} {numero_final}</div>
            <div style="font-size:12px;color:#777;margin-top:2px;">{t["label_fecha"]}: {fecha_emision}</div>
          </td>
        </tr>
      </table>

      <!-- Company info bar -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#1B3B6B;border-radius:4px;">
        <tr>
          <td style="padding:10px 14px;color:#fff;font-size:11px;line-height:1.7;">
            <strong>{t["empresa_encabezado"]}</strong><br>
            NIT: 1128049588-6 &nbsp;|&nbsp; RNT: 157745<br>
            Hotel Marie Real, Calle del Boquete #7-156, Cartagena de Indias<br>
            Tel: +573223789349 &nbsp;|&nbsp; agenciagaraytour1@gmail.com
          </td>
        </tr>
      </table>

      <!-- Client info + Invoice details -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
        <tr>
          <td width="50%" style="vertical-align:top;padding-right:12px;">
            <div style="background:#f5f7fa;border:1px solid #e0e4ea;border-radius:4px;padding:12px;">
              <div style="font-size:11px;font-weight:bold;color:#1B3B6B;text-transform:uppercase;margin-bottom:8px;">{t["label_cliente"]}</div>
              <div style="font-size:13px;font-weight:bold;">{ctx.cliente_nombre or "—"}</div>
              <div style="font-size:12px;color:#555;margin-top:4px;">
                {ctx.cliente_tipo_identificacion or "CC"}: {ctx.cliente_identificacion or "—"}<br>
                Tel: {ctx.cliente_telefono or "—"}<br>
                Email: {ctx.cliente_email or "—"}
              </div>
            </div>
          </td>
          <td width="50%" style="vertical-align:top;padding-left:12px;">
            <div style="background:#f5f7fa;border:1px solid #e0e4ea;border-radius:4px;padding:12px;">
              <div style="font-size:11px;font-weight:bold;color:#1B3B6B;text-transform:uppercase;margin-bottom:8px;">{t["label_detalle"]}</div>
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;">
                <tr><td style="color:#777;padding-bottom:3px;">{t["label_tour"]}</td><td style="text-align:right;font-weight:bold;">{", ".join(ctx.destinos_nombres) if ctx.destinos_nombres else "—"}</td></tr>
                <tr><td style="color:#777;padding-bottom:3px;">{t["label_fecha_tour"]}</td><td style="text-align:right;font-weight:bold;">{fecha_tour}</td></tr>
                {fila_horario}
                <tr><td style="color:#777;padding-bottom:3px;">{t["label_adultos"]}</td><td style="text-align:right;">{ctx.adultos or 0}</td></tr>
                <tr><td style="color:#777;padding-bottom:3px;">{t["label_ninos"]}</td><td style="text-align:right;">{ctx.ninos or 0}</td></tr>
                <tr><td style="color:#777;">{t["label_hotel"]}</td><td style="text-align:right;">{t["sin_hotel"] if ctx.sin_hotel else (ctx.cliente_hotel or "—")}</td></tr>
              </table>
            </div>
          </td>
        </tr>
      </table>

      <!-- Financial summary -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;border:1px solid #e0e4ea;border-radius:4px;border-collapse:collapse;">
        <tr style="background:#1B3B6B;color:#fff;">
          <th style="padding:10px 14px;text-align:left;font-size:12px;font-weight:bold;">{t["label_concepto"]}</th>
          <th style="padding:10px 14px;text-align:right;font-size:12px;font-weight:bold;">{t["label_monto"]}</th>
        </tr>
        <tr style="border-bottom:1px solid #e0e4ea;">
          <td style="padding:10px 14px;font-size:13px;">{t["concepto_valor"]}</td>
          <td style="padding:10px 14px;text-align:right;font-size:13px;">{_fmt_cop(ctx.valor)}</td>
        </tr>
        <tr style="border-bottom:1px solid #e0e4ea;">
          <td style="padding:10px 14px;font-size:13px;color:#555;">{t["concepto_abono"]}</td>
          <td style="padding:10px 14px;text-align:right;font-size:13px;color:#555;">{_fmt_cop(ctx.abono)}</td>
        </tr>
        <tr style="background:#f5f7fa;">
          <td style="padding:12px 14px;font-size:14px;font-weight:bold;color:#1B3B6B;">{t["concepto_saldo"]}</td>
          <td style="padding:12px 14px;text-align:right;font-size:16px;font-weight:bold;color:#1B3B6B;">{_fmt_cop(saldo)}</td>
        </tr>
      </table>

      <!-- Payment methods -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;">
        <tr>
          <td style="padding:12px 14px;font-size:12px;line-height:1.8;">
            <strong style="color:#1B3B6B;">{t["medios_pago"]}</strong><br>
            🏦 {t["cta_ahorro"]} <strong>085-043956-43</strong><br>
            🔑 {t["llave"]} <strong>@garay58804</strong><br>
            <span style="color:#555;font-size:11px;">{t["referencia"]} {numero_final}</span>
          </td>
        </tr>
      </table>

      <div style="margin-top:16px;font-size:10px;color:#aaa;text-align:center;padding-bottom:24px;">
        {t["footer_p1"]}
      </div>
    </td>
  </tr>
</table>

<!-- PAGE 2: CANCELLATION POLICIES -->
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:700px;margin:0 auto;border-collapse:collapse;page-break-before:always;">
  <tr>
    <td style="padding:24px;">
      <div style="background:#1B3B6B;color:#fff;padding:14px 18px;border-radius:4px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:bold;">{t["titulo_politicas"]}</div>
        <div style="font-size:11px;margin-top:4px;color:#b0c4de;">{t["politicas_sub"]}</div>
      </div>

      <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;line-height:1.7;color:#333;">
        {filas_politicas}
        <tr><td style="padding:10px 0;">
          <div style="background:#f5f7fa;border-left:4px solid #1B3B6B;padding:10px 12px;font-size:11px;color:#555;line-height:1.6;">
            {aceptacion}
          </div>
        </td></tr>
      </table>

      <div style="margin-top:16px;font-size:10px;color:#aaa;text-align:center;">
        {t["footer_politicas_1"]} {t["label_numero"]} {numero_final} {t["footer_politicas_2"]} {fecha_emision} — GARAY TOURS
      </div>
    </td>
  </tr>
</table>

</body>
</html>"""
