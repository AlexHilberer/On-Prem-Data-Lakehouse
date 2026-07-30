from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import requests


class AirflowClient:
    def __init__(
        self,
        base_url: str,
        dag_id: str,
        session: requests.Session | None = None,
        timeout: int = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.dag_id = dag_id
        self.session = session or requests.Session()
        self.timeout = timeout

    def authenticate(self, username: str, password: str) -> str:
        response = self.session.post(
            f"{self.base_url}/auth/token",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def trigger(self, token: str, rows: int | None, seed: int) -> dict:
        headers = self._headers(token)
        unpause_response = self.session.patch(
            f"{self.base_url}/api/v2/dags/{self.dag_id}",
            headers=headers,
            json={"is_paused": False},
            timeout=self.timeout,
        )
        unpause_response.raise_for_status()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"control-{timestamp}-{uuid4().hex[:8]}"
        response = self.session.post(
            f"{self.base_url}/api/v2/dags/{self.dag_id}/dagRuns",
            headers=headers,
            json={
                "dag_run_id": run_id,
                "logical_date": None,
                "conf": {"rows": rows or 0, "seed": seed},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def list_runs(self, token: str, limit: int = 20) -> list[dict]:
        response = self.session.get(
            f"{self.base_url}/api/v2/dags/{self.dag_id}/dagRuns",
            headers=self._headers(token),
            params=[("limit", str(limit)), ("order_by", "-run_after")],
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("dag_runs", [])

    def list_tasks(self, token: str, run_id: str) -> list[dict]:
        response = self.session.get(
            f"{self.base_url}/api/v2/dags/{self.dag_id}/dagRuns/{run_id}/taskInstances",
            headers=self._headers(token),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("task_instances", [])

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}
