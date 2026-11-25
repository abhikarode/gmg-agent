import json
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from api import readiness
from expertise import LABELS, save_topics
from membership import build_roster, decode_roster, expertise_key, member_id_for
from people_match import PeopleIndex


def member(record_id, email, *, status="authenticated", leaving="0000"):
    return {"unique_profile_id": record_id, "primary_email": email,
            "aunthentication_status": status, "year-of-leaving": leaving}


class MembershipTests(unittest.TestCase):
    def test_maps_active_unique_match_and_confirmed_aliases(self):
        source = [member("one", "Active@example.test"), member("inactive", "left@example.test", leaving="2026"),
                  member("incomplete", "pending@example.test", status="incomplete"),
                  member("two", "duplicate@example.test"), member("three", "duplicate@example.test")]
        payload = json.dumps(build_roster(source, "fixture", {"Alias@example.test": "one"})).encode()
        self.assertNotIn(b"@example.test", payload)
        entries = decode_roster(payload, "fixture")
        for email in (" ACTIVE@example.test ", "alias@example.test"):
            self.assertEqual(member_id_for(email, entries, "fixture"), "one")
        for email in ("left@example.test", "pending@example.test", "duplicate@example.test",
                      "active+unconfirmed@example.test"):
            self.assertIsNone(member_id_for(email, entries, "fixture"))
        with self.assertRaises(ValueError):
            decode_roster(payload, "wrong-key")

    def test_alias_cannot_bypass_inactive_member_or_an_existing_match(self):
        users = [member("one", "one@example.test"), member("two", "two@example.test"),
                 member("former", "former@example.test", leaving="2025")]
        with self.assertRaises(ValueError):
            build_roster(users, "fixture", {"alias@example.test": "former"})
        entries = build_roster(users, "fixture", {"two@example.test": "one"})["entries"]
        self.assertIsNone(member_id_for("two@example.test", entries, "fixture"))


class ExpertiseTests(unittest.TestCase):
    @patch("expertise.table_client")
    def test_only_catalog_ids_can_be_saved_and_cleared(self, table_client):
        key = expertise_key("member-1")
        storage = table_client.return_value = Mock()
        with self.assertRaises(ValueError):
            save_topics(key, ["made-up-topic"])
        storage.upsert_entity.assert_not_called()
        self.assertEqual(save_topics(key, ["robotics", "robotics"]), ["robotics"])
        self.assertEqual(storage.upsert_entity.call_args.args[0]["RowKey"], key)
        self.assertEqual(save_topics(key, []), [])
        self.assertEqual(json.loads(storage.upsert_entity.call_args.args[0]["Topics"]), [])

    def test_member_topics_are_searchable_with_clear_provenance(self):
        index = PeopleIndex([{"name": "Member", "_gmg_member_expertise": [LABELS["robotics"]]}])
        match = index.retrieve(["robotics"], "")[0]
        self.assertEqual(match.evidence[0].source, "Member-reported expertise")


class ReadinessTests(unittest.TestCase):
    @patch.dict("os.environ", {"GMG_EXPERTISE_TABLE_CONNECTION_STRING": "configured"})
    @patch("api.get_data_store")
    @patch("api.lookup_member")
    @patch("api.get_people_index")
    @patch("api.expertise_entries")
    def test_readiness_validates_directory_and_roster_before_lazy_search(
        self, entries, recommend_index, membership_lookup, data_store,
    ):
        data_store.return_value.get_users.return_value = [{"name": "Member"}]
        self.assertEqual(readiness(), {"status": "ready"})
        membership_lookup.assert_called_once()
        recommend_index.assert_not_called()
        entries.assert_not_called()

        membership_lookup.side_effect = ValueError("Invalid roster")
        with self.assertRaises(HTTPException) as rejected:
            readiness()
        self.assertEqual(rejected.exception.status_code, 503)

        membership_lookup.reset_mock()
        data_store.return_value.get_users.return_value = []
        with self.assertRaises(HTTPException) as rejected:
            readiness()
        self.assertEqual(rejected.exception.status_code, 503)
        membership_lookup.assert_not_called()
