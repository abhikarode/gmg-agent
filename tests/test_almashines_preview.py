"""Offline regression tests using the synthetic inputs from GMG issue #1."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "preview_directory_refresh.py"
FLAGS = ("baseline", "candidate", "pilot-ids", "manual-additions")

GUARD = """
import os, runpy, sys

def guard(event, args):
    blocked = event.startswith(("socket.", "os.exec", "os.posix_spawn", "subprocess."))
    blocked |= event in {
        "os.system", "os.fork", "os.forkpty", "os.remove", "os.rename",
        "os.mkdir", "os.rmdir", "os.chmod", "os.chown", "os.link",
        "os.symlink", "os.truncate", "os.utime", "os.setxattr", "os.removexattr",
        "ctypes.dlopen",
    }
    if event == "open" and isinstance(args[2], int):
        blocked |= bool(args[2] & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        ))
    if blocked:
        print("PREVIEW_GUARD_DENIED", file=sys.stderr)
        raise RuntimeError("Preview attempted a network, process, or write operation")

sys.addaudithook(guard)
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(sys.argv[0]))
runpy.run_path(sys.argv[0], run_name="__main__")
"""

EXPECTED = {
    "schema_version": 1,
    "pilot": {
        "total": 25, "unchanged": 19, "gained": 1, "changed": 1,
        "blank": 1, "malformed": 1, "shared": 1, "removed": 1,
    },
    "outside_pilot": {"changed": 1, "added": 1, "removed": 1},
    "manual": {"total": 3, "retained": 1, "matched": 1, "conflict": 1},
}


def profile(slug):
    return f"https://www.linkedin.com/in/{slug}/"


def row(member_id, url):
    return {
        "unique_profile_id": member_id,
        "name": "Preview Synthetic Person",
        "primary_email": "preview-canary@example.test",
        "profile_url_linkedin": url,
    }


def fixture():
    ids = [f"gmg-fixture-{i:02d}" for i in range(1, 26)]
    old = {"users": [row(member_id, profile(member_id)) for member_id in ids]}
    old["users"][0]["profile_url_linkedin"] = " N/A "
    old["users"].extend([
        row("gmg-fixture-outside-shared", profile("gmg-fixture-shared")),
        row("gmg-fixture-outside-changed", profile("gmg-fixture-outside-old")),
        row("gmg-fixture-outside-removed", None),
        row("gmg-fixture-outside-equivalent", profile("gmg-fixture-outside-equivalent")),
        row("gmg-fixture-outside-blank", None),
    ])
    new = copy.deepcopy(old)
    updates = [
        profile(ids[0]),
        "http://LINKEDIN.COM/in/GMG-FIXTURE-02/?tracking=synthetic",
        profile("gmg-fixture-new-slug"),
        None,
        "https://invalid.example.test/in/gmg-fixture-05/",
        profile("gmg-fixture-shared"),
    ]
    for item, url in zip(new["users"], updates):
        item["profile_url_linkedin"] = url
    del new["users"][3]["profile_url_linkedin"]
    del new["users"][6]
    new["users"] = [
        item for item in new["users"]
        if item["unique_profile_id"] != "gmg-fixture-outside-removed"
    ]
    new["users"][-3]["profile_url_linkedin"] = profile("gmg-fixture-outside-new")
    new["users"][-2]["profile_url_linkedin"] = (
        "http://LINKEDIN.COM/in/GMG-FIXTURE-OUTSIDE-EQUIVALENT?trk=synthetic"
    )
    new["users"][-1]["profile_url_linkedin"] = "None"
    new["users"].append(row("gmg-fixture-outside-added", None))
    manual = {
        "version": 1,
        "members": [
            {"name": f"Preview Synthetic Manual {n}", "linkedin": profile(slug)}
            for n, slug in enumerate(["gmg-fixture-manual", ids[1], "gmg-fixture-shared"])
        ],
    }
    return [old, new, {"member_ids": ids}, manual]


def counts_only(value):
    if isinstance(value, dict):
        return all(counts_only(item) for item in value.values())
    return type(value) is int


class PreviewTests(unittest.TestCase):
    def run_preview(self, documents, *, guarded=False):
        with tempfile.TemporaryDirectory(prefix="gmg-preview-test-") as temporary:
            root = Path(temporary)
            args = []
            for flag, document in zip(FLAGS, documents, strict=True):
                path = root / f"{flag}.json"
                if document is not None:
                    path.write_text(
                        document if isinstance(document, str) else json.dumps(document),
                        encoding="utf-8",
                    )
                args.extend([f"--{flag}", str(path)])

            def snapshot():
                return {
                    item.name: (item.read_bytes(), item.stat().st_mtime_ns)
                    for item in root.iterdir()
                }

            before = snapshot()
            command = [sys.executable, "-B", "-c", GUARD] if guarded else [sys.executable]
            result = subprocess.run(
                [*command, str(CLI), *args],
                cwd=root,
                env={"HOME": temporary, "PATH": os.defpath, "PYTHONUTF8": "1"},
                capture_output=True,
                text=True,
                timeout=10,
            )
            # AC-003.5
            self.assertEqual(snapshot(), before)
            combined = (result.stdout + result.stderr).lower()
            # AC-003.6
            self.assertNotIn("preview_guard_denied", combined)
            # AC-003.4
            for canary in (
                "gmg-fixture-", "preview synthetic", "preview-canary", "http://",
                "https://", str(root).lower(),
            ):
                self.assertNotIn(canary, combined)
            return result

    def success(self, documents, *, guarded=False):
        result = self.run_preview(documents, guarded=guarded)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def test_source_harness(self):
        # AC-001.1 AC-003.1 AC-005.3
        documents = fixture()
        first = self.success(documents, guarded=True)
        report = json.loads(first)
        self.assertTrue(counts_only(report))
        self.assertEqual(report, EXPECTED)

        total = report["pilot"]["total"]
        # AC-002.13
        self.assertEqual(sum(v for k, v in report["pilot"].items() if k != "total"), total)

        reordered = copy.deepcopy(documents)
        for document, key in zip(reordered, ("users", "users", "member_ids", "members")):
            document[key].reverse()
        # AC-003.3
        self.assertEqual(self.success(reordered, guarded=True), first)

        old, new, pilot, manual = documents
        # AC-001.14 AC-003.2
        one = self.success([old, new, {"member_ids": pilot["member_ids"][:1]}, manual],
                           guarded=True)
        self.assertEqual(json.loads(one)["pilot"], {
            "total": 1, "unchanged": 0, "gained": 1, "changed": 0,
            "blank": 0, "malformed": 0, "shared": 0, "removed": 0,
        })
        print("PASS: 25-member preview, variable cohort, redaction, and offline read-only checks")

    def test_pilot_statuses(self):
        old, new, pilot, manual = fixture()
        cases = (
            ("AC-002.1", 6, "removed"),
            ("AC-002.2", 3, "blank"),
            ("AC-002.3", 4, "malformed"),
            ("AC-002.4", 5, "shared"),
            ("AC-002.5", 1, "unchanged"),
            ("AC-002.6", 2, "changed"),
            ("AC-002.7", 0, "gained"),
        )
        for criterion, index, status in cases:
            with self.subTest(criterion=criterion):
                cohort = {"member_ids": [pilot["member_ids"][index]]}
                report = json.loads(self.success([old, new, cohort, manual]))
                expected = dict.fromkeys(EXPECTED["pilot"], 0)
                expected["total"] = expected[status] = 1
                self.assertEqual(report["pilot"], expected)

    def test_manual_statuses(self):
        old, new, pilot, manual = fixture()
        cases = (
            ("AC-002.10", "retained"),
            ("AC-002.11", "matched"),
            ("AC-002.12", "conflict"),
        )
        for member, (criterion, status) in zip(manual["members"], cases, strict=True):
            with self.subTest(criterion=criterion):
                additions = {"version": 1, "members": [member]}
                report = json.loads(self.success([old, new, pilot, additions]))
                expected = dict.fromkeys(EXPECTED["manual"], 0)
                expected["total"] = expected[status] = 1
                self.assertEqual(report["manual"], expected)

    def test_input_validation(self):
        old, new, pilot, manual = fixture()
        member_id = pilot["member_ids"][0]
        cases = [
            ("AC-001.2", 0, None, "FileNotFoundError"),
            ("missing candidate", 1, None, "FileNotFoundError"),
            ("invalid JSON", 1, '{"users": ["gmg-fixture-bad-json"', "JSONDecodeError"),
            ("AC-001.3", 1, {"profiles": []}, "ValueError"),
            ("AC-001.4 baseline", 0, {"users": [old["users"][0]] * 2}, "ValueError"),
            ("AC-001.4 candidate", 1, {"users": [new["users"][0]] * 2}, "ValueError"),
            ("missing ID", 1, {"users": [{"name": "Preview Synthetic Missing ID"}]}, "ValueError"),
            ("AC-001.5", 1, {"users": [row("  ", None)]}, "ValueError"),
            ("AC-001.6", 1, {"users": [row(member_id, 10)]}, "ValueError"),
            ("AC-001.7", 2, {"member_ids": [member_id, member_id]}, "ValueError"),
            ("AC-001.8", 2, {"member_ids": ["gmg-fixture-nonexistent"]}, "ValueError"),
            ("AC-001.9", 2, {"member_ids": []}, "ValueError"),
            ("AC-001.10 float", 3, {**manual, "version": 1.0}, "ValueError"),
            ("AC-001.10 bool", 3, {**manual, "version": True}, "ValueError"),
            ("AC-001.10 wrong version", 3, {**manual, "version": 2}, "ValueError"),
            ("AC-001.11", 3, {"version": 1, "members": [
                {**manual["members"][0], "name": "  "},
            ]}, "ValueError"),
            ("invalid manual URL", 3, {"version": 1, "members": [
                {**manual["members"][0], "linkedin": ""},
            ]}, "ValueError"),
            ("AC-001.12", 3, {"version": 1, "members": [
                manual["members"][0],
                {"name": "Preview Synthetic Duplicate",
                 "linkedin": "http://LINKEDIN.COM/in/GMG-FIXTURE-MANUAL?trk=synthetic"},
            ]}, "ValueError"),
        ]
        for label, index, value, error in cases:
            with self.subTest(label=label):
                documents = [old, new, pilot, manual]
                documents[index] = value
                result = self.run_preview(documents, guarded=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, f"{FLAGS[index]}: {error}\n")

    def test_empty_manual_and_unrelated_fields(self):
        documents = fixture()
        original = self.success(documents)
        old, new, pilot, manual = documents
        old["exported_at"] = "2000-01-01T00:00:00Z"
        new["users"][0]["unrelated"] = {"anything": True}
        manual["members"][0]["unrelated"] = ["descriptive field"]
        # AC-001.15
        self.assertEqual(self.success(documents), original)
        manual["members"].clear()
        # AC-001.13
        self.assertEqual(json.loads(self.success(documents))["manual"], {
            "total": 0, "retained": 0, "matched": 0, "conflict": 0,
        })
        # AC-003.2: Also check the complete report when nothing changes.
        self.assertEqual(json.loads(self.success([old, old, pilot, manual])), {
            "schema_version": 1,
            "pilot": {
                "total": 25, "unchanged": 24, "gained": 0, "changed": 0,
                "blank": 1, "malformed": 0, "shared": 0, "removed": 0,
            },
            "outside_pilot": {"changed": 0, "added": 0, "removed": 0},
            "manual": {"total": 0, "retained": 0, "matched": 0, "conflict": 0},
        })

    def test_outside_link_transitions(self):
        old = {"users": [
            row("gmg-fixture-pilot", "not a URL"),
            row("gmg-fixture-add", None),
            row("gmg-fixture-lose", profile("lose")),
            row("gmg-fixture-change", profile("before")),
            row("gmg-fixture-malformed", "invalid URL"),
        ]}
        new = {"users": [
            row("gmg-fixture-pilot", profile("pilot")),
            row("gmg-fixture-add", profile("add")),
            row("gmg-fixture-lose", "N/A"),
            row("gmg-fixture-change", profile("after")),
            row("gmg-fixture-malformed", "  invalid URL  "),
        ]}
        report = json.loads(self.success([
            old, new, {"member_ids": ["gmg-fixture-pilot"]}, {"version": 1, "members": []},
        ]))
        # AC-002.8 AC-002.9
        self.assertEqual(report["outside_pilot"], {"added": 1, "removed": 1, "changed": 1})
        # AC-002.7 also covers a malformed baseline URL.
        self.assertEqual(report["pilot"]["gained"], 1)

    def test_readme_contract(self):
        # AC-003.7
        section = (ROOT / "README.md").read_text(encoding="utf-8").split(
            "### Preview AlmaShines LinkedIn URL changes"
        )[1].split("\n## ")[0]
        for flag in FLAGS:
            self.assertIn(f"--{flag}", section)
        self.assertIn("Exit `0`", section)
        self.assertIn("Exit `2`", section)
        report = json.loads(section.split("```json\n")[1].split("```")[0])
        self.assertEqual(report, EXPECTED)


# AC-004.2 AC-005.1: This module runs under the requested unittest discovery command.
# AC-004.1 AC-005.2: The repository verifier runs this module through unittest discovery.
if __name__ == "__main__":
    unittest.main()
