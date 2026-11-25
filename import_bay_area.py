"""Preview or build the local Bay Area member overlay from the three source workbooks."""

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from member_enrichment import (
    BAY_AREA_CITIES, DEFAULT_OVERLAY, compatible_bay_area_location, linkedin_path,
    missing, normalize, public_work_text,
)


LINKEDIN_HEADERS = (
    "First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On",
)
ENRICHMENT_HEADERS = ("Bay Area Email", "Email Match Status", "Other Bay Area Emails")


def email_key(value: object) -> str:
    email = str(value or "").strip().casefold()
    return email if re.fullmatch(r"[^\s@,;]+@[^\s@,;]+\.[a-z]{2,}", email) else ""


def read_rows(path: Path, headers: tuple = ()) -> list[tuple]:
    from openpyxl import load_workbook

    book = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        sheet = book["LinkedIn Matches"] if headers else book["Sheet1"]
        rows = sheet.iter_rows(values_only=True, max_col=len(headers) or 5)
        if headers and next(rows, None) != headers:
            raise ValueError("Workbook headers do not match the expected source format.")
        return [row for row in rows if any(value is not None for value in row)]
    finally:
        book.close()


def index_rows(rows: list, key) -> dict[str, set[int]]:
    index = defaultdict(set)
    for i, row in enumerate(rows):
        value = key(row)
        if value:
            index[value].add(i)
    return index


def build_overlay(users: list[dict], contacts: list[tuple], profiles: list[tuple],
                  email_review: list[tuple]) -> tuple[dict, dict]:
    review = {linkedin_path(row[2]): row for row in email_review}
    profile_links = index_rows(profiles, lambda row: linkedin_path(row[2]))
    if (len(profiles) != len(email_review) or len(review) != len(email_review)
            or len(profile_links) != len(profiles)
            or any(review.get(linkedin_path(row[2]), ())[:7] != row for row in profiles)):
        raise ValueError("The two LinkedIn workbooks must contain the same original profile rows.")

    member_emails = index_rows(users, lambda member: email_key(member.get("primary_email")))
    member_links = index_rows(users, lambda member: linkedin_path(member.get("profile_url_linkedin")))
    member_ids = Counter(str(member.get("unique_profile_id") or "") for member in users)
    export_emails = index_rows(profiles, lambda row: email_key(row[3]))
    raw_emails = index_rows(contacts, lambda row: email_key(row[1]))
    stats = Counter({
        "member_rows": len(users), "linkedin_rows": len(profiles), "raw_rows": len(contacts),
        "linkedin_matches": 0, "linkedin_conflicts": 0, "work": 0, "linkedin": 0, "city": 0,
    })
    proposals = defaultdict(list)

    for row in profiles:
        link, email = linkedin_path(row[2]), email_key(row[3])
        link_hits = member_links.get(link, set())
        email_hits = member_emails.get(email, set())
        direct_hits = link_hits | email_hits
        if not direct_hits:
            continue
        joined_hits = member_emails.get(email_key(review[link][7]), set())
        if len(direct_hits) != 1 or joined_hits - direct_hits:
            stats["linkedin_conflicts"] += 1
            continue
        if not link_hits and len(export_emails.get(email, ())) != 1:
            continue
        i = next(iter(direct_hits))
        existing_link = linkedin_path(users[i].get("profile_url_linkedin"))
        if existing_link and existing_link != link:
            stats["linkedin_conflicts"] += 1
            continue
        proposals[i].append(row)

    updates = {}
    for i, rows in proposals.items():
        member = users[i]
        member_id = str(member.get("unique_profile_id") or "")
        if not member_id or member_ids[member_id] != 1 or len(rows) != 1:
            stats["linkedin_conflicts"] += len(rows)
            continue
        stats["linkedin_matches"] += 1
        row = rows[0]
        changes = {}
        company, title = public_work_text(row[4]), public_work_text(row[5])
        if company and title:
            changes["linkedin_work"] = {"company": company, "designation": title}
            stats["profile_summaries"] += 1
        if not member.get("work_experiences") and company and title:
            changes.update(company=company, title=title)
            stats["work"] += 1
        if missing(member.get("profile_url_linkedin")):
            changes["linkedin"] = f"https://www.linkedin.com/{linkedin_path(row[2])}"
            stats["linkedin"] += 1
        if changes:
            updates[member_id] = changes

    for email, source_rows in raw_emails.items():
        targets = member_emails.get(email, ())
        if len(source_rows) != 1 or len(targets) != 1:
            continue
        member = users[next(iter(targets))]
        member_id = str(member.get("unique_profile_id") or "")
        city = contacts[next(iter(source_rows))][3]
        if (member_id and member_ids[member_id] == 1 and missing(member.get("current-city"))
                and isinstance(city, str) and normalize(city) in BAY_AREA_CITIES
                and compatible_bay_area_location(member)):
            updates.setdefault(member_id, {})["city"] = city.strip()
            stats["city"] += 1

    stats["updated_members"] = len(updates)
    return {"version": 1, "members": updates}, dict(stats)


def write_overlay(path: Path, overlay: dict) -> None:
    temporary = None
    try:
        with NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as output:
            temporary = Path(output.name)
            json.dump(overlay, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contacts", type=Path, required=True)
    parser.add_argument("--linkedin", type=Path, required=True)
    parser.add_argument("--email-review", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=Path("almashines_data.json"))
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OVERLAY))
    parser.add_argument("--apply", action="store_true", help="Write the overlay. Default: preview.")
    args = parser.parse_args()
    sources = (args.snapshot, args.contacts, args.linkedin, args.email_review)
    if args.output.resolve() in {file.resolve() for file in sources}:
        parser.error("The output must differ from every input file.")
    users = json.loads(args.snapshot.read_text(encoding="utf-8"))["users"]
    if not isinstance(users, list) or not users:
        parser.error("The AlmaShines snapshot must contain members.")
    overlay, stats = build_overlay(
        users, read_rows(args.contacts), read_rows(args.linkedin, LINKEDIN_HEADERS),
        read_rows(args.email_review, LINKEDIN_HEADERS + ENRICHMENT_HEADERS),
    )
    if args.apply:
        write_overlay(args.output, overlay)
    print(json.dumps({"mode": "apply" if args.apply else "preview", **stats}, indent=2))


if __name__ == "__main__":
    main()
