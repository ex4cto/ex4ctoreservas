"""Tests for PTB handler utilities: _get_fsm and _contexto_a_comando."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.infraestructura.telegram.handlers import (
    _contexto_a_comando,
    _foto_en_conversacion,
    _get_fsm,
    cmd_foto,
    cmd_start,
)

# ── helpers ─────────────────────────────────────────────────────────────────


def _update(telegram_id: int = 12345) -> MagicMock:
    u = MagicMock()
    u.effective_user.id = telegram_id
    return u


def _context(bot_data: dict) -> MagicMock:  # type: ignore[type-arg]
    c = MagicMock()
    c.bot_data = bot_data
    return c


def _freelancer(nombre: str = "Maria Lopez") -> MagicMock:
    f = MagicMock()
    f.nombre = nombre
    return f


def _servicio(numero: int, sid: uuid.UUID | None = None) -> MagicMock:
    s = MagicMock()
    s.numero = numero
    s.id = sid or uuid.uuid4()
    return s


def _pdv(nombre: str, pid: uuid.UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.nombre = nombre
    p.id = pid or uuid.uuid4()
    return p


def _full_ctx(**overrides: object) -> ContextoVenta:
    defaults: dict[str, object] = {
        "tipo_cliente": TipoCliente.INTERNO,
        "destinos_numeros": [1],
        "cliente_nombre": "Juan Perez",
        "cliente_telefono": "3001234567",
        "fecha_salida": datetime.datetime(2026, 12, 25),
        "adultos": 2,
        "ninos": 0,
        "valor": Decimal("500000"),
        "neto": Decimal("450000"),
        "rol_registrante": "ambos",
    }
    defaults.update(overrides)
    return ContextoVenta(**defaults)  # type: ignore[arg-type]


def _base_bot_data(
    *,
    freelancer_nombre: str = "Maria Lopez",
    servicio_numero: int = 1,
) -> tuple[dict, uuid.UUID]:  # type: ignore[type-arg]
    sid = uuid.uuid4()
    fl_repo = MagicMock()
    fl_repo.buscar_por_telegram_id.return_value = _freelancer(freelancer_nombre)
    s_repo = MagicMock()
    s_repo.listar.return_value = [_servicio(servicio_numero, sid)]
    c_repo = MagicMock()
    bot_data = {
        "freelancer_repo": fl_repo,
        "servicio_repo": s_repo,
        "cliente_repo": c_repo,
    }
    return bot_data, sid


# ── TestGetFsm ───────────────────────────────────────────────────────────────


class TestGetFsm:
    def test_returns_fsm_when_present(self) -> None:
        fsm = FSMTiquetera(servicios=[], puntos_venta=[])  # type: ignore[arg-type]
        result = _get_fsm(_context({"fsm": fsm}))
        assert result is fsm

    def test_returns_none_when_missing(self) -> None:
        assert _get_fsm(_context({})) is None

    def test_returns_none_when_wrong_type(self) -> None:
        assert _get_fsm(_context({"fsm": "not-a-fsm"})) is None


# ── TestContextoAComando ─────────────────────────────────────────────────────


class TestContextoAComando:
    def test_ambos_sets_both_names_to_freelancer(self) -> None:
        bot_data, _ = _base_bot_data(freelancer_nombre="Maria Lopez")
        ctx = _full_ctx(rol_registrante="ambos", destinos_numeros=[1])
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.participantes.vendedor_nombre == "Maria Lopez"
        assert cmd.participantes.cerrador_nombre == "Maria Lopez"

    def test_vendedor_sets_vendedor_to_freelancer_cerrador_from_ctx(self) -> None:
        bot_data, _ = _base_bot_data(freelancer_nombre="Maria")
        ctx = _full_ctx(rol_registrante="vendedor", cerrador_nombre="Pedro")
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.participantes.vendedor_nombre == "Maria"
        assert cmd.participantes.cerrador_nombre == "Pedro"

    def test_cerrador_sets_cerrador_to_freelancer_vendedor_from_ctx(self) -> None:
        bot_data, _ = _base_bot_data(freelancer_nombre="Maria")
        ctx = _full_ctx(rol_registrante="cerrador", vendedor_nombre="Juan")
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.participantes.cerrador_nombre == "Maria"
        assert cmd.participantes.vendedor_nombre == "Juan"

    def test_returns_none_when_effective_user_is_none(self) -> None:
        u = MagicMock()
        u.effective_user = None
        bot_data, _ = _base_bot_data()
        assert _contexto_a_comando(u, _context(bot_data), _full_ctx()) is None

    def test_returns_none_when_freelancer_repo_missing(self) -> None:
        assert _contexto_a_comando(_update(), _context({}), _full_ctx()) is None

    def test_returns_none_when_freelancer_not_found(self) -> None:
        fl_repo = MagicMock()
        fl_repo.buscar_por_telegram_id.return_value = None
        bot_data: dict = {"freelancer_repo": fl_repo}  # type: ignore[type-arg]
        assert _contexto_a_comando(_update(), _context(bot_data), _full_ctx()) is None

    def test_returns_none_when_rol_registrante_invalid(self) -> None:
        bot_data, _ = _base_bot_data()
        ctx = _full_ctx(rol_registrante=None)
        assert _contexto_a_comando(_update(), _context(bot_data), ctx) is None

    def test_returns_none_when_valor_is_none(self) -> None:
        bot_data, _ = _base_bot_data()
        ctx = _full_ctx(valor=None)
        assert _contexto_a_comando(_update(), _context(bot_data), ctx) is None

    def test_returns_none_when_destinos_empty(self) -> None:
        bot_data, _ = _base_bot_data()
        ctx = _full_ctx(destinos_numeros=[])
        assert _contexto_a_comando(_update(), _context(bot_data), ctx) is None

    def test_returns_none_when_servicio_repo_missing(self) -> None:
        fl_repo = MagicMock()
        fl_repo.buscar_por_telegram_id.return_value = _freelancer()
        bot_data: dict = {"freelancer_repo": fl_repo}  # type: ignore[type-arg]
        assert _contexto_a_comando(_update(), _context(bot_data), _full_ctx()) is None

    def test_returns_none_when_no_servicio_matches(self) -> None:
        bot_data, _ = _base_bot_data(servicio_numero=99)
        ctx = _full_ctx(destinos_numeros=[1])
        assert _contexto_a_comando(_update(), _context(bot_data), ctx) is None

    def test_returns_none_when_cliente_repo_missing(self) -> None:
        fl_repo = MagicMock()
        fl_repo.buscar_por_telegram_id.return_value = _freelancer()
        s_repo = MagicMock()
        s_repo.listar.return_value = [_servicio(1)]
        bot_data: dict = {"freelancer_repo": fl_repo, "servicio_repo": s_repo}  # type: ignore[type-arg]
        assert _contexto_a_comando(_update(), _context(bot_data), _full_ctx()) is None

    def test_servicio_ids_resolved_correctly(self) -> None:
        sid = uuid.uuid4()
        fl_repo = MagicMock()
        fl_repo.buscar_por_telegram_id.return_value = _freelancer()
        s_repo = MagicMock()
        s_repo.listar.return_value = [_servicio(1, sid), _servicio(2)]
        c_repo = MagicMock()
        bot_data = {"freelancer_repo": fl_repo, "servicio_repo": s_repo, "cliente_repo": c_repo}
        ctx = _full_ctx(destinos_numeros=[1])
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.servicio_ids == [sid]

    def test_pdv_id_resolved_when_pdv_repo_present(self) -> None:
        bot_data, _ = _base_bot_data()
        pdv_id = uuid.uuid4()
        pdv_repo = MagicMock()
        pdv_repo.listar.return_value = [_pdv("Marie Real", pdv_id)]
        bot_data["pdv_repo"] = pdv_repo
        ctx = _full_ctx(punto_de_venta_nombre="Marie Real")
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.participantes.punto_de_venta_id == pdv_id

    def test_pdv_id_none_when_no_match(self) -> None:
        bot_data, _ = _base_bot_data()
        pdv_repo = MagicMock()
        pdv_repo.listar.return_value = [_pdv("Otro PDV")]
        bot_data["pdv_repo"] = pdv_repo
        ctx = _full_ctx(punto_de_venta_nombre="Marie Real")
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.participantes.punto_de_venta_id is None

    def test_pdv_match_is_case_insensitive(self) -> None:
        bot_data, _ = _base_bot_data()
        pdv_id = uuid.uuid4()
        pdv_repo = MagicMock()
        pdv_repo.listar.return_value = [_pdv("MARIE REAL", pdv_id)]
        bot_data["pdv_repo"] = pdv_repo
        ctx = _full_ctx(punto_de_venta_nombre="marie real")
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.participantes.punto_de_venta_id == pdv_id

    def test_cliente_guardar_called_once(self) -> None:
        bot_data, _ = _base_bot_data()
        ctx = _full_ctx()
        _contexto_a_comando(_update(), _context(bot_data), ctx)
        bot_data["cliente_repo"].guardar.assert_called_once()

    def test_abono_none_when_ctx_abono_none(self) -> None:
        bot_data, _ = _base_bot_data()
        ctx = _full_ctx(abono=None)
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.abono is None

    def test_abono_set_when_ctx_abono_present(self) -> None:
        bot_data, _ = _base_bot_data()
        ctx = _full_ctx(abono=Decimal("50000"))
        cmd = _contexto_a_comando(_update(), _context(bot_data), ctx)
        assert cmd is not None
        assert cmd.abono is not None


# ── TestCmdFoto ──────────────────────────────────────────────────────────────


def _make_freelancer_repo(found: bool = True) -> MagicMock:
    repo = MagicMock()
    if found:
        fl = MagicMock()
        fl.nombre = "Maria"
        repo.buscar_por_telegram_id.return_value = fl
    else:
        repo.buscar_por_telegram_id.return_value = None
    return repo


class TestCmdFoto:
    def _make_update_with_photo(self) -> MagicMock:
        update = MagicMock()
        update.message = MagicMock()
        update.message.photo = [MagicMock()]  # non-empty list
        update.message.document = None
        update.message.text = None
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.effective_message = MagicMock()
        update.callback_query = None
        # Make get_file().download_as_bytearray() async
        file_mock = AsyncMock()
        file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake_image_bytes"))
        update.message.photo[-1].get_file = AsyncMock(return_value=file_mock)
        return update

    def _make_context(self, bot_data: dict) -> MagicMock:  # type: ignore[type-arg]
        ctx = MagicMock()
        ctx.bot_data = bot_data
        ctx.user_data = {}
        return ctx

    @pytest.mark.asyncio
    async def test_cmd_foto_sin_extractor_en_bot_data(self) -> None:
        update = self._make_update_with_photo()
        update.effective_message.reply_text = AsyncMock()
        fl_repo = _make_freelancer_repo(found=True)
        context = self._make_context({"freelancer_repo": fl_repo})
        result = await cmd_foto(update, context)
        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_foto_timeout_ollama(self) -> None:
        update = self._make_update_with_photo()
        update.effective_message.reply_text = AsyncMock()

        fsm = FSMTiquetera(servicios=[(1, "Tour", Decimal("100"), None)], puntos_venta=["PDV"])
        fl_repo = _make_freelancer_repo(found=True)
        bot_data = {"extractor_reserva": MagicMock(), "fsm": fsm, "freelancer_repo": fl_repo}
        context = self._make_context(bot_data)

        wait_for_path = "garay.infraestructura.telegram.handlers.asyncio.wait_for"
        with patch(wait_for_path, new=AsyncMock(side_effect=TimeoutError())):
            result = await cmd_foto(update, context)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_foto_extractor_error(self) -> None:
        update = self._make_update_with_photo()
        update.effective_message.reply_text = AsyncMock()

        fsm = FSMTiquetera(servicios=[(1, "Tour", Decimal("100"), None)], puntos_venta=["PDV"])
        fl_repo = _make_freelancer_repo(found=True)
        bot_data = {"extractor_reserva": MagicMock(), "fsm": fsm, "freelancer_repo": fl_repo}
        context = self._make_context(bot_data)

        wait_for_path = "garay.infraestructura.telegram.handlers.asyncio.wait_for"
        with patch(wait_for_path, new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await cmd_foto(update, context)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_foto_exitoso(self) -> None:
        update = self._make_update_with_photo()
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        extracted_ctx = ContextoVenta(cliente_nombre="Maria", adultos=2)
        fsm = FSMTiquetera(servicios=[(1, "Tour", Decimal("100"), None)], puntos_venta=["PDV"])
        fl_repo = _make_freelancer_repo(found=True)
        bot_data = {"extractor_reserva": MagicMock(), "fsm": fsm, "freelancer_repo": fl_repo}
        context = self._make_context(bot_data)

        wait_for_path = "garay.infraestructura.telegram.handlers.asyncio.wait_for"
        with patch(wait_for_path, new=AsyncMock(return_value=extracted_ctx)):
            result = await cmd_foto(update, context)

        # Should start at TIPO_RESERVA
        assert result == ESTADO_PTB[EstadoFSM.TIPO_RESERVA]
        # user_data should have the extracted ctx
        assert context.user_data["contexto"] is extracted_ctx

    @pytest.mark.asyncio
    async def test_foto_en_conversacion_activa(self) -> None:
        update = MagicMock()
        update.effective_message = MagicMock()
        update.effective_message.reply_text = AsyncMock()
        context = MagicMock()

        result = await _foto_en_conversacion(update, context)
        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()


class TestCmdStart:
    """WU-6: /start returns METODO_INPUT state."""

    @pytest.mark.asyncio
    async def test_cmd_start_retorna_metodo_input(self) -> None:
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        update.effective_message = update.message
        update.effective_user = MagicMock()
        update.effective_user.id = 12345

        fsm = FSMTiquetera(servicios=[(1, "Tour", Decimal("100"), None)], puntos_venta=["PDV"])
        fl_repo = _make_freelancer_repo(found=True)
        context = MagicMock()
        context.bot_data = {"fsm": fsm, "freelancer_repo": fl_repo}
        context.user_data = {}

        result = await cmd_start(update, context)
        assert result == ESTADO_PTB[EstadoFSM.METODO_INPUT]
