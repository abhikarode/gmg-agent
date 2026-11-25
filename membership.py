"""Match verified LinkedIn emails to the operator-published GMG membership roster."""

import hashlib
import hmac
import json
import os
import re
from functools import lru_cache
from time import monotonic

from directory_snapshot import read_blob, snapshot_container

ROSTER = "membership.json"
MAX_ROSTER_BYTES = 4 * 1024 * 1024


def normalize_email(value: object) -> str:
    email = value.strip().lower() if isinstance(value, str) else ""
    return email if len(email) <= 254 and re.fullmatch(r"[^\s@,;]+@[^\s@,;]+\.[a-z]{2,}", email) else ""


def _email_key(email: str, secret: str) -> str:
    if not secret:
        raise ValueError("Configure the internal token before using the membership roster.")
    return hmac.digest(secret.encode(), b"gmg-membership-v1\0" + email.encode(), "sha256").hex()


def build_roster(users: list[dict], secret: str, aliases: dict[str, str] | None = None) -> dict:
    """Use the source roster for active status and hold shared or ambiguous addresses."""
    active = set()
    candidates: dict[str, set[str]] = {}
    for user in users:
        member_id = user.get("unique_profile_id")
        if (not isinstance(member_id, str) or not 1 <= len(member_id) <= 200
                or user.get("aunthentication_status") != "authenticated"
                or str(user.get("year-of-leaving")) != "0000"):
            continue
        active.add(member_id)
        secondary = user.get("secondary_emails")
        for raw in [user.get("primary_email"), *(secondary if isinstance(secondary, list) else [])]:
            if email := normalize_email(raw):
                candidates.setdefault(email, set()).add(member_id)
    for raw, member_id in (aliases or {}).items():
        email = normalize_email(raw)
        if not email or member_id not in active:
            raise ValueError("A membership email alias must name an active member.")
        candidates.setdefault(email, set()).add(member_id)
    entries = {_email_key(email, secret): next(iter(ids)) for email, ids in candidates.items() if len(ids) == 1}
    return {"version": 1, "keyCheck": _email_key("gmg-roster-key-check", secret), "entries": entries}


def decode_roster(contents: bytes, secret: str) -> dict[str, str]:
    roster = json.loads(contents)
    entries = roster.get("entries") if isinstance(roster, dict) and roster.get("version") == 1 else None
    check = roster.get("keyCheck") if isinstance(roster, dict) else None
    if (not isinstance(check, str) or not hmac.compare_digest(check, _email_key("gmg-roster-key-check", secret))
        or not isinstance(entries, dict) or not entries or any(
        not re.fullmatch(r"[a-f0-9]{64}", key) or not isinstance(value, str) or not 1 <= len(value) <= 200
        for key, value in entries.items()
    )):
        raise ValueError("Invalid GMG membership roster.")
    return entries


def member_id_for(email: str, entries: dict[str, str], secret: str) -> str | None:
    normalized = normalize_email(email)
    return entries.get(_email_key(normalized, secret)) if normalized else None


@lru_cache(maxsize=1)
def _roster(_period: int, secret: str) -> dict[str, str]:
    connection = os.getenv("GMG_BLOB_CONNECTION_STRING")
    return decode_roster(read_blob(snapshot_container(connection), ROSTER, MAX_ROSTER_BYTES), secret)


def lookup_member(email: str, secret: str) -> str | None:
    return member_id_for(email, _roster(int(monotonic() // 30), secret), secret)


def roster_lookup_key(email: object, secret: str) -> str | None:
    normalized = normalize_email(email)
    return _email_key(normalized, secret) if normalized else None


def lookup_member_key(key: str, secret: str) -> str | None:
    return _roster(int(monotonic() // 30), secret).get(key)


def expertise_key(member_id: str) -> str:
    return hashlib.sha256(member_id.encode()).hexdigest()
