import hashlib
import hmac
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from azure.data.tables import TableServiceClient
from fastapi.testclient import TestClient

from api import app
from whatsapp_pilot import Pilot, answer_for, inbound_texts, reserve_reply


PILOT = Pilot("test-signing-key", "test-verification-key", "test-send-token", "12345",
              frozenset({"16505550100"}), "https://example.test/login", "v27.0", 3)
AUTH = {"Authorization": "Bearer test-internal"}


def event(message=None, **data):
    message = message or {"from": "16505550100", "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                          "id": "wamid.fixture-1", "type": "text", "text": {"body": "How do I sign in?"}}
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": PILOT.phone_number_id}, "messages": [message], **data,
    }}]}]}


class WhatsAppTests(unittest.TestCase):
    def test_replies_send_members_to_desk_and_do_not_repeat_user_text(self):
        for text, expected in [("how do I log in?", "verified primary LinkedIn email"),
                               ("update my skills", "My expertise"), ("find a mentor", "Find people"),
                               ("what is GMG", "Garje Marathi Global"), ("लॉगिन", "सत्यापित")]:
            reply = answer_for(text, PILOT.desk_url)
            self.assertIn(expected, reply)
            self.assertIn(PILOT.desk_url, reply)
        self.assertNotIn("person@example.test", answer_for("show person@example.test", PILOT.desk_url))

    def test_only_fresh_direct_text_for_the_configured_number_can_send(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(len(list(inbound_texts(event(), PILOT, now))), 1)
        message = event()["entry"][0]["changes"][0]["value"]["messages"][0]
        bad_messages = [{**message, **override} for override in [
            {"from": "16505550101"}, {"group_id": "group"}, {"timestamp": str(int(now.timestamp()) - 901)},
            {"type": "image"}, {"timestamp": 0}, {"id": {}}, {"text": {"body": " "}},
        ]]
        for payload in [*(event(m) for m in bad_messages), event(group_id="group"), event(metadata={}),
                        event(messages=[]), {"object": "whatsapp_business_account", "entry": [None]}]:
            self.assertEqual(list(inbound_texts(payload, PILOT, now)), [])

    @patch("api.handle_inbound")
    @patch("api.configured_pilot", return_value=PILOT)
    @patch("api.INTERNAL_TOKEN", "test-internal")
    def test_webhook_signature_challenge_and_size(self, _pilot, handler):
        client = TestClient(app)
        challenge = {"mode": "subscribe", "token": PILOT.verify_token, "challenge": "357"}
        self.assertEqual(client.post("/api/whatsapp-verify", json=challenge).status_code, 401)
        verified = client.post("/api/whatsapp-verify", json=challenge, headers=AUTH)
        self.assertEqual((verified.status_code, verified.text), (200, "357"))
        self.assertEqual(client.post("/api/whatsapp-verify", json={**challenge, "token": "wrong"}, headers=AUTH).status_code, 403)
        raw = json.dumps(event()).encode()
        headers = {**AUTH, "X-Hub-Signature-256": "sha256=" + hmac.digest(PILOT.app_secret.encode(), raw, "sha256").hex()}
        self.assertEqual(client.post("/api/whatsapp", content=raw + b" ", headers=headers).status_code, 401)
        self.assertEqual(client.post("/api/whatsapp", content=b" " * 65537, headers=headers).status_code, 413)
        handler.assert_not_called()
        self.assertEqual(client.post("/api/whatsapp", content=raw, headers=headers).status_code, 200)
        handler.assert_called_once_with(json.loads(raw), PILOT)

    @patch("whatsapp_pilot.requests.post")
    @patch("whatsapp_pilot.reply_table")
    @patch("whatsapp_pilot.reserve_reply", side_effect=[True, False])
    def test_provider_send_is_inbound_only_and_duplicate_is_ignored(self, _reserve, _table, post):
        from whatsapp_pilot import handle_inbound
        post.return_value.status_code = 200
        payload = event()
        handle_inbound(payload, PILOT)
        handle_inbound(payload, PILOT)
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["json"]["recipient_type"], "individual")
        self.assertEqual(post.call_args.kwargs["json"]["to"], "16505550100")
        self.assertIn(PILOT.desk_url, post.call_args.kwargs["json"]["text"]["body"])


@unittest.skipUnless(os.getenv("GMG_TEST_TABLE_CONNECTION_STRING"), "Azurite Table endpoint not configured")
class WhatsAppLedgerTests(unittest.TestCase):
    def test_duplicate_concurrency_cap_restart_and_rollover(self):
        with TableServiceClient.from_connection_string(os.environ["GMG_TEST_TABLE_CONNECTION_STRING"]) as store:
            name = "whatsapp" + uuid4().hex
            table = store.create_table(name)
            self.addCleanup(store.close)
            try:
                with ThreadPoolExecutor(max_workers=8) as pool:
                    attempted = list(pool.map(lambda _n: reserve_reply(table, "wamid.same", "2026-11", 2), range(8)))
                self.assertEqual(sum(attempted), 1)
                restarted = store.get_table_client(name)
                self.assertTrue(reserve_reply(restarted, "wamid.second", "2026-11", 2))
                self.assertFalse(reserve_reply(restarted, "wamid.third", "2026-11", 2))
                self.assertFalse(reserve_reply(restarted, "wamid.same", "2026-12", 2))
                self.assertTrue(reserve_reply(restarted, "wamid.third", "2026-12", 2))
                self.assertFalse(reserve_reply(restarted, "wamid.second", "2026-12", 2))
                row = restarted.get_entity("gmg-whatsapp", "reply-ledger")
                self.assertEqual(json.loads(row["Current"]), [hashlib.sha256(b"wamid.third").hexdigest()])
            finally:
                store.delete_table(name)
