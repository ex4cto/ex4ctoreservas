"""Tests for ProveedorUsoRailwayHTTP — Railway GraphQL API adapter.

TDD RED phase: tests written before implementation exists.

Covers:
- uso_mes_a_la_fecha: correct dict parsing from usage response
- uso_mes_a_la_fecha: request carries Bearer header + correct query + correct ISO dates
- estimado_mes: correct dict parsing from estimatedUsage response (field is estimatedValue)
- estimado_mes: request carries Bearer header + estimatedUsage query (no dates)
- HTTP error (non-2xx) raises via raise_for_status
- GraphQL errors field present raises a clear exception
- Correct date computation: startDate = first day of month T00:00:00Z,
  endDate = hasta + 1 day T00:00:00Z
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from garay.infraestructura.monitor.proveedor_uso_railway_http import ProveedorUsoRailwayHTTP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOKEN = "test-railway-token"
_PROJECT_ID = "test-project-id"
_MEASUREMENTS = ["MEMORY_USAGE_GB", "CPU_USAGE", "NETWORK_TX_GB", "DISK_USAGE_GB"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter(**kwargs: Any) -> ProveedorUsoRailwayHTTP:
    return ProveedorUsoRailwayHTTP(
        api_token=_TOKEN,
        project_id=_PROJECT_ID,
        **kwargs,
    )


def _make_usage_response(items: list[dict[str, Any]]) -> MagicMock:
    """Return a fake httpx.Response for the usage query."""
    resp = MagicMock()
    resp.json.return_value = {"data": {"usage": items}}
    resp.raise_for_status.return_value = None
    return resp


def _make_estimated_response(items: list[dict[str, Any]]) -> MagicMock:
    """Return a fake httpx.Response for the estimatedUsage query."""
    resp = MagicMock()
    resp.json.return_value = {"data": {"estimatedUsage": items}}
    resp.raise_for_status.return_value = None
    return resp


def _make_http_error_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("HTTP 402 Client Error")
    return resp


def _make_graphql_error_response(message: str = "Unauthorized") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"errors": [{"message": message}]}
    return resp


# ---------------------------------------------------------------------------
# uso_mes_a_la_fecha: dict parsing
# ---------------------------------------------------------------------------


def test_uso_mes_a_la_fecha_parses_measurement_to_value() -> None:
    """uso_mes_a_la_fecha returns {measurement: value} from the usage response."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    usage_items = [
        {"measurement": "MEMORY_USAGE_GB", "value": 1234.5},
        {"measurement": "CPU_USAGE", "value": 678.9},
        {"measurement": "NETWORK_TX_GB", "value": 0.5},
        {"measurement": "DISK_USAGE_GB", "value": 100.0},
    ]

    with patch("httpx.post", return_value=_make_usage_response(usage_items)) as mock_post:
        result = adapter.uso_mes_a_la_fecha(hoy)

    assert result == {
        "MEMORY_USAGE_GB": 1234.5,
        "CPU_USAGE": 678.9,
        "NETWORK_TX_GB": 0.5,
        "DISK_USAGE_GB": 100.0,
    }
    mock_post.assert_called_once()


def test_uso_mes_a_la_fecha_empty_list_returns_empty_dict() -> None:
    """uso_mes_a_la_fecha with empty usage list returns empty dict."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_usage_response([])):
        result = adapter.uso_mes_a_la_fecha(hoy)

    assert result == {}


# ---------------------------------------------------------------------------
# uso_mes_a_la_fecha: request shape (header, query, dates)
# ---------------------------------------------------------------------------


def test_uso_mes_a_la_fecha_sends_bearer_auth_header() -> None:
    """uso_mes_a_la_fecha sends Authorization: Bearer <token> header."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_usage_response([])) as mock_post:
        adapter.uso_mes_a_la_fecha(hoy)

    call_kwargs = mock_post.call_args.kwargs
    assert "Authorization" in call_kwargs.get("headers", {})
    assert call_kwargs["headers"]["Authorization"] == f"Bearer {_TOKEN}"


def test_uso_mes_a_la_fecha_sends_correct_iso_dates() -> None:
    """uso_mes_a_la_fecha sends startDate = first day of month T00:00:00Z,
    endDate = (hasta + 1 day) T00:00:00Z in the JSON body."""
    adapter = _make_adapter()
    hasta = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_usage_response([])) as mock_post:
        adapter.uso_mes_a_la_fecha(hasta)

    payload = mock_post.call_args.kwargs.get("json", {})
    variables = payload.get("variables", {})

    assert variables.get("startDate") == "2026-08-01T00:00:00Z"
    assert variables.get("endDate") == "2026-08-17T00:00:00Z"  # hasta + 1 day


def test_uso_mes_a_la_fecha_dates_at_month_start() -> None:
    """startDate stays correct when hasta is already the 1st of the month."""
    adapter = _make_adapter()
    hasta = datetime.date(2026, 8, 1)

    with patch("httpx.post", return_value=_make_usage_response([])) as mock_post:
        adapter.uso_mes_a_la_fecha(hasta)

    variables = mock_post.call_args.kwargs.get("json", {}).get("variables", {})
    assert variables.get("startDate") == "2026-08-01T00:00:00Z"
    assert variables.get("endDate") == "2026-08-02T00:00:00Z"


def test_uso_mes_a_la_fecha_sends_project_id_and_measurements() -> None:
    """uso_mes_a_la_fecha sends projectId and measurements in variables."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_usage_response([])) as mock_post:
        adapter.uso_mes_a_la_fecha(hoy)

    variables = mock_post.call_args.kwargs.get("json", {}).get("variables", {})
    assert variables.get("projectId") == _PROJECT_ID
    assert set(variables.get("measurements", [])) == set(_MEASUREMENTS)


# ---------------------------------------------------------------------------
# estimado_mes: dict parsing (field is estimatedValue, not value)
# ---------------------------------------------------------------------------


def test_estimado_mes_parses_estimated_value_field() -> None:
    """estimado_mes uses 'estimatedValue' (not 'value') to build the dict."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    estimated_items = [
        {"measurement": "MEMORY_USAGE_GB", "estimatedValue": 2000.0},
        {"measurement": "CPU_USAGE", "estimatedValue": 1000.0},
        {"measurement": "NETWORK_TX_GB", "estimatedValue": 1.5},
        {"measurement": "DISK_USAGE_GB", "estimatedValue": 200.0},
    ]

    with patch("httpx.post", return_value=_make_estimated_response(estimated_items)):
        result = adapter.estimado_mes(hoy)

    assert result == {
        "MEMORY_USAGE_GB": 2000.0,
        "CPU_USAGE": 1000.0,
        "NETWORK_TX_GB": 1.5,
        "DISK_USAGE_GB": 200.0,
    }


def test_estimado_mes_empty_list_returns_empty_dict() -> None:
    """estimado_mes with empty estimatedUsage list returns empty dict."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_estimated_response([])):
        result = adapter.estimado_mes(hoy)

    assert result == {}


# ---------------------------------------------------------------------------
# estimado_mes: request shape (no dates)
# ---------------------------------------------------------------------------


def test_estimado_mes_sends_bearer_auth_header() -> None:
    """estimado_mes sends Authorization: Bearer <token> header."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_estimated_response([])) as mock_post:
        adapter.estimado_mes(hoy)

    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs.get("headers", {}).get("Authorization") == f"Bearer {_TOKEN}"


def test_estimado_mes_sends_project_id_no_dates() -> None:
    """estimado_mes sends projectId but no startDate/endDate in variables."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_estimated_response([])) as mock_post:
        adapter.estimado_mes(hoy)

    variables = mock_post.call_args.kwargs.get("json", {}).get("variables", {})
    assert variables.get("projectId") == _PROJECT_ID
    assert "startDate" not in variables
    assert "endDate" not in variables


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_uso_mes_a_la_fecha_raises_on_http_error() -> None:
    """uso_mes_a_la_fecha propagates exceptions from raise_for_status."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with (
        patch("httpx.post", return_value=_make_http_error_response()),
        pytest.raises(Exception, match="HTTP 402"),
    ):
        adapter.uso_mes_a_la_fecha(hoy)


def test_estimado_mes_raises_on_http_error() -> None:
    """estimado_mes propagates exceptions from raise_for_status."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with (
        patch("httpx.post", return_value=_make_http_error_response()),
        pytest.raises(Exception, match="HTTP 402"),
    ):
        adapter.estimado_mes(hoy)


def test_uso_mes_a_la_fecha_raises_on_graphql_errors() -> None:
    """uso_mes_a_la_fecha raises when GraphQL response contains 'errors' field."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with (
        patch("httpx.post", return_value=_make_graphql_error_response("Unauthorized")),
        pytest.raises(Exception, match="Unauthorized"),
    ):
        adapter.uso_mes_a_la_fecha(hoy)


def test_estimado_mes_raises_on_graphql_errors() -> None:
    """estimado_mes raises when GraphQL response contains 'errors' field."""
    adapter = _make_adapter()
    hoy = datetime.date(2026, 8, 16)

    with (
        patch("httpx.post", return_value=_make_graphql_error_response("Unauthorized")),
        pytest.raises(Exception, match="Unauthorized"),
    ):
        adapter.estimado_mes(hoy)


# ---------------------------------------------------------------------------
# Custom timeout propagated
# ---------------------------------------------------------------------------


def test_uso_mes_a_la_fecha_sends_timeout() -> None:
    """uso_mes_a_la_fecha passes a timeout to httpx.post."""
    adapter = _make_adapter(timeout=15.0)
    hoy = datetime.date(2026, 8, 16)

    with patch("httpx.post", return_value=_make_usage_response([])) as mock_post:
        adapter.uso_mes_a_la_fecha(hoy)

    assert mock_post.call_args.kwargs.get("timeout") == 15.0
