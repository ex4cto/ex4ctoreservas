"""Importa las ventas historicas de la planilla de contabilidad al modelo de dominio.

Escribe cada fila (ya deduplicada por el lector) como una `Venta` + su
`ComisionRegistrada`, resolviendo los FKs (cliente, servicio via alias, punto de
venta). NO reusa `RegistrarVentaService`: la comision se SNAPSHOTEA de la planilla
(no se recalcula), no notifica, y usa `uuid5` determinista para ser idempotente.

Crespo presencial rows: commission is derived via buscar_regla + motor.calcular
(same path as the live bot flow, for REQ-07 parity). Commission base is
venta.ganancia = valor - neto.

Hotel/Externas rows: commission is snapshotted from the spreadsheet residual
(historical behavior preserved).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from garay.aplicacion.importacion.errores import (
    DescripcionSinMapeo,
    ImportacionConNombresNoResueltos,
    PuntoCrespoNoConfigurado,
    VentaCrespoSinParticipantes,
)
from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    ComisionRegistradaRepository,
    FreelancerRepository,
    PuntoDeVentaRepository,
    ReglasComisionRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import FilaVentaImportada, LectorVentasExcel
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_NS = uuid.UUID("f0e1d2c3-b4a5-6789-abcd-ef0123456789")
_CERO = Dinero(0)
_CANAL_HOTEL = "Hotel"
_CANAL_CRESPO = "Crespo"


@dataclass(frozen=True)
class ResultadoImportacion:
    ventas_creadas: int
    clientes_creados: int
    ventas_omitidas: int
    total_valor: Dinero
    total_agencia: Dinero


def _norm_desc(descripcion: str) -> str:
    return " ".join(descripcion.strip().lower().split())


def _tipo_cliente(canal: str) -> TipoCliente:
    return TipoCliente.INTERNO if canal == _CANAL_HOTEL else TipoCliente.EXTERNO


class ImportarVentasExcelService:
    def __init__(
        self,
        lector: LectorVentasExcel,
        ventas: VentaRepository,
        clientes: ClienteRepository,
        servicios: ServicioRepository,
        puntos: PuntoDeVentaRepository,
        comisiones: ComisionRegistradaRepository,
        alias: dict[str, int],
        freelancer_repo: FreelancerRepository,
        *,
        reglas_repo: ReglasComisionRepository,
        motor: MotorComisiones,
    ) -> None:
        self._lector = lector
        self._ventas = ventas
        self._clientes = clientes
        self._servicios = servicios
        self._puntos = puntos
        self._comisiones = comisiones
        self._alias = alias
        self._freelancers = freelancer_repo
        self._reglas_repo = reglas_repo
        self._motor = motor

    def ejecutar(self, ruta: str, mes: int, anio: int) -> ResultadoImportacion:
        filas = [
            f
            for f in self._lector.leer(ruta)
            if f.fecha.month == mes and f.fecha.year == anio
        ]
        servicios_por_numero = {s.numero: s for s in self._servicios.listar()}
        punto_crespo = self._puntos.buscar_por_nombre(_CANAL_CRESPO)
        punto_crespo_id = punto_crespo.id if punto_crespo is not None else None

        # FIX-C: If the batch has any Crespo rows, the Crespo punto must be seeded.
        # Without it, motor.calcular receives None and silently zeroes the 20% capa,
        # corrupting every Crespo commission for the run.  Fail loudly before persistence.
        tiene_crespo = any(
            f.canal == _CANAL_CRESPO
            for f in filas
            if f.valor > _CERO and f.neto <= f.valor
        )
        if tiene_crespo and punto_crespo is None:
            raise PuntoCrespoNoConfigurado()

        # PASS 1: resolve all participant names; abort before any persistence on failure.
        no_encontrados: list[tuple[int, str]] = []
        ambiguos: list[tuple[int, str]] = []
        crespo_sin_participantes: list[int] = []
        resoluciones: dict[int, tuple[uuid.UUID | None, uuid.UUID | None]] = {}
        omitidas_pass1 = 0
        for i, f in enumerate(filas):
            if f.valor <= _CERO or f.neto > f.valor:
                omitidas_pass1 += 1
                continue
            fila_num = i + 1
            vendedor_id, vendedor_err = self._resolver_freelancer_id(f.vendedor_nombre)
            cerrador_id, cerrador_err = self._resolver_freelancer_id(f.cerrador_nombre)
            if vendedor_err == "no_encontrado":
                no_encontrados.append((fila_num, f.vendedor_nombre))  # type: ignore[arg-type]
            elif vendedor_err == "ambiguo":
                ambiguos.append((fila_num, f.vendedor_nombre))  # type: ignore[arg-type]
            if cerrador_err == "no_encontrado":
                no_encontrados.append((fila_num, f.cerrador_nombre))  # type: ignore[arg-type]
            elif cerrador_err == "ambiguo":
                ambiguos.append((fila_num, f.cerrador_nombre))  # type: ignore[arg-type]
            resoluciones[i] = (vendedor_id, cerrador_id)

            # FIX-B: Crespo rows need both vendedor_id and cerrador_id resolved so
            # _derivar_numero_personas can return 1 or 2.  A blank name on a Crespo
            # row means numero_personas is None, which makes buscar_regla raise a
            # raw ValueError from the C3 guard.  Detect this in PASS 1 (before any
            # persistence) and collect all offending rows for a descriptive domain error.
            if f.canal == _CANAL_CRESPO and (vendedor_id is None or cerrador_id is None):
                crespo_sin_participantes.append(fila_num)

        if no_encontrados or ambiguos:
            raise ImportacionConNombresNoResueltos(no_encontrados, ambiguos)

        if crespo_sin_participantes:
            raise VentaCrespoSinParticipantes(crespo_sin_participantes)

        # PASS 2: persist — only reached when all names are resolved.
        clientes_creados = 0
        omitidas = 0
        total_valor = _CERO
        total_agencia = _CERO
        for i, f in enumerate(filas):
            if f.valor <= _CERO or f.neto > f.valor:
                omitidas += 1
                continue
            vendedor_id, cerrador_id = resoluciones[i]
            servicio_id = self._resolver_servicio(f.descripcion, servicios_por_numero)
            cliente_id, creado = self._resolver_cliente(f)
            if creado:
                clientes_creados += 1
            punto_id = punto_crespo_id if f.canal == _CANAL_CRESPO else None

            venta = Venta(
                id=self._venta_id(f),
                valor_venta=f.valor,
                neto=f.neto,
                servicio_ids=[servicio_id],
                cliente_id=cliente_id,
                tipo_cliente=_tipo_cliente(f.canal),
                fecha=f.fecha,
                participantes=Participantes(
                    vendedor_nombre=f.vendedor_nombre,
                    cerrador_nombre=f.cerrador_nombre,
                    punto_de_venta_id=punto_id,
                    referido_nombre=None,
                    vendedor_id=vendedor_id,
                    cerrador_id=cerrador_id,
                ),
                estado=EstadoVenta.PROCESADA,
                canal_origen=f.canal,
            )
            # FIX-A: Compute desglose BEFORE persisting the venta.
            # SQLAVentaRepository.guardar commits immediately (uses `with sf.begin()`).
            # If _desglose raises (e.g. buscar_regla returns None for a missing rule),
            # the Venta would be orphaned with no ComisionRegistrada.  Computing first
            # ensures a raise leaves nothing persisted for that row.
            desglose = self._desglose(f, venta, punto_crespo)
            self._ventas.guardar(venta)
            self._comisiones.guardar(
                ComisionRegistrada(venta_id=venta.id, desglose=desglose, fecha=f.fecha)
            )
            total_valor = total_valor + f.valor
            # NOTE: total_agencia is a mixed-basis total — motor-derived for Crespo rows
            # (desglose.agencia = ganancia residual after capa + vendedor + cerrador),
            # spreadsheet-derived for all other rows (Hotel, Externas, etc.) — REQ-07.
            total_agencia = total_agencia + desglose.agencia

        return ResultadoImportacion(
            ventas_creadas=len(filas) - omitidas,
            clientes_creados=clientes_creados,
            ventas_omitidas=omitidas,
            total_valor=total_valor,
            total_agencia=total_agencia,
        )

    def _resolver_freelancer_id(
        self, nombre: str | None
    ) -> tuple[uuid.UUID | None, str | None]:
        """Resolve a participant name to a freelancer id via the repo.

        Returns (id, None) on exact match, (None, "no_encontrado") on 0 matches,
        (None, "ambiguo") on >=2 matches, and (None, None) when nombre is blank.
        """
        if not nombre:
            return None, None
        coincidencias = self._freelancers.listar_por_nombre(nombre)
        if len(coincidencias) == 1:
            return coincidencias[0].id, None
        if len(coincidencias) == 0:
            return None, "no_encontrado"
        return None, "ambiguo"

    def _resolver_servicio(
        self, descripcion: str, servicios_por_numero: dict[int, Servicio]
    ) -> uuid.UUID:
        numero = self._alias.get(_norm_desc(descripcion))
        servicio = servicios_por_numero.get(numero) if numero is not None else None
        if servicio is None:
            raise DescripcionSinMapeo(f"Sin servicio para la descripcion: {descripcion!r}")
        return servicio.id

    def _resolver_cliente(self, f: FilaVentaImportada) -> tuple[uuid.UUID, bool]:
        existente = self._clientes.buscar_por_nombre(f.cliente_nombre)
        if existente is not None:
            return existente.id, False
        cliente = Cliente(
            id=uuid.uuid5(_NS, f"cliente:{f.cliente_nombre.lower()}"),
            nombre=f.cliente_nombre,
            tipo=_tipo_cliente(f.canal),
        )
        self._clientes.guardar(cliente)
        return cliente.id, True

    def _venta_id(self, f: FilaVentaImportada) -> uuid.UUID:
        clave = (
            f"{f.cliente_nombre.lower()}|{f.fecha.isoformat()}"
            f"|{int(f.valor.monto)}|{f.descripcion.lower()[:15]}"
        )
        return uuid.uuid5(_NS, clave)

    def _desglose(
        self,
        f: FilaVentaImportada,
        venta: Venta,
        punto_crespo: PuntoDeVenta | None,
    ) -> DesgloseComision:
        # Crespo presencial path: derive personas, look up rule, calculate via motor.
        # Commission base is venta.ganancia = valor - neto (REQ-07 parity with live flow).
        if f.canal == _CANAL_CRESPO:
            numero_personas = _derivar_numero_personas(venta.participantes)
            reglas = self._reglas_repo.buscar_regla(
                _tipo_cliente(f.canal),
                _CANAL_CRESPO,
                numero_personas,
            )
            if reglas is None:
                raise ReglasComisionNoEncontradas(
                    f"No se encontraron reglas de comision para Crespo, "
                    f"personas={numero_personas!r}"
                )
            return self._motor.calcular(venta, reglas, punto_crespo, Decimal("0"))

        # Historical spreadsheet path for all non-Crespo rows (Hotel, Externas, etc.).
        punto_residual = f.margen - f.agencia - f.comision_vendedor - f.comision_cerrador
        margen = f.margen.monto

        def pct(x: Dinero) -> Decimal:
            return x.monto / margen if margen else Decimal("0")

        snapshot = SnapshotReglas(
            tipo_cliente=_tipo_cliente(f.canal),
            porcentaje_vendedor=pct(f.comision_vendedor),
            porcentaje_cerrador=pct(f.comision_cerrador),
            porcentaje_referido_maximo=Decimal("0"),
            porcentaje_capa_punto=pct(punto_residual),
        )
        return DesgloseComision(
            vendedor=f.comision_vendedor,
            cerrador=f.comision_cerrador,
            punto_de_venta=punto_residual,
            referido=_CERO,
            agencia=f.agencia,
            snapshot=snapshot,
        )
