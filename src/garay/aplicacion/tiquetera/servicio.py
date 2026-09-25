"""RegistrarVentaService — application service for registering a sale."""

from __future__ import annotations

import datetime
import html
import logging
import uuid

from garay.aplicacion.comun.fechas import formatear_fechas_compactas
from garay.aplicacion.comun.formato import fmt_cop
from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando, ResultadoRegistrarVenta
from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    SocioConfigRepository,
    TiqueteraRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.dominio.servicios.horarios import render_horarios
from garay.dominio.socios.entidades import SocioConfig
from garay.dominio.socios.servicio import calcular_split_venta
from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

logger = logging.getLogger(__name__)



def _esc(v: object) -> str:
    """Escape a dynamic value for the group message (parse_mode=HTML).

    Telegram rejects malformed HTML with HTTP 400, so any user-provided text
    ('&', '<', '>' in client/tour/hotel/name) must be escaped before it goes
    into the message; the intentional <b> title tags stay literal.
    """
    return html.escape(str(v), quote=False)


def _render_fecha(cmd: RegistrarVentaComando) -> str:
    """Render the sale date line: scalar for one tour, compact per-tour otherwise."""
    if len(cmd.servicio_ids) > 1 and cmd.fechas_por_servicio:
        fecha_base = datetime.datetime.combine(cmd.fecha, datetime.time())
        pares = [
            (nombre, cmd.fechas_por_servicio.get(sid, fecha_base))
            for sid, nombre in zip(cmd.servicio_ids, cmd.servicio_nombres, strict=False)
        ]
        return formatear_fechas_compactas(pares)
    return cmd.fecha.strftime("%d/%m/%Y")


def _derivar_numero_personas(participantes: Participantes) -> int | None:
    """Derive the number of distinct people involved in a sale.

    Returns:
        1  — vendedor_id and cerrador_id are both non-None AND equal (same person).
        2  — vendedor_id and cerrador_id are both non-None AND different persons.
        None — either id is None; cannot determine count (design S2).
    """
    vid = participantes.vendedor_id
    cid = participantes.cerrador_id
    if vid is None or cid is None:
        return None
    return 1 if vid == cid else 2


def _construir_mensaje_privado(
    socio: SocioConfig,
    monto: Dinero,
    desglose: DesgloseComision,
    cmd: RegistrarVentaComando,
    split: dict[str, Dinero],
    socios: list[SocioConfig],
) -> str:
    """Build the private HTML split waterfall message for a socio.

    Shows the complete money waterfall for a single sale:
    destino/fecha → bruto → neto → ganancia → freelancer commissions
    (omitting zero roles) → agencia neta → every socio's share.
    """
    ganancia = cmd.valor_venta - cmd.neto
    agencia_neta = desglose.agencia
    snap = desglose.snapshot

    lineas: list[str] = ["💰 <b>Nueva venta — tu parte</b>", ""]

    if cmd.servicio_nombres:
        lineas.append(f"📍 Destino: {_esc(', '.join(cmd.servicio_nombres))}")

    lineas.append(f"📅 Fecha: {_render_fecha(cmd)}")
    lineas.append("")

    lineas.append(f"💵 Bruto: {fmt_cop(cmd.valor_venta)}")
    lineas.append(f"🏭 Neto operador: {fmt_cop(cmd.neto)}")
    lineas.append(f"📈 Ganancia: {fmt_cop(ganancia)}")

    # Freelancer commissions — omit roles whose amount is zero
    lineas.append("")
    if desglose.vendedor.monto > 0:
        vendedor_nombre = cmd.participantes.vendedor_nombre or "—"
        lineas.append(
            f"👤 Vendedor — {_esc(vendedor_nombre)} ({snap.porcentaje_vendedor}%): {fmt_cop(desglose.vendedor)}"
        )
    if desglose.cerrador.monto > 0:
        cerrador_nombre = cmd.participantes.cerrador_nombre or "—"
        lineas.append(
            f"🔑 Cerrador — {_esc(cerrador_nombre)} ({snap.porcentaje_cerrador}%): {fmt_cop(desglose.cerrador)}"
        )
    if desglose.punto_de_venta.monto > 0:
        pct_punto = snap.porcentaje_capa_punto
        lineas.append(
            f"🏪 Punto de venta ({pct_punto}%): {fmt_cop(desglose.punto_de_venta)}"
        )

    lineas.append(f"🏢 Agencia neta: {fmt_cop(agencia_neta)}")

    # All socios' shares — every socio sees every other socio's cut
    lineas.append("")
    for s in socios:
        cantidad = split.get(s.nombre, Dinero(0))
        lineas.append(
            f"   📊 {_esc(s.nombre)} ({s.porcentaje}%): {fmt_cop(cantidad)}"
        )

    lineas.append("")
    lineas.append(f"✅ Tu parte: {fmt_cop(monto)}")

    return "\n".join(lineas)


class RegistrarVentaService:
    """Orchestrates sale registration: creates the aggregate, calculates
    commissions, persists, optionally creates a tiquetera, and notifies."""

    def __init__(
        self,
        ventas: VentaRepository,
        reglas_repo: ReglasComisionRepository,
        tiqueteras: TiqueteraRepository,
        puntos_repo: PuntoDeVentaRepository,
        motor: MotorComisiones,
        notificador: NotificadorGrupo,
        grupo_id: str,
        comisiones_repo: ComisionRegistradaRepository,
        socios_config: SocioConfigRepository,
    ) -> None:
        self._ventas = ventas
        self._reglas_repo = reglas_repo
        self._tiqueteras = tiqueteras
        self._puntos_repo = puntos_repo
        self._motor = motor
        self._notificador = notificador
        self._grupo_id = grupo_id
        self._comisiones_repo = comisiones_repo
        self._socios_config = socios_config

    def ejecutar(self, cmd: RegistrarVentaComando) -> ResultadoRegistrarVenta:
        # 1. Create the Venta aggregate
        venta = Venta(
            id=uuid.uuid4(),
            valor_venta=cmd.valor_venta,
            neto=cmd.neto,
            servicio_ids=cmd.servicio_ids,
            cliente_id=cmd.cliente_id,
            tipo_cliente=cmd.tipo_cliente,
            fecha=cmd.fecha,
            participantes=cmd.participantes,
            adultos=cmd.adultos,
            ninos=cmd.ninos,
            abono=cmd.abono,
            canal_origen=cmd.canal_origen,
            fechas_por_servicio=cmd.fechas_por_servicio,
            horarios_por_servicio=cmd.horarios_por_servicio,
            factura_idioma=cmd.factura_idioma,
            registrado_en=datetime.datetime.now(datetime.UTC),
            metodo_pago=cmd.metodo_pago,
        )

        # 2. Resolve punto de venta FIRST — needed to determine if Crespo (design S1).
        punto = None
        if cmd.participantes.punto_de_venta_id is not None:
            punto = self._puntos_repo.buscar_por_id(cmd.participantes.punto_de_venta_id)

        # 3. Gate: point-specific lookup is only applicable for the Crespo punto (design S1).
        #    For every other punto the service falls through to the global rule by passing
        #    None/None, which triggers step-2 in buscar_regla (global tipo_cliente lookup).
        es_crespo = punto is not None and punto.nombre == "Crespo"
        lookup_punto = punto.nombre if (es_crespo and punto is not None) else None
        lookup_personas = _derivar_numero_personas(cmd.participantes) if es_crespo else None

        # 4. Fetch commission rules via two-step selector — raise if not found (design S3).
        reglas = self._reglas_repo.buscar_regla(
            cmd.tipo_cliente,
            lookup_punto,
            lookup_personas,
        )
        if reglas is None:
            raise ReglasComisionNoEncontradas(
                f"No se encontraron reglas de comision para tipo={cmd.tipo_cliente!r}, "
                f"punto={lookup_punto!r}, personas={lookup_personas!r}"
            )

        # 5. Calculate commission breakdown
        desglose = self._motor.calcular(venta, reglas, punto, cmd.porcentaje_referido)

        # 6. Persist the sale
        self._ventas.guardar(venta)

        # 6b. Persist commission record
        comision = ComisionRegistrada(
            venta_id=venta.id,
            desglose=desglose,
            fecha=venta.fecha,
        )
        self._comisiones_repo.guardar(comision)

        # 7. Create tiquetera if a reference photo was provided
        if cmd.foto_referencia is not None:
            tiquetera = Tiquetera(
                id=uuid.uuid4(),
                venta_id=venta.id,
                foto_referencia=cmd.foto_referencia,
                numero_fisico=cmd.numero_fisico,
                procesada=False,
            )
            self._tiqueteras.guardar(tiquetera)

        # 8. Notify the group
        vendedor = _esc(cmd.participantes.vendedor_nombre or "—")
        cerrador = _esc(cmd.participantes.cerrador_nombre or "—")

        lineas: list[str] = ["🎉 <b>Nueva venta registrada</b>", "Agencia Garay Tours", ""]

        if cmd.servicio_nombres:
            lineas.append(f"📍 Destino: {_esc(', '.join(cmd.servicio_nombres))}")

        lineas.append(f"📅 Fecha: {_render_fecha(cmd)}")

        horario_pares = list(
            zip(
                cmd.servicio_nombres,
                [(cmd.horarios_por_servicio or {}).get(sid, "") for sid in cmd.servicio_ids],
                strict=False,
            )
        )
        horario_grupo = render_horarios(horario_pares)
        if horario_grupo:
            lineas.append(f"⏰ Horario: {horario_grupo}")

        if cmd.cliente_nombre:
            lineas.append(f"👤 Cliente: {_esc(cmd.cliente_nombre)}")

        if cmd.cliente_telefono:
            lineas.append(f"📞 Teléfono: {_esc(cmd.cliente_telefono)}")

        if cmd.cliente_email:
            lineas.append(f"📧 Correo: {_esc(cmd.cliente_email)}")

        if cmd.hotel:
            hotel_line = f"🏨 Hotel: {_esc(cmd.hotel)}"
            if cmd.habitacion:
                hotel_line += f" | Hab: {_esc(cmd.habitacion)}"
            lineas.append(hotel_line)

        if cmd.ninos > 0:
            suffix = "s" if cmd.ninos != 1 else ""
            lineas.append(f"👥 Pax: {cmd.adultos} adultos / {cmd.ninos} niño{suffix}")
        else:
            lineas.append(f"👥 Pax: {cmd.adultos} adultos")

        valor_line = f"💰 Valor: {fmt_cop(cmd.valor_venta)}"
        if cmd.abono is not None:
            valor_line += f" | Abono: {fmt_cop(cmd.abono)}"
        lineas.append(valor_line)

        saldo_pendiente = (
            cmd.valor_venta - cmd.abono if cmd.abono is not None else cmd.valor_venta
        )
        lineas.append(f"🧾 Saldo pendiente: {fmt_cop(saldo_pendiente)}")

        if cmd.numero_fisico:
            lineas.append(f"🎫 Ticket: {_esc(cmd.numero_fisico)}")

        lineas.append(f"🏷 Tipo: {cmd.tipo_cliente.value}")
        if cmd.canal_origen:
            lineas.append(f"📲 Canal: {_esc(cmd.canal_origen)}")
        if cmd.metodo_pago is not None:
            lineas.append(f"💳 Pago: {cmd.metodo_pago.value}")
        lineas.append("")
        lineas.append("Comisiones:")
        lineas.append(f"  Agencia: {fmt_cop(desglose.agencia)}")

        if vendedor == cerrador:
            comision_total = fmt_cop(desglose.vendedor + desglose.cerrador)
            lineas.append(f"  {vendedor}: {comision_total}")
        else:
            lineas.append(f"  Vendedor ({vendedor}): {fmt_cop(desglose.vendedor)}")
            lineas.append(f"  Cerrador ({cerrador}): {fmt_cop(desglose.cerrador)}")

        mensaje = "\n".join(lineas)
        # Best-effort: la notificación al grupo NUNCA debe tumbar la venta (ya se
        # commiteó arriba). Si el grupo falla, se registra y se sigue con la factura.
        # Capture the returned message_id (int | None) so it can be persisted on the
        # venta for future delete-and-replace edit notifications.
        try:
            grupo_message_id = self._notificador.notificar(mensaje, self._grupo_id)
            if grupo_message_id is not None:
                venta.mensaje_grupo_id = grupo_message_id
                self._ventas.guardar(venta)
        except Exception:
            logger.exception(
                "No se pudo notificar la venta %s al grupo (la venta ya quedó registrada)",
                venta.id,
            )

        # 9. Send private split waterfall message to each socio with telegram_id (best-effort)
        socios = self._socios_config.listar()
        if socios:
            split = calcular_split_venta(desglose.agencia, socios)
            for socio in socios:
                if socio.telegram_id is None:
                    continue
                monto_socio = split.get(socio.nombre, Dinero(0))
                msg_privado = _construir_mensaje_privado(
                    socio=socio,
                    monto=monto_socio,
                    desglose=desglose,
                    cmd=cmd,
                    split=split,
                    socios=socios,
                )
                try:
                    self._notificador.notificar(msg_privado, str(socio.telegram_id))
                except Exception:
                    logger.exception(
                        "No se pudo enviar DM de split al socio %s (venta %s ya registrada)",
                        socio.nombre,
                        venta.id,
                    )

        return ResultadoRegistrarVenta(venta_id=venta.id, desglose=desglose)
