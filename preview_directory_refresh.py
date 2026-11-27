#!/usr/bin/env python3
"""Compare local AlmaShines exports and print a counts-only preview."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Import the directory helpers without writing a bytecode cache.
sys.dont_write_bytecode = True
from member_enrichment import linkedin_path, missing


class PreviewParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse diagnostics can echo raw argument values.
        self.exit(2, "arguments: ArgumentError (expected four input flags and paths)\n")


def array_field(document, field):
    if not isinstance(document, dict) or not isinstance(document.get(field), list):
        raise ValueError
    return document[field]


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def export_links(document):
    links = {}
    for row in array_field(document, "users"):
        if not isinstance(row, dict):
            raise ValueError
        member_id = row.get("unique_profile_id")
        url = row.get("profile_url_linkedin")
        if not nonblank(member_id) or member_id in links:
            raise ValueError
        if url is not None and not isinstance(url, str):
            raise ValueError
        if missing(url):
            links[member_id] = ("blank", "")
        elif path := linkedin_path(url):
            links[member_id] = ("valid", path)
        else:
            links[member_id] = ("malformed", url.strip())
    return links


def pilot_ids(document, baseline):
    ids = array_field(document, "member_ids")
    if not ids or any(not nonblank(item) or item not in baseline for item in ids):
        raise ValueError
    if len(set(ids)) != len(ids):
        raise ValueError
    return ids


def manual_paths(document):
    members = array_field(document, "members")
    version = document.get("version")
    if type(version) is not int or version != 1:
        raise ValueError
    paths = set()
    for member in members:
        if not isinstance(member, dict) or not nonblank(member.get("name")):
            raise ValueError
        url = member.get("linkedin")
        path = linkedin_path(url) if isinstance(url, str) else ""
        if not path or path in paths:
            raise ValueError
        paths.add(path)
    return paths


def pilot_status(previous, current, matches):
    if current is None:
        return "removed"
    kind, path = current
    if kind != "valid":
        return kind
    if matches[path] > 1:
        return "shared"
    if current == previous:
        return "unchanged"
    return "changed" if previous[0] == "valid" else "gained"


def preview(baseline, candidate, ids, manual):
    matches = Counter(path for kind, path in candidate.values() if kind == "valid")
    pilot = dict.fromkeys(
        ("unchanged", "gained", "changed", "blank", "malformed", "shared", "removed"), 0
    )
    for member_id in ids:
        pilot[pilot_status(baseline[member_id], candidate.get(member_id), matches)] += 1

    outside = dict.fromkeys(("changed", "added", "removed"), 0)
    for member_id in (baseline.keys() | candidate.keys()) - set(ids):
        previous = baseline.get(member_id)
        current = candidate.get(member_id)
        if current == previous:
            continue
        if previous is None or (current and current[0] == "valid" and previous[0] != "valid"):
            outside["added"] += 1
        elif current is None or (previous[0] == "valid" and current[0] != "valid"):
            outside["removed"] += 1
        else:
            outside["changed"] += 1

    additions = dict.fromkeys(("retained", "matched", "conflict"), 0)
    for path in manual:
        additions[("retained", "matched", "conflict")[min(matches[path], 2)]] += 1

    return {
        "schema_version": 1,
        "pilot": {"total": len(ids), **pilot},
        "outside_pilot": outside,
        "manual": {"total": len(manual), **additions},
    }


def main():
    parser = PreviewParser(description=__doc__, allow_abbrev=False)
    for flag in ("baseline", "candidate", "pilot-ids", "manual-additions"):
        parser.add_argument(f"--{flag}", required=True, type=Path)
    args = parser.parse_args()

    inputs = {}
    for label, path, validate in (
        ("baseline", args.baseline, export_links),
        ("candidate", args.candidate, export_links),
        ("pilot-ids", args.pilot_ids, lambda document: pilot_ids(document, inputs["baseline"])),
        ("manual-additions", args.manual_additions, manual_paths),
    ):
        try:
            inputs[label] = validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, RecursionError) as error:
            print(f"{label}: {type(error).__name__}", file=sys.stderr)
            return 2

    print(json.dumps(preview(
        inputs["baseline"], inputs["candidate"], inputs["pilot-ids"], inputs["manual-additions"]
    )))
    return 0


if __name__ == "__main__":
    sys.exit(main())
