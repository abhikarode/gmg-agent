import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from uuid import uuid4

from azure.core.exceptions import ServiceRequestError
from azure.data.tables import TableServiceClient

from directory_snapshot import snapshot_container
from hosted_inference import MODEL, MODEL_LABEL, HostedModelUnavailable, HostedInference, inference_status
from inference_budget import COUNTER_PARTITION, InferenceBudget, InferenceBudgetUnavailable
from people_match import MatchUnavailable, PeopleIndex, recommend


class HostedInferenceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.status = 200
        self.result = {"choices": [{"finish_reason": "stop", "message": {"content": '{"terms":["AI"]}'}}]}
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.calls.append((self.path, self.headers["Authorization"], body))
                self.send_response(test.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Location", "/other-endpoint")
                self.end_headers()
                self.wfile.write(json.dumps(test.result).encode())

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join)
        self.addCleanup(server.shutdown)
        self.budget = Mock(spec=InferenceBudget)
        self.token = Mock(return_value="fixture-token")
        self.adapter = HostedInference("https://gmg-test.services.ai.azure.com", self.budget, self.token)
        path = self.adapter.url.split(".com", 1)[1]
        self.adapter.url = f"http://127.0.0.1:{server.server_port}{path}"

    def test_foundry_contract_redacts_contacts_and_caps_output(self):
        self.budget.reserve.side_effect = lambda: self.assertEqual(self.calls, [])
        result = self.adapter.complete(
            "Return JSON", "Marathi AI mentor name@example.com +1 650 555 1234 https://www.linkedin.com/in/sample/",
            800, 2, {"type": "object"},
        )
        self.assertEqual(json.loads(result), {"terms": ["AI"]})
        path, auth, body = self.calls[0]
        self.assertEqual(path, "/openai/v1/chat/completions")
        self.assertEqual(auth, "Bearer fixture-token")
        self.assertEqual(body["model"], MODEL)
        self.assertEqual(inference_status.get(), MODEL_LABEL)
        self.assertEqual(body["max_completion_tokens"], 500)
        self.assertEqual(body["reasoning_effort"], "none")
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(body["messages"][1]["content"], "Marathi AI mentor [email] [phone] [link]")

    def test_budget_exhaustion_and_storage_error_send_no_request(self):
        for error in (InferenceBudgetUnavailable(), ServiceRequestError("emulated storage outage")):
            self.budget.reserve.side_effect = error
            with self.assertRaises(HostedModelUnavailable):
                self.adapter.complete("Answer", "short request", 200, 2)
        self.assertEqual(self.calls, [])
        self.token.assert_not_called()

    def test_paused_inference_is_reported_and_sends_no_request(self):
        status = inference_status.set("directory")
        self.addCleanup(inference_status.reset, status)
        self.budget.reserve.side_effect = InferenceBudgetUnavailable("Hosted inference is paused.")
        with self.assertRaises(HostedModelUnavailable):
            self.adapter.complete("Answer", "short request", 200, 2)
        self.assertEqual(inference_status.get(), "inference paused")
        self.token.assert_not_called()
        self.assertEqual(self.calls, [])

    @patch("inference_budget.quota_table_from_environment")
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_live_allowance_defaults_to_paused(self, quota_table):
        budget = InferenceBudget.from_environment()
        with self.assertRaisesRegex(InferenceBudgetUnavailable, "Hosted inference is paused"):
            budget.reserve()
        quota_table.return_value.get_entity.assert_not_called()

    def test_grant_deadline_prevents_inference_even_with_unused_allowance(self):
        table = Mock()
        with patch("inference_budget.datetime", wraps=datetime) as clock:
            cutoff = datetime(2027, 11, 1, tzinfo=timezone.utc)
            clock.now.return_value = cutoff
            budget = InferenceBudget(table, 100, 2000, cutoff)
            with self.assertRaisesRegex(InferenceBudgetUnavailable, "Hosted inference is paused"):
                budget.reserve()
        self.assertEqual(table.mock_calls, [])

    def test_input_ceiling_rejects_before_reservation(self):
        with self.assertRaises(HostedModelUnavailable):
            self.adapter.complete("Answer", "म" * 1500, 200, 2)
        self.budget.reserve.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_provider_failure_does_not_retry_or_refund(self):
        self.status = 307
        with self.assertRaises(HostedModelUnavailable):
            self.adapter.complete("Answer", "short request", 200, 2)
        self.budget.reserve.assert_called_once()
        self.assertEqual(len(self.calls), 1)

    def test_truncated_response_is_unavailable(self):
        self.result["choices"][0]["finish_reason"] = "length"
        with self.assertRaises(HostedModelUnavailable):
            self.adapter.complete("Answer", "short request", 200, 2)


class StorageAuthenticationTests(unittest.TestCase):
    @patch("directory_snapshot.BlobServiceClient")
    @patch("directory_snapshot.runtime_identity")
    def test_cloud_directory_uses_managed_identity(self, identity, blob):
        endpoint = "https://gmgrehearsal.blob.core.windows.net"
        with patch.dict(os.environ, {"GMG_BLOB_ACCOUNT_URL": endpoint}):
            snapshot_container()
            with self.assertRaises(ValueError):
                snapshot_container("shared-key-connection")
        self.assertEqual(blob.call_args.args, (endpoint,))
        self.assertIs(blob.call_args.kwargs["credential"], identity.return_value)
        blob.from_connection_string.assert_not_called()

    @patch("inference_budget.TableClient")
    @patch("inference_budget.runtime_identity")
    def test_cloud_counter_uses_managed_identity(self, identity, table):
        endpoint = "https://gmgrehearsal.table.core.windows.net"
        with patch.dict(os.environ, {"GMG_QUOTA_TABLE_URL": endpoint}, clear=True):
            InferenceBudget.from_environment()
        self.assertEqual(table.call_args.args, (endpoint,))
        self.assertIs(table.call_args.kwargs["credential"], identity.return_value)
        table.from_connection_string.assert_not_called()


class DirectoryFallbackTests(unittest.TestCase):
    def test_unavailable_planner_keeps_explicit_location_filter(self):
        index = PeopleIndex([
            {"name": "Bay Member", "current-city": "Sunnyvale", "current-country": "USA",
             "Specialization": "Robotics"},
            {"name": "Mumbai Member", "current-city": "Mumbai", "current-country": "India",
             "Specialization": "Robotics"},
        ])
        unavailable = Mock(side_effect=MatchUnavailable)
        result = recommend(index, "Find robotics professionals in Mumbai", "", MODEL, unavailable,
                           fallback_on_plan_failure=True)
        self.assertEqual(result.ranking, "directory")
        self.assertEqual([member.name for member in result.members], ["Mumbai Member"])
        unavailable.assert_called_once()


@unittest.skipUnless(os.getenv("GMG_TEST_TABLE_CONNECTION_STRING"), "Azurite Table endpoint not configured")
class AzuriteBudgetTests(unittest.TestCase):
    def test_shared_counter_with_contention_restart_and_utc_rollover(self):
        with TableServiceClient.from_connection_string(os.environ["GMG_TEST_TABLE_CONNECTION_STRING"]) as service:
            name = f"gmgtest{uuid4().hex}"
            table = service.create_table(name)
            try:
                current = datetime(2026, 11, 22, tzinfo=timezone.utc)

                def reserve(_index):
                    try:
                        InferenceBudget(service.get_table_client(name), 4, 5)._reserve(current)
                    except InferenceBudgetUnavailable:
                        return False
                    return True

                with ThreadPoolExecutor(max_workers=12) as pool:
                    self.assertEqual(sum(pool.map(reserve, range(12))), 4)
                restarted = InferenceBudget(service.get_table_client(name), 4, 5)
                with self.assertRaises(InferenceBudgetUnavailable):
                    restarted._reserve(current)
                restarted._reserve(current.replace(day=23))
                with self.assertRaises(InferenceBudgetUnavailable):
                    restarted._reserve(current.replace(day=23))
                with self.assertRaises(InferenceBudgetUnavailable):
                    restarted._reserve(current.replace(day=24))
                restarted._reserve(current.replace(month=12, day=1))
                self.assertEqual(table.get_entity(COUNTER_PARTITION, "2026-11")["Calls"], 5)
                self.assertEqual(table.get_entity(COUNTER_PARTITION, "2026-12")["Calls"], 1)
            finally:
                service.delete_table(name)
