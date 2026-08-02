"""Tests for the REPROCESS service (reprocesar_pendientes).

TDD RED phase: all tests are written before the implementation exists.
Uses fake in-memory repos and monkeypatched parsers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from garay.dominio.conciliacion.entidades import CorreoNoParseado, Egreso, Ingreso
from garay.dominio.puertos.repositorios import (
    CorreoNoParseadoRepository,
    EgresoRepository,
    IngresoRepository,
)
from garay.infraestructura.webhook.parser.base import (
    DIRECCION_EGRESO,
    DIRECCION_INGRESO,
    ErrorParseoBanco,
)
from garay.infraestructura.webhook.schemas import EgresoExtraido, PagoExtraido

# ---------------------------------------------------------------------------
# Helpers — fake repos
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def _make_correo(
    *,
    id: uuid.UUID | None = None,
    banco: str = "Bancolombia",
    direccion: str = DIRECCION_INGRESO,
    referencia: str = "msg-001",
    asunto: str = "Transferencia recibida",
    cuerpo_texto: str = "Recibiste $500,000",
    cuerpo_html: str = "",
    error_parseo: str = "parser choked",
    correo_origen: str | None = "bank@bancolombia.com",
) -> CorreoNoParseado:
    return CorreoNoParseado(
        id=id or uuid.uuid4(),
        banco=banco,
        direccion=direccion,
        referencia=referencia,
        asunto=asunto,
        cuerpo_texto=cuerpo_texto,
        cuerpo_html=cuerpo_html,
        error_parseo=error_parseo,
        fecha_recibido=_NOW,
        correo_origen=correo_origen,
        procesado=False,
        intentos=0,
        error_ultimo="",
    )


def _pago_extraido() -> PagoExtraido:
    return PagoExtraido(
        monto=Decimal("500000"),
        remitente="Carlos Gomez",
        banco_origen="Bancolombia",
        fecha_pago=datetime(2026, 7, 15, 10, 30, tzinfo=UTC),
    )


def _egreso_extraido() -> EgresoExtraido:
    return EgresoExtraido(
        monto=Decimal("69328"),
        descripcion="MOVISTAR PAGOSEPAYCO",
        banco_origen="Bancolombia",
        fecha_egreso=datetime(2026, 7, 27, 18, 25, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Fake in-memory correo repo
# ---------------------------------------------------------------------------


class FakeCorreoRepo(CorreoNoParseadoRepository):
    """Minimal in-memory implementation of CorreoNoParseadoRepository."""

    def __init__(self, pendientes: list[CorreoNoParseado]) -> None:
        self._pendientes = list(pendientes)
        self.marcados_procesados: list[uuid.UUID] = []
        self.intentos_fallidos: list[tuple[uuid.UUID, str]] = []

    def guardar(self, correo: CorreoNoParseado) -> None:
        self._pendientes.append(correo)

    def existe_referencia(self, referencia: str) -> bool:
        return any(c.referencia == referencia for c in self._pendientes)

    def listar_pendientes(self, max_intentos: int) -> list[CorreoNoParseado]:
        return [c for c in self._pendientes if not c.procesado and c.intentos < max_intentos]

    def marcar_procesado(self, id: uuid.UUID) -> None:
        self.marcados_procesados.append(id)
        for c in self._pendientes:
            if c.id == id:
                c.procesado = True

    def registrar_intento_fallido(self, id: uuid.UUID, error: str) -> None:
        self.intentos_fallidos.append((id, error))
        for c in self._pendientes:
            if c.id == id:
                c.intentos += 1
                c.error_ultimo = error


# ---------------------------------------------------------------------------
# Fake ingreso / egreso repos
# ---------------------------------------------------------------------------


class FakeIngresoRepo(IngresoRepository):
    def __init__(self, *, referencia_exists: bool = False) -> None:
        self._exists = referencia_exists
        self.guardados: list[Ingreso] = []

    def guardar(self, ingreso: Ingreso) -> None:
        self.guardados.append(ingreso)

    def existe_referencia(self, referencia: str) -> bool:
        return self._exists

    def buscar_por_id(self, id: uuid.UUID) -> Ingreso | None:
        return None

    def listar_sin_clasificar(self) -> list[Ingreso]:
        return []

    def listar_recientes(self, minutos: int) -> list[Ingreso]:
        return []

    def listar_por_periodo(self, desde: date, hasta: date) -> list[Ingreso]:
        return []


class FakeEgresoRepo(EgresoRepository):
    def __init__(self, *, referencia_exists: bool = False) -> None:
        self._exists = referencia_exists
        self.guardados: list[Egreso] = []

    def guardar(self, egreso: Egreso) -> None:
        self.guardados.append(egreso)

    def existe_referencia(self, referencia: str) -> bool:
        return self._exists

    def buscar_por_id(self, id: uuid.UUID) -> Egreso | None:
        return None

    def listar_recientes(self, minutos: int) -> list[Egreso]:
        return []

    def listar_por_periodo(self, desde: date, hasta: date) -> list[Egreso]:
        return []


# ---------------------------------------------------------------------------
# Import target (will fail until reproceso.py exists — RED)
# ---------------------------------------------------------------------------

from garay.infraestructura.webhook.reproceso import reprocesar_pendientes  # noqa: E402

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_reproceso_exito_marca_procesado_y_guarda() -> None:
    """A pending ingreso that now parses successfully must be persisted via
    guardar_ingreso, marcar_procesado must be called, and the row is counted
    as recuperado."""
    correo = _make_correo(direccion=DIRECCION_INGRESO, referencia="msg-001")
    correo_repo = FakeCorreoRepo(pendientes=[correo])
    ingreso_repo = FakeIngresoRepo(referencia_exists=False)
    egreso_repo = FakeEgresoRepo()

    mock_parser = MagicMock()
    mock_parser.parsear.return_value = _pago_extraido()

    with patch(
        "garay.infraestructura.webhook.reproceso.obtener_parser",
        return_value=mock_parser,
    ):
        resultado = reprocesar_pendientes(
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            egreso_repo=egreso_repo,
            moneda="COP",
            max_intentos=5,
        )

    assert resultado.recuperados == 1
    assert resultado.ya_existian == 0
    assert resultado.fallidos == 0
    assert correo.id in correo_repo.marcados_procesados
    assert len(ingreso_repo.guardados) == 1


def test_reproceso_no_guarda_si_referencia_duplicada() -> None:
    """If ingreso_repo.existe_referencia returns True (bank re-sent and live
    route already saved it), guardar is NOT called but marcar_procesado IS,
    and the row is counted as ya_existian."""
    correo = _make_correo(direccion=DIRECCION_INGRESO, referencia="msg-002")
    correo_repo = FakeCorreoRepo(pendientes=[correo])
    ingreso_repo = FakeIngresoRepo(referencia_exists=True)
    egreso_repo = FakeEgresoRepo()

    mock_parser = MagicMock()
    mock_parser.parsear.return_value = _pago_extraido()

    with patch(
        "garay.infraestructura.webhook.reproceso.obtener_parser",
        return_value=mock_parser,
    ):
        resultado = reprocesar_pendientes(
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            egreso_repo=egreso_repo,
            moneda="COP",
            max_intentos=5,
        )

    assert resultado.ya_existian == 1
    assert resultado.recuperados == 0
    assert resultado.fallidos == 0
    assert correo.id in correo_repo.marcados_procesados
    assert len(ingreso_repo.guardados) == 0


def test_reproceso_usa_direccion_guardada() -> None:
    """A row with direccion=egreso must route to the egreso parser and egreso repo,
    not to the ingreso path."""
    correo = _make_correo(
        direccion=DIRECCION_EGRESO,
        referencia="msg-003",
        cuerpo_texto="Compraste $69.328 en MOVISTAR con tu T.Deb *9283, el 27/07/2026 a las 18:25.",
    )
    correo_repo = FakeCorreoRepo(pendientes=[correo])
    ingreso_repo = FakeIngresoRepo()
    egreso_repo = FakeEgresoRepo(referencia_exists=False)

    mock_parser_egreso = MagicMock()
    mock_parser_egreso.parsear.return_value = _egreso_extraido()

    with (
        patch(
            "garay.infraestructura.webhook.reproceso.obtener_parser_egreso",
            return_value=mock_parser_egreso,
        ),
        patch("garay.infraestructura.webhook.reproceso.obtener_parser") as mock_ingreso_parser_fn,
    ):
        resultado = reprocesar_pendientes(
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            egreso_repo=egreso_repo,
            moneda="COP",
            max_intentos=5,
        )

    # Egreso parser was used
    mock_parser_egreso.parsear.assert_called_once()
    # Ingreso parser factory was NOT called
    mock_ingreso_parser_fn.assert_not_called()
    assert resultado.recuperados == 1
    assert len(egreso_repo.guardados) == 1
    assert len(ingreso_repo.guardados) == 0


def test_reproceso_reconstruye_reenviado_desde_asunto() -> None:
    """detectar_reenvio must receive correo.asunto so the saved ingreso carries
    the correct reenviado flag when the subject starts with 'Fwd:'."""
    correo = _make_correo(
        direccion=DIRECCION_INGRESO,
        referencia="msg-004",
        asunto="Fwd: Transferencia recibida",
    )
    correo_repo = FakeCorreoRepo(pendientes=[correo])
    ingreso_repo = FakeIngresoRepo(referencia_exists=False)
    egreso_repo = FakeEgresoRepo()

    mock_parser = MagicMock()
    mock_parser.parsear.return_value = _pago_extraido()

    with patch(
        "garay.infraestructura.webhook.reproceso.obtener_parser",
        return_value=mock_parser,
    ):
        reprocesar_pendientes(
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            egreso_repo=egreso_repo,
            moneda="COP",
            max_intentos=5,
        )

    assert len(ingreso_repo.guardados) == 1
    ingreso = ingreso_repo.guardados[0]
    # detectar_reenvio("Fwd: Transferencia recibida", ...) must return True
    assert ingreso.reenviado is True


def test_reproceso_falla_incrementa_intentos_no_marca_procesado() -> None:
    """When the parser still raises ErrorParseoBanco, registrar_intento_fallido
    is called, marcar_procesado is NOT called, and the row is counted as fallido."""
    correo = _make_correo(direccion=DIRECCION_INGRESO, referencia="msg-005")
    correo_repo = FakeCorreoRepo(pendientes=[correo])
    ingreso_repo = FakeIngresoRepo()
    egreso_repo = FakeEgresoRepo()

    with patch(
        "garay.infraestructura.webhook.reproceso.obtener_parser",
        side_effect=ErrorParseoBanco("still broken"),
    ):
        resultado = reprocesar_pendientes(
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            egreso_repo=egreso_repo,
            moneda="COP",
            max_intentos=5,
        )

    assert resultado.fallidos == 1
    assert resultado.recuperados == 0
    assert correo.id not in correo_repo.marcados_procesados
    assert len(correo_repo.intentos_fallidos) == 1
    assert correo_repo.intentos_fallidos[0][0] == correo.id
    assert "still broken" in correo_repo.intentos_fallidos[0][1]


def test_reproceso_una_fila_mala_no_aborta_el_lote() -> None:
    """An unexpected exception on one row must not abort processing of subsequent rows."""
    correo_malo = _make_correo(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        referencia="msg-bad",
        banco="Bancolombia",
        direccion=DIRECCION_INGRESO,
    )
    correo_bueno = _make_correo(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        referencia="msg-good",
        banco="Bancolombia",
        direccion=DIRECCION_INGRESO,
    )
    correo_repo = FakeCorreoRepo(pendientes=[correo_malo, correo_bueno])
    ingreso_repo = FakeIngresoRepo(referencia_exists=False)
    egreso_repo = FakeEgresoRepo()

    call_count = 0

    def flaky_obtener_parser(banco: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("unexpected database timeout")
        mock = MagicMock()
        mock.parsear.return_value = _pago_extraido()
        return mock

    with patch(
        "garay.infraestructura.webhook.reproceso.obtener_parser",
        side_effect=flaky_obtener_parser,
    ):
        resultado = reprocesar_pendientes(
            correo_repo=correo_repo,
            ingreso_repo=ingreso_repo,
            egreso_repo=egreso_repo,
            moneda="COP",
            max_intentos=5,
        )

    # Good row was still processed
    assert correo_bueno.id in correo_repo.marcados_procesados
    # Good row was persisted
    assert len(ingreso_repo.guardados) == 1
    # Overall result reflects both rows
    assert resultado.recuperados == 1
    assert resultado.fallidos == 1
