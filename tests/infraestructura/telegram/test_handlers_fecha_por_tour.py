"""Tests for _contexto_a_comando per-tour date mapping (Slice 2 — fecha-por-tour)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.infraestructura.telegram.handlers import _contexto_a_comando, cmd_mis_ventas


def _update(telegram_id: int = 12345) -> MagicMock:
    u = MagicMock()
    u.effective_user.id = telegram_id
    return u


def _context(bot_data: dict) -> MagicMock:  # type: ignore[type-arg]
    c = MagicMock()
    c.bot_data = bot_data
    return c


def _freelancer(nombre: str = "Maria Lopez", fl_id: uuid.UUID | None = None) -> MagicMock:
    f = MagicMock()
    f.nombre = nombre
    f.id = fl_id or uuid.uuid4()
    return f


def _servicio(numero: int, sid: uuid.UUID | None = None) -> MagicMock:
    s = MagicMock()
    s.numero = numero
    s.id = sid or uuid.uuid4()
    return s


def _bot_data_two_tours(
    sid1: uuid.UUID,
    sid2: uuid.UUID,
) -> dict:  # type: ignore[type-arg]
    fl_repo = MagicMock()
    fl_repo.buscar_por_telegram_id.return_value = _freelancer()
    s_repo = MagicMock()
    s_repo.listar.return_value = [_servicio(1, sid1), _servicio(2, sid2)]
    c_repo = MagicMock()
    return {"freelancer_repo": fl_repo, "servicio_repo": s_repo, "cliente_repo": c_repo}


def _full_ctx_two_tours(
    sid1: uuid.UUID,
    sid2: uuid.UUID,
    dt1: datetime.datetime,
    dt2: datetime.datetime,
    **overrides: object,
) -> ContextoVenta:
    defaults: dict[str, object] = {
        "tipo_cliente": TipoCliente.INTERNO,
        "destinos_numeros": [1, 2],
        "cliente_nombre": "Juan Perez",
        "cliente_telefono": "3001234567",
        "fecha_salida": min(dt1, dt2),
        "fechas_por_servicio": {1: dt1, 2: dt2},
        "adultos": 2,
        "ninos": 0,
        "valor": Decimal("500000"),
        "neto": Decimal("450000"),
        "rol_registrante": "ambos",
    }
    defaults.update(overrides)
    return ContextoVenta(**defaults)  # type: ignore[arg-type]


class TestContextoAComandoFechasPorServicio:
    def test_fechas_por_servicio_translated_to_ids(self) -> None:
        """fechas_por_servicio keyed by numero → translated to servicio ids."""
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        dt1 = datetime.datetime(2026, 12, 20, 10, 0)
        dt2 = datetime.datetime(2026, 12, 22, 9, 0)
        bot_data = _bot_data_two_tours(sid1, sid2)
        ctx = _full_ctx_two_tours(sid1, sid2, dt1, dt2)

        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.fechas_por_servicio is not None
        assert cmd.fechas_por_servicio[sid1] == dt1
        assert cmd.fechas_por_servicio[sid2] == dt2

    def test_primary_fecha_is_min_of_fechas_por_servicio(self) -> None:
        """cmd.fecha must equal the earliest date across all tours."""
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        dt1 = datetime.datetime(2026, 12, 22, 9, 0)  # later
        dt2 = datetime.datetime(2026, 12, 20, 8, 0)  # earlier
        bot_data = _bot_data_two_tours(sid1, sid2)
        ctx = _full_ctx_two_tours(sid1, sid2, dt1, dt2)

        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.fecha == datetime.date(2026, 12, 20)

    def test_single_tour_fallback_uses_ctx_fecha_salida(self) -> None:
        """Single tour with empty fechas_por_servicio falls back to ctx.fecha_salida."""
        sid1 = uuid.uuid4()
        fl_repo = MagicMock()
        fl_repo.buscar_por_telegram_id.return_value = _freelancer()
        s_repo = MagicMock()
        s_repo.listar.return_value = [_servicio(1, sid1)]
        c_repo = MagicMock()
        bot_data = {
            "freelancer_repo": fl_repo,
            "servicio_repo": s_repo,
            "cliente_repo": c_repo,
        }
        ctx = ContextoVenta(
            tipo_cliente=TipoCliente.INTERNO,
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300",
            fecha_salida=datetime.datetime(2026, 12, 25),
            adultos=2,
            ninos=0,
            valor=Decimal("500000"),
            neto=Decimal("450000"),
            rol_registrante="ambos",
            fechas_por_servicio={},
        )
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.fecha == datetime.date(2026, 12, 25)

    def test_fechas_por_servicio_none_when_map_empty_and_no_ids(self) -> None:
        """Single-tour with empty fechas_por_servicio passes None to command.

        All required fields are present so the function reaches the fechas_id
        block (no earlier guard returns None).
        """
        sid1 = uuid.uuid4()
        fl_repo = MagicMock()
        fl_repo.buscar_por_telegram_id.return_value = _freelancer()
        s_repo = MagicMock()
        s_repo.listar.return_value = [_servicio(1, sid1)]
        c_repo = MagicMock()
        bot_data = {
            "freelancer_repo": fl_repo,
            "servicio_repo": s_repo,
            "cliente_repo": c_repo,
        }
        ctx = ContextoVenta(
            tipo_cliente=TipoCliente.INTERNO,
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="3001234567",  # required to rule out early-guard confusion
            fecha_salida=datetime.datetime(2026, 12, 25),
            adultos=2,
            ninos=0,
            valor=Decimal("500000"),
            neto=Decimal("450000"),
            rol_registrante="ambos",
            fechas_por_servicio={},  # empty — single tour, so guard does NOT fire
        )
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.fechas_por_servicio is None


class TestIncompleteDateGuard:
    """Tests for the multi-tour incomplete-date guard in _contexto_a_comando."""

    def _full_two_tour_ctx(
        self,
        fechas_por_servicio: dict[int, datetime.datetime],
        fecha_salida: datetime.datetime,
    ) -> ContextoVenta:
        """Valid two-tour context with all required fields except per-tour dates override."""
        return ContextoVenta(
            tipo_cliente=TipoCliente.INTERNO,
            destinos_numeros=[1, 2],
            cliente_nombre="Juan Perez",
            cliente_telefono="3001234567",
            fecha_salida=fecha_salida,
            fechas_por_servicio=fechas_por_servicio,
            adultos=2,
            ninos=0,
            valor=Decimal("500000"),
            neto=Decimal("450000"),
            rol_registrante="ambos",
        )

    def test_one_of_two_tours_missing_date_returns_none(self) -> None:
        """Two destinos, only tour 1 has a date → _contexto_a_comando returns None."""
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        dt1 = datetime.datetime(2026, 12, 20)
        bot_data = _bot_data_two_tours(sid1, sid2)
        # Tour 2 intentionally absent from fechas_por_servicio
        ctx = self._full_two_tour_ctx(
            fechas_por_servicio={1: dt1},
            fecha_salida=dt1,
        )
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is None

    def test_empty_fechas_por_servicio_with_two_tours_returns_none(self) -> None:
        """Two destinos, empty fechas_por_servicio → returns None (new guard)."""
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        bot_data = _bot_data_two_tours(sid1, sid2)
        ctx = self._full_two_tour_ctx(
            fechas_por_servicio={},
            fecha_salida=datetime.datetime(2026, 12, 20),
        )
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is None


class TestNightTourTimePrecision:
    """Per-tour datetime with explicit HH:MM must be preserved through numero→id translation."""

    def test_night_tour_time_preserved_in_command(self) -> None:
        """datetime(2026,12,20,22,30) for a per-tour entry preserves 22:30 in cmd."""
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        dt1 = datetime.datetime(2026, 12, 20, 22, 30)
        dt2 = datetime.datetime(2026, 12, 22, 9, 0)
        bot_data = _bot_data_two_tours(sid1, sid2)
        ctx = _full_ctx_two_tours(sid1, sid2, dt1, dt2)

        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.fechas_por_servicio is not None
        translated = cmd.fechas_por_servicio[sid1]
        assert translated.hour == 22
        assert translated.minute == 30


def _venta(
    fecha: datetime.date,
    fechas_por_servicio: dict[uuid.UUID, datetime.datetime] | None,
    monto: Decimal = Decimal("500000"),
) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.fecha = fecha
    v.valor_venta.monto = monto
    v.canal_origen = None
    v.fechas_por_servicio = fechas_por_servicio
    return v


def _mis_ventas_context(ventas: list[MagicMock]) -> MagicMock:
    freelancer = MagicMock()
    freelancer.id = uuid.uuid4()
    freelancer.nombre = "Carlos"
    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer

    venta_repo = MagicMock()
    venta_repo.listar_por_freelancer_y_periodo.return_value = ventas

    comision_repo = MagicMock()
    comision_repo.listar_por_venta_ids.return_value = []

    ctx = MagicMock()
    ctx.bot_data = {
        "freelancer_repo": freelancer_repo,
        "venta_repo": venta_repo,
        "comision_registrada_repo": comision_repo,
    }
    return ctx


def _mis_ventas_update(user_id: int = 123) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    return update


class TestMisVentasVariasFechasMarker:
    """/mis_ventas appends ' (varias fechas)' only when a sale spans >1 tour date."""

    async def _mensaje(self, ventas: list[MagicMock]) -> str:
        update = _mis_ventas_update()
        context = _mis_ventas_context(ventas)
        await cmd_mis_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]
        msg: str = update.effective_message.reply_text.call_args[0][0]
        return msg

    @pytest.mark.asyncio
    async def test_single_tour_no_marker(self) -> None:
        """fechas_por_servicio None → no marker."""
        v = _venta(datetime.date(2026, 12, 20), None)
        msg = await self._mensaje([v])
        assert "20/12" in msg
        assert "(varias fechas)" not in msg

    @pytest.mark.asyncio
    async def test_one_entry_map_no_marker(self) -> None:
        """A map with a single entry (one tour) → no marker."""
        v = _venta(
            datetime.date(2026, 12, 20),
            {uuid.uuid4(): datetime.datetime(2026, 12, 20, 8, 0)},
        )
        msg = await self._mensaje([v])
        assert "(varias fechas)" not in msg

    @pytest.mark.asyncio
    async def test_multi_tour_marker_present(self) -> None:
        """A map with >1 entry → ' (varias fechas)' appended to the line."""
        v = _venta(
            datetime.date(2026, 12, 20),
            {
                uuid.uuid4(): datetime.datetime(2026, 12, 20, 8, 0),
                uuid.uuid4(): datetime.datetime(2026, 12, 22, 19, 0),
            },
        )
        msg = await self._mensaje([v])
        assert "20/12" in msg
        assert "(varias fechas)" in msg
