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
            f'<tr><td style="color:#777;padding-bottom:3px;">Horario</td>'
            f'<td style="text-align:right;font-weight:bold;">{horario_tour}</td></tr>'
            if horario_tour
            else ""
        )

        logo_html = (
            f'<img src="{self._logo_url}" alt="Garay Tours" style="height:70px;max-width:200px;">'
            if self._logo_url
            else '<span style="font-size:22px;font-weight:bold;color:#1B3B6B;">GARAY TOURS</span>'
        )

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Factura {numero_final}</title>
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
            <div style="font-size:11px;color:#555;margin-top:6px;">AGENCIA TURÍSTICA</div>
          </td>
          <td style="text-align:right;vertical-align:top;">
            <div style="font-size:22px;font-weight:bold;color:#1B3B6B;">FACTURA DE SERVICIO</div>
            <div style="font-size:13px;color:#555;margin-top:4px;">N° {numero_final}</div>
            <div style="font-size:12px;color:#777;margin-top:2px;">Fecha: {fecha_emision}</div>
          </td>
        </tr>
      </table>

      <!-- Company info bar -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#1B3B6B;border-radius:4px;">
        <tr>
          <td style="padding:10px 14px;color:#fff;font-size:11px;line-height:1.7;">
            <strong>GARAY TOURS — AGENCIA TURÍSTICA</strong><br>
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
              <div style="font-size:11px;font-weight:bold;color:#1B3B6B;text-transform:uppercase;margin-bottom:8px;">Cliente</div>
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
              <div style="font-size:11px;font-weight:bold;color:#1B3B6B;text-transform:uppercase;margin-bottom:8px;">Detalle del servicio</div>
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;">
                <tr><td style="color:#777;padding-bottom:3px;">Tour</td><td style="text-align:right;font-weight:bold;">{", ".join(ctx.destinos_nombres) if ctx.destinos_nombres else "—"}</td></tr>
                <tr><td style="color:#777;padding-bottom:3px;">Fecha del tour</td><td style="text-align:right;font-weight:bold;">{fecha_tour}</td></tr>
                {fila_horario}
                <tr><td style="color:#777;padding-bottom:3px;">Adultos</td><td style="text-align:right;">{ctx.adultos or 0}</td></tr>
                <tr><td style="color:#777;padding-bottom:3px;">Niños</td><td style="text-align:right;">{ctx.ninos or 0}</td></tr>
                <tr><td style="color:#777;">Hotel</td><td style="text-align:right;">{"Sin hotel" if ctx.sin_hotel else (ctx.cliente_hotel or "—")}</td></tr>
              </table>
            </div>
          </td>
        </tr>
      </table>

      <!-- Financial summary -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;border:1px solid #e0e4ea;border-radius:4px;border-collapse:collapse;">
        <tr style="background:#1B3B6B;color:#fff;">
          <th style="padding:10px 14px;text-align:left;font-size:12px;font-weight:bold;">Concepto</th>
          <th style="padding:10px 14px;text-align:right;font-size:12px;font-weight:bold;">Monto</th>
        </tr>
        <tr style="border-bottom:1px solid #e0e4ea;">
          <td style="padding:10px 14px;font-size:13px;">Valor total del servicio</td>
          <td style="padding:10px 14px;text-align:right;font-size:13px;">{_fmt_cop(ctx.valor)}</td>
        </tr>
        <tr style="border-bottom:1px solid #e0e4ea;">
          <td style="padding:10px 14px;font-size:13px;color:#555;">Abono / anticipo</td>
          <td style="padding:10px 14px;text-align:right;font-size:13px;color:#555;">{_fmt_cop(ctx.abono)}</td>
        </tr>
        <tr style="background:#f5f7fa;">
          <td style="padding:12px 14px;font-size:14px;font-weight:bold;color:#1B3B6B;">Saldo pendiente</td>
          <td style="padding:12px 14px;text-align:right;font-size:16px;font-weight:bold;color:#1B3B6B;">{_fmt_cop(saldo)}</td>
        </tr>
      </table>

      <!-- Payment methods -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;">
        <tr>
          <td style="padding:12px 14px;font-size:12px;line-height:1.8;">
            <strong style="color:#1B3B6B;">Medios de pago:</strong><br>
            🏦 Bancolombia cta. ahorro: <strong>085-043956-43</strong><br>
            🔑 Bancolombia llave BRE-B: <strong>@garay58804</strong><br>
            <span style="color:#555;font-size:11px;">Referencia: número de factura {numero_final}</span>
          </td>
        </tr>
      </table>

      <div style="margin-top:16px;font-size:10px;color:#aaa;text-align:center;padding-bottom:24px;">
        Gracias por elegir Garay Tours. Este documento es una factura de servicio emitida conforme a la ley colombiana.
      </div>
    </td>
  </tr>
</table>

<!-- PAGE 2: CANCELLATION POLICIES -->
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:700px;margin:0 auto;border-collapse:collapse;page-break-before:always;">
  <tr>
    <td style="padding:24px;">
      <div style="background:#1B3B6B;color:#fff;padding:14px 18px;border-radius:4px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:bold;">POLÍTICAS DE CANCELACIÓN Y CONDICIONES</div>
        <div style="font-size:11px;margin-top:4px;color:#b0c4de;">GARAY TOURS — AGENCIA TURÍSTICA · NIT: 1128049588-6</div>
      </div>

      <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;line-height:1.7;color:#333;">
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">1. CONFIRMACIÓN DE RESERVA</strong><br>
          Todas las reservas se confirman únicamente al recibir el pago del anticipo o el valor total del servicio.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">2. CANCELACIONES</strong><br>
          Las cancelaciones deben solicitarse por escrito a través de nuestros canales oficiales. Cuando aplique reembolso, estará sujeto a cargos administrativos y las políticas de cancelación de nuestros operadores aliados.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">3. CARGOS ADMINISTRATIVOS</strong><br>
          Garay Tours podrá deducir hasta el 35% del monto pagado, correspondiente a los costos administrativos, operativos y logísticos efectivamente incurridos en la gestión de la reserva.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">4. REPROGRAMACIÓN</strong><br>
          Las solicitudes de reprogramación deben realizarse con al menos 24 horas de anticipación y están sujetas a disponibilidad y condiciones del operador turístico.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">5. PLANES PROMOCIONALES</strong><br>
          Los planes promocionales, descuentos especiales, servicios de cortesía y tiquetes promocionales no son reembolsables. Cuando sea posible, podrán reprogramarse o cambiarse por un servicio de valor similar.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">6. NO SHOW</strong><br>
          La inasistencia a la hora establecida o el abandono voluntario del servicio implicará la pérdida del derecho a reembolso.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">7. FUERZA MAYOR / FORCE MAJEURE O CIRCUNSTANCIAS IMPREVISTAS</strong><br>
          Garay Tours podrá modificar, reprogramar o cancelar uno o más servicios turísticos cuando se presenten casos de fuerza mayor o circunstancias imprevistas que afecten las operaciones o pongan en riesgo la salud y seguridad de los clientes.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">8. OPERADORES ALIADOS</strong><br>
          Garay Tours actúa como agencia intermediaria, por lo que algunas condiciones de cancelación y reembolso dependen de las políticas de nuestros operadores turísticos aliados.
        </td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #eee;">
          <strong style="color:#1B3B6B;">9. OTRAS CONSIDERACIONES</strong><br>
          Garay Tours podrá solicitar soporte para contratación, cotizaciones, comprobantes de pago, conversaciones, correos electrónicos, mensajes y demás pruebas permitidas por la ley colombiana.
        </td></tr>
        <tr><td style="padding:10px 0;">
          <div style="background:#f5f7fa;border-left:4px solid #1B3B6B;padding:10px 12px;font-size:11px;color:#555;line-height:1.6;">
            <strong>ACEPTACIÓN DE CONDICIONES:</strong> Al realizar el pago total o parcial (anticipo), el cliente declara haber leído, comprendido y aceptado estas políticas y las condiciones del servicio contratado. Estas políticas se elaboran conforme a las leyes colombianas: Ley 300 de 1996 (Ley General de Turismo), Ley 1558 de 2012, Ley 1480 de 2011 (Estatuto del Consumidor), Decreto 1074 de 2015 y demás normas que las modifiquen o sustituyan.
          </div>
        </td></tr>
      </table>

      <div style="margin-top:16px;font-size:10px;color:#aaa;text-align:center;">
        Documento correspondiente a la factura N° {numero_final} emitido el {fecha_emision} — GARAY TOURS
      </div>
    </td>
  </tr>
</table>

</body>
</html>"""
