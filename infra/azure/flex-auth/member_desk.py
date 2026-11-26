"""Session and read-only directory for the same-origin Flex Desk."""

import base64
import json
from functools import lru_cache
from hmac import digest
from time import monotonic

from cryptography.fernet import Fernet, InvalidToken

from directory_snapshot import current_snapshot_digest, load_snapshot_version, snapshot_container
from member_enrichment import linkedin_path, normalize, public_work_text

PREVIOUS_DESK_COOKIE = "__Host-gmg-flex-desk"
DESK_COOKIE = "__Host-gmg-flex-desk-v2"
DESK_SESSION_AGE = 8 * 60 * 60


def desk_cipher(secret: str) -> Fernet:
    key = digest(secret.encode(), b"gmg-flex-desk-session-v1", "sha256")
    return Fernet(base64.urlsafe_b64encode(key))


def desk_identity(cipher: Fernet, token: str | None) -> dict | None:
    if not token or len(token) > 4096:
        return None
    try:
        identity = json.loads(cipher.decrypt(token, ttl=DESK_SESSION_AGE))
    except (InvalidToken, ValueError):
        return None
    if not isinstance(identity, dict) or not isinstance(identity.get("rosterKey"), str):
        return None
    sub = identity.get("sub")
    return identity if isinstance(sub, str) and 1 <= len(sub) <= 200 else None


def _profile(member: dict) -> dict | None:
    name = public_work_text(member.get("name"))
    if not name:
        return None
    experiences = member.get("work_experiences")
    work = experiences[0] if isinstance(experiences, list) and experiences and isinstance(experiences[0], dict) else {}
    link = linkedin_path(member.get("profile_url_linkedin"))
    return {
        "name": name,
        "location": ", ".join(filter(None, (public_work_text(member.get(field)) for field in ("current-city", "current-state", "current-country")))),
        "role": public_work_text(work.get("designation")),
        "company": public_work_text(work.get("company")),
        "summary": public_work_text(member.get("_gmg_linkedin_profile_summary")),
        "linkedin": f"https://www.linkedin.com/{link}/" if link else "",
    }


@lru_cache(maxsize=1)
def _manifest(_minute: int) -> str:
    return current_snapshot_digest(snapshot_container())


@lru_cache(maxsize=1)
def published_snapshot(version: str) -> dict:
    return load_snapshot_version(snapshot_container(), version)


def published_version() -> str:
    return _manifest(int(monotonic() // 60))


@lru_cache(maxsize=1)
def _index(version: str) -> dict[str, list[dict]]:
    by_name = {}
    for member in published_snapshot(version)["users"]:
        if card := _profile(member):
            by_name.setdefault(normalize(card["name"]), []).append(card)
    return by_name


def exact_members(name: str) -> list[dict]:
    """Load the published version before rendering a Desk capable of searching it."""
    return _index(published_version()).get(normalize(name), [])[:10]
