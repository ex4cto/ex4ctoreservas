"""RED tests for NotificarCambioCatalogoServicio.

All infrastructure is faked/mocked. No Playwright, no DB, no Telegram.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fakes / helpers
# ---------------------------------------------------------------------------


class FakeCambiosRepo:
    """In-memory fake for CambiosPendientesRepository."""

    def __init__(self) -> None:
        self._registros: list[str] = []

    def registrar(self, descripcion: str) -> None:
        self._registros.append(descripcion)

    def listar_todos(self) -> list[object]:
        import datetime

        from garay.dominio.puertos.cambios_imagen import CambioPendiente

        return [
            CambioPendiente(id=i + 1, descripcion=d, creado_en=datetime.datetime.now())
            for i, d in enumerate(self._registros)
        ]

    def limpiar(self) -> None:
        self._registros.clear()


class FakeNotificador:
    """Async fake for NotificadorTextoPort."""

    def __init__(self) -> None:
        self.enviados: list[tuple[int, str]] = []

    async def enviar(self, chat_id: int, texto: str) -> None:
        self.enviados.append((chat_id, texto))


def _make_svc(
    repo: object | None = None,
    notificador: object | None = None,
    publicar_svc: object | None = None,
    destinatarios: list[int] | None = None,
    dev_ids: list[int] | None = None,
    grupo_id: str = "",
) -> object:
    from garay.aplicacion.servicios.notificaciones_catalogo import (
        NotificarCambioCatalogoServicio,
    )

    _repo = repo or FakeCambiosRepo()
    _notif = notificador or FakeNotificador()
    _pub = publicar_svc or MagicMock()
    return NotificarCambioCatalogoServicio(
        cambios_repo=_repo,
        notificador=_notif,
        publicar_svc=_pub,
        destinatarios=destinatarios or [111],
        dev_ids=dev_ids or [111],
        grupo_id=grupo_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNotificarCambioCatalogoServicio:
    @pytest.mark.asyncio
    async def test_registrar_cambio_persiste_en_repo(self) -> None:
        """registrar_cambio persists a descripcion in the repo."""
        repo = FakeCambiosRepo()
        svc = _make_svc(repo=repo)

        await svc.registrar_cambio("editado", "Ryan", "Playa Tranquila")

        assert len(repo._registros) == 1
        assert "Playa Tranquila" in repo._registros[0]

    @pytest.mark.asyncio
    async def test_timer_se_reinicia_en_cada_cambio(self) -> None:
        """Two rapid changes cancel and restart the reminder timer — only 1 reminder sent."""
        import garay.aplicacion.servicios.notificaciones_catalogo as mod

        original = mod.DEBOUNCE_RECORDATORIO_SEG
        mod.DEBOUNCE_RECORDATORIO_SEG = 0  # fire immediately

        repo = FakeCambiosRepo()
        notificador = FakeNotificador()
        svc = _make_svc(repo=repo, notificador=notificador, destinatarios=[111])

        # Two rapid changes
        await svc.registrar_cambio("editado", "Ryan", "Tour A")
        await svc.registrar_cambio("editado", "Ryan", "Tour B")

        # Let the timer fire
        await asyncio.sleep(0.05)

        # Only one reminder batch should have been sent (for the second timer)
        reminder_texts = [texto for _cid, texto in notificador.enviados]
        assert len(notificador.enviados) == 1
        assert len(reminder_texts) == 1

        mod.DEBOUNCE_RECORDATORIO_SEG = original

    @pytest.mark.asyncio
    async def test_generar_confirma_y_limpia_repo(self) -> None:
        """generar_y_confirmar publishes, clears the repo, and DMs all destinatarios."""
        from unittest.mock import AsyncMock

        repo = FakeCambiosRepo()
        repo.registrar("• Ryan editó <i>Tour X</i>")

        notificador = FakeNotificador()
        pub_svc = MagicMock()
        pub_svc.publicar = AsyncMock()

        svc = _make_svc(
            repo=repo,
            notificador=notificador,
            publicar_svc=pub_svc,
            destinatarios=[111, 222],
            dev_ids=[111],
        )
        await svc.generar_y_confirmar()

        # publicar() was called directly on the service
        pub_svc.publicar.assert_called_once()

        # repo was cleared
        assert repo._registros == []

        # confirmation sent to all destinatarios
        dest_ids = [cid for cid, _ in notificador.enviados]
        assert 111 in dest_ids
        assert 222 in dest_ids

    @pytest.mark.asyncio
    async def test_sin_pendientes_no_genera(self) -> None:
        """With empty repo, generar_y_confirmar skips publish and returns without error."""
        from unittest.mock import AsyncMock

        repo = FakeCambiosRepo()  # empty
        notificador = FakeNotificador()
        pub_svc = MagicMock()
        pub_svc.publicar = AsyncMock()

        svc = _make_svc(repo=repo, notificador=notificador, publicar_svc=pub_svc, destinatarios=[111])
        await svc.generar_y_confirmar()

        # publish was NOT called — no pending changes
        pub_svc.publicar.assert_not_called()
        # no confirmations sent either
        assert notificador.enviados == []

    @pytest.mark.asyncio
    async def test_generar_forzado_publica_sin_pendientes(self) -> None:
        """generar_forzado() publishes images even with an empty repo."""
        from unittest.mock import AsyncMock

        repo = FakeCambiosRepo()  # empty
        notificador = FakeNotificador()
        pub_svc = MagicMock()
        pub_svc.publicar = AsyncMock()

        svc = _make_svc(repo=repo, notificador=notificador, publicar_svc=pub_svc, destinatarios=[111])
        await svc.generar_forzado()

        pub_svc.publicar.assert_called_once()
        dest_ids = [cid for cid, _ in notificador.enviados]
        assert 111 in dest_ids

    @pytest.mark.asyncio
    async def test_descripcion_usa_html_escape(self) -> None:
        """Tour names with HTML chars are escaped in the stored description."""
        repo = FakeCambiosRepo()
        svc = _make_svc(repo=repo)

        await svc.registrar_cambio("editado", "Admin", "<VIP>")

        assert len(repo._registros) == 1
        assert "&lt;VIP&gt;" in repo._registros[0]
        assert "<VIP>" not in repo._registros[0]
