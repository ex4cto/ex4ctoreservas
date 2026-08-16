"""HTTP adapter: Railway GraphQL API implementation of ProveedorUsoRailway.

Queries the Railway GraphQL v2 endpoint to retrieve actual and estimated
resource usage amounts for a given project.  Results are returned as plain
``dict[str, float]`` mappings from measurement name to amount, matching the
contract defined by the port.

GraphQL endpoint: https://backboard.railway.com/graphql/v2
Auth: Authorization: Bearer <api_token>

Measurements requested: MEMORY_USAGE_GB, CPU_USAGE, NETWORK_TX_GB, DISK_USAGE_GB

usage query:
    usage(projectId, startDate, endDate, measurements) -> [{measurement, value}]
    DateTime format: YYYY-MM-DDT00:00:00Z

estimatedUsage query:
    estimatedUsage(projectId, measurements) -> [{measurement, estimatedValue}]
    NOTE: field is estimatedValue (not value); no date arguments.
"""

from __future__ import annotations

import datetime
from typing import Any

import httpx

from garay.dominio.puertos.proveedor_uso_railway import ProveedorUsoRailway

_GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"
_DEFAULT_TIMEOUT = 10.0

# All four Railway measurements relevant to cost computation.
_MEASUREMENTS = ["MEMORY_USAGE_GB", "CPU_USAGE", "NETWORK_TX_GB", "DISK_USAGE_GB"]

_USAGE_QUERY = """
query GetUsage(
  $projectId: String
  $startDate: DateTime!
  $endDate: DateTime!
  $measurements: [MetricMeasurement!]!
) {
  usage(
    projectId: $projectId
    startDate: $startDate
    endDate: $endDate
    measurements: $measurements
  ) {
    measurement
    value
  }
}
"""

_ESTIMATED_USAGE_QUERY = """
query GetEstimatedUsage(
  $projectId: String
  $measurements: [MetricMeasurement!]!
) {
  estimatedUsage(
    projectId: $projectId
    measurements: $measurements
  ) {
    measurement
    estimatedValue
  }
}
"""


class ProveedorUsoRailwayHTTP(ProveedorUsoRailway):
    """Fetch Railway resource usage via the Railway GraphQL v2 API.

    Mirrors the httpx usage pattern from ResendAdapter: synchronous
    ``httpx.post`` with ``raise_for_status()`` and a configurable timeout.
    GraphQL-level errors (``errors`` field in response) also raise.
    """

    def __init__(
        self,
        api_token: str,
        project_id: str,
        base_url: str = _GRAPHQL_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_token = api_token
        self._project_id = project_id
        self._base_url = base_url
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_token}"}

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a GraphQL POST and return the parsed JSON body.

        Raises:
            httpx.HTTPStatusError: on non-2xx HTTP response.
            RuntimeError: when the GraphQL response includes an ``errors`` field.
        """
        response = httpx.post(
            self._base_url,
            headers=self._headers(),
            json={"query": query, "variables": variables},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if "errors" in payload:
            messages = "; ".join(e.get("message", str(e)) for e in payload["errors"])
            raise RuntimeError(f"Railway GraphQL error: {messages}")
        return payload

    def uso_mes_a_la_fecha(self, hasta: datetime.date) -> dict[str, float]:
        """Return actual usage from the 1st of *hasta*'s month through *hasta*.

        startDate = first day of the month at T00:00:00Z
        endDate   = (hasta + 1 day) at T00:00:00Z — so *hasta* is fully included.
        """
        start = hasta.replace(day=1)
        end = hasta + datetime.timedelta(days=1)

        variables: dict[str, Any] = {
            "projectId": self._project_id,
            "startDate": f"{start.isoformat()}T00:00:00Z",
            "endDate": f"{end.isoformat()}T00:00:00Z",
            "measurements": _MEASUREMENTS,
        }
        payload = self._post(_USAGE_QUERY, variables)
        items: list[dict[str, Any]] = payload.get("data", {}).get("usage", [])
        return {item["measurement"]: float(item["value"]) for item in items}

    def estimado_mes(self, hoy: datetime.date) -> dict[str, float]:
        """Return projected usage for the current billing period.

        Uses the ``estimatedUsage`` query — no date arguments, field is
        ``estimatedValue`` (not ``value``).
        """
        variables: dict[str, Any] = {
            "projectId": self._project_id,
            "measurements": _MEASUREMENTS,
        }
        payload = self._post(_ESTIMATED_USAGE_QUERY, variables)
        items: list[dict[str, Any]] = payload.get("data", {}).get("estimatedUsage", [])
        return {item["measurement"]: float(item["estimatedValue"]) for item in items}
