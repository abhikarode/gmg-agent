from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from import_bay_area import build_overlay, write_overlay
from member_enrichment import load_directory_additions, load_enrichment


def member(identifier, email, *, link=None, city=None, experience=None):
    return {
        "unique_profile_id": identifier,
        "primary_email": email,
        "profile_url_linkedin": link,
        "current-city": city,
        "work_experiences": experience or [],
    }


class EnrichmentTests(unittest.TestCase):
    def test_local_additions_preserve_snapshot_records_and_deduplicate_by_profile(self):
        original = member("canonical", "private@example.test",
                          link="https://www.linkedin.com/in/existing", city="Oakland")
        rows = [deepcopy(original)]
        addition = {
            "name": "New Member", "linkedin": "https://www.linkedin.com/in/new-member/",
            "email": "private@example.test", "current-city": "Oakland",
            "linkedin_profile_summary": "Builds open-source tools for engineers.",
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "members.json"
            path.write_text(json.dumps({"version": 1, "members": [
                {"name": "Overlapping", "linkedin": "https://linkedin.com/in/existing/?utm_source=test"},
                {"name": "Invalid", "linkedin": "https://example.test/in/new-member"},
                addition, addition,
            ]}), encoding="utf-8")
            load_directory_additions(rows, path)
            load_directory_additions(rows, path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], original)
        self.assertEqual(rows[1]["name"], "New Member")
        self.assertEqual(rows[1]["profile_url_linkedin"], addition["linkedin"])
        self.assertEqual(rows[1]["current-city"], "")
        self.assertEqual(rows[1]["_gmg_linkedin_profile_summary"], addition["linkedin_profile_summary"])
        self.assertNotIn("email", rows[1])

    def test_reviewed_profile_summary_can_follow_a_unique_canonical_link(self):
        rows = [member("canonical", "private@example.test",
                       link="https://www.linkedin.com/in/example", city="Oakland")]
        data = {"version": 1, "members": [{
            "name": "Example Member",
            "linkedin": "https://www.linkedin.com/in/example/",
            "linkedin_profile_summary": "Builds tools for designers.",
        }]}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "members.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            load_directory_additions(rows, path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["unique_profile_id"], "canonical")
        self.assertEqual(rows[0]["_gmg_linkedin_profile_summary"], "Builds tools for designers.")

    def test_direct_matches_only_and_no_email_persistence(self):
        users = [
            member("match", "direct@example.test"),
            member("mismatch", "other@example.test", link="https://www.linkedin.com/in/other"),
            member("existing", "existing@example.test", city="Oakland",
                   experience=[{"company": "Directory Employer", "designation": "Designer"}]),
        ]
        profiles = [
            ("A", "Person", "https://linkedin.com/in/direct", "direct@example.test", "Company", "Engineer", None),
            ("B", "Person", "https://linkedin.com/in/other", None, "Other", "Designer", None),
            ("C", "Person", "https://linkedin.com/in/unmatched", None, "New", "Manager", None),
            ("D", "Person", "https://linkedin.com/in/existing", "existing@example.test", "Overwrite", "Manager", None),
        ]
        reviews = [
            profiles[0] + (None, None, None),
            profiles[1] + ("direct@example.test", None, None),
            profiles[2] + ("other@example.test", None, None),
            profiles[3] + (None, None, None),
        ]
        contacts = [
            ("A Person", "direct@example.test", None, "San Jose", None),
            ("D Person", "existing@example.test", None, "San Ramon", None),
        ]
        overlay, stats = build_overlay(users, contacts, profiles, reviews)

        self.assertEqual(stats["linkedin_conflicts"], 1)
        self.assertEqual(stats["work"], 1)
        self.assertEqual(stats["city"], 1)
        self.assertNotIn("example.test", json.dumps(overlay))
        self.assertNotIn("mismatch", overlay["members"])
        with TemporaryDirectory() as directory:
            output = Path(directory) / "overlay.json"
            write_overlay(output, overlay)
            load_enrichment(users, output)
        self.assertEqual(users[0]["current-city"], "San Jose")
        self.assertEqual(users[0]["work_experiences"][0]["designation"], "Engineer")
        self.assertEqual(users[0]["_gmg_linkedin_work"]["designation"], "Engineer")
        self.assertEqual(users[2]["current-city"], "Oakland")
        self.assertEqual(users[2]["work_experiences"][0]["company"], "Directory Employer")
        self.assertEqual(users[2]["_gmg_linkedin_work"]["company"], "Overwrite")

    def test_duplicate_and_injected_fields_are_excluded_at_runtime(self):
        users = [
            member("duplicate", "a@example.test"),
            member("duplicate", "b@example.test"),
            member("safe", "original@example.test"),
        ]
        overlay = {"version": 1, "members": {
            "duplicate": {"city": "San Jose"},
            "safe": {
                "primary_email": "unapproved@example.test", "company": "bad@example.test",
                "title": "Engineer", "linkedin": "https://attacker.example/in/profile",
            },
        }}
        with TemporaryDirectory() as directory:
            output = Path(directory) / "overlay.json"
            write_overlay(output, overlay)
            original = deepcopy(users)
            load_enrichment(users, output)
            self.assertEqual(users, original)
            output.write_text("invalid", encoding="utf-8")
            with self.assertLogs("member_enrichment", level="WARNING"):
                load_enrichment(users, output)
            self.assertEqual(users, original)

    def test_altered_original_columns_are_rejected(self):
        profile = ("A", "Person", "https://linkedin.com/in/direct", None, "Company", "Engineer", None)
        review = profile[:4] + ("Different company",) + profile[5:] + (None, None, None)
        with self.assertRaisesRegex(ValueError, "same original profile rows"):
            build_overlay([], [], [profile], [review])
