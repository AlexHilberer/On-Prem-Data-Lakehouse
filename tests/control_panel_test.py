import importlib.util
import pathlib
import unittest

import requests


MODULE_PATH = pathlib.Path(__file__).parents[1] / "control-panel" / "airflow_client.py"
SPEC = importlib.util.spec_from_file_location("airflow_client", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AirflowClient = MODULE.AirflowClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _call(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        return self._call("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._call("PATCH", url, **kwargs)

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)


class AirflowClientTest(unittest.TestCase):
    def test_authenticate_returns_token(self):
        session = FakeSession([FakeResponse({"access_token": "jwt-token"})])
        client = AirflowClient("http://airflow-api:8080/", "retail", session=session)

        token = client.authenticate("bob.engineer", "secret")

        self.assertEqual(token, "jwt-token")
        self.assertEqual(
            session.calls[0][2]["json"],
            {"username": "bob.engineer", "password": "secret"},
        )
        self.assertEqual(session.calls[0][2]["timeout"], 10)

    def test_trigger_unpauses_dag_and_sends_parameters(self):
        session = FakeSession(
            [
                FakeResponse({"is_paused": False}),
                FakeResponse({"dag_run_id": "control-run", "state": "queued"}),
            ]
        )
        client = AirflowClient("http://airflow-api:8080", "retail", session=session)

        result = client.trigger("jwt-token", 750, 99)

        self.assertEqual(result["state"], "queued")
        self.assertEqual(session.calls[0][0], "PATCH")
        self.assertEqual(session.calls[0][2]["json"], {"is_paused": False})
        trigger_payload = session.calls[1][2]["json"]
        self.assertTrue(trigger_payload["dag_run_id"].startswith("control-"))
        self.assertIsNone(trigger_payload["logical_date"])
        self.assertEqual(trigger_payload["conf"], {"rows": 750, "seed": 99})

    def test_lists_runs_and_tasks(self):
        session = FakeSession(
            [
                FakeResponse({"dag_runs": [{"dag_run_id": "run-1"}]}),
                FakeResponse({"task_instances": [{"task_id": "generate"}]}),
            ]
        )
        client = AirflowClient("http://airflow-api:8080", "retail", session=session)

        self.assertEqual(client.list_runs("jwt"), [{"dag_run_id": "run-1"}])
        self.assertEqual(
            client.list_tasks("jwt", "run-1"),
            [{"task_id": "generate"}],
        )
        self.assertEqual(
            session.calls[0][2]["params"],
            [("limit", "20"), ("order_by", "-run_after")],
        )

    def test_http_errors_are_not_hidden(self):
        session = FakeSession([FakeResponse({}, status_code=403)])
        client = AirflowClient("http://airflow-api:8080", "retail", session=session)

        with self.assertRaises(requests.HTTPError):
            client.list_runs("jwt")


if __name__ == "__main__":
    unittest.main()
