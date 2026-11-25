"""Publish a field-limited directory from local AlmaShines and enrichment files."""

import argparse
import json
import os
import re
from pathlib import Path

from azure.identity import AzureCliCredential

from ai_agent import job_description, job_location, job_text
from directory_snapshot import activate_snapshot, publish_snapshot, snapshot_container
from membership import ROSTER, build_roster, decode_roster
from member_enrichment import (
    linkedin_path, load_directory_additions, load_enrichment, official_evidence_url, public_work_text,
)


def select_text(record: dict, fields: tuple[str, ...]) -> dict:
    return {field: value for field in fields if (value := public_work_text(record.get(field)))}


def member_record(member: dict) -> dict:
    member_id = member.get("unique_profile_id")
    if not isinstance(member_id, str) or not member_id.strip():
        raise ValueError("A source member is missing a stable ID.")
    record = {"unique_profile_id": member_id.strip()}
    record.update(select_text(member, (
        "name", "first_name", "last_name", "current-city", "current-state",
        "current-country", "Specialization", "_gmg_linkedin_profile_summary",
    )))
    if isinstance(member.get("role"), int):
        record["role"] = member["role"]
    if link := linkedin_path(member.get("profile_url_linkedin")):
        record["profile_url_linkedin"] = f"https://www.linkedin.com/{link}/"
    work = member.get("work_experiences")
    if isinstance(work, list):
        record["work_experiences"] = [
            item for entry in work if isinstance(entry, dict)
            and (item := select_text(entry, ("company", "designation")))
        ]
    for key, fields in (
        ("_gmg_linkedin_work", ("company", "designation")),
        ("_gmg_enrichment_sources", ("linkedin", "work", "city")),
    ):
        if isinstance(member.get(key), dict) and (value := select_text(member[key], fields)):
            record[key] = value
    evidence = member.get("_gmg_professional_evidence")
    if isinstance(evidence, dict) and (url := official_evidence_url(evidence.get("url"))):
        text = select_text(evidence, ("text", "source"))
        if len(text) == 2:
            record["_gmg_professional_evidence"] = {**text, "url": url}
    if member.get("profile_pic") or member.get("has_profile_photo"):
        record["has_profile_photo"] = True
    return record


def job_record(job: dict) -> dict:
    description = job_description(job.get("description"))
    description = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "", description)
    description = re.sub(r"(?<!\w)\+?\d(?:[ .()\-]*\d){7,}(?!\w)", "", description)
    return {
        "designation": job_text(job.get("designation")),
        "company": job_text(job.get("company")),
        "job_type": job_text(job.get("job_type")),
        "location": job_location(job),
        "description": description,
    }


def read_records(path: Path, key: str) -> list[dict]:
    source = json.loads(path.read_text(encoding="utf-8"))
    records = source.get(key) if isinstance(source, dict) else None
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValueError(f"Invalid {key} list in directory input.")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    seed = commands.add_parser("seed")
    for option in ("members", "jobs", "enrichment", "additions"):
        seed.add_argument(f"--{option}", type=Path, required=option == "members")
    access = commands.add_parser("membership")
    access.add_argument("--members", type=Path, required=True)
    access.add_argument("--aliases", type=Path, help="Private JSON object mapping confirmed emails to active member IDs")
    commands.add_parser("activate").add_argument("sha256")
    args = parser.parse_args()
    connection = os.getenv("GMG_BLOB_CONNECTION_STRING")
    credential = AzureCliCredential() if os.getenv("GMG_BLOB_ACCOUNT_URL") else None
    if args.operation == "activate":
        activate_snapshot(snapshot_container(connection, credential=credential), args.sha256)
        print(f"Activated snapshot {args.sha256}")
        return
    if args.operation == "membership":
        users = read_records(args.members, "users")
        aliases = json.loads(args.aliases.read_text(encoding="utf-8")) if args.aliases else {}
        secret = os.environ["GMG_INTERNAL_TOKEN"]
        contents = json.dumps(build_roster(users, secret, aliases)).encode()
        entries = decode_roster(contents, secret)
        snapshot_container(connection, credential=credential).upload_blob(ROSTER, contents, overwrite=True)
        print(f"Published {len(entries)} eligible email mappings for {len(set(entries.values()))} active members.")
        if connection and os.getenv("GMG_EXPERTISE_TABLE_CONNECTION_STRING"):
            from azure.core.exceptions import ResourceExistsError
            from expertise import table_client
            try:
                table_client().create_table()
            except ResourceExistsError:
                pass
        return
    users = read_records(args.members, "users")
    source_count = len(users)
    jobs = read_records(args.jobs, "jobs") if args.jobs else []
    if args.enrichment:
        load_enrichment(users, args.enrichment)
    if args.additions:
        load_directory_additions(users, args.additions)
    snapshot = {"users": [member_record(user) for user in users], "jobs": [job_record(job) for job in jobs]}
    digest = publish_snapshot(connection, snapshot, credential=credential)
    print(f"Published {digest}: {source_count} source members, {len(users)} directory members, {len(jobs)} jobs.")


if __name__ == "__main__":
    main()
