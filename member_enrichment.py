"""Apply local directory records and field-limited enrichment to AlmaShines data."""

import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit


BAY_AREA_CITIES = frozenset("""
Alameda|Albany|Antioch|Atherton|Belmont|Belvedere|Benicia|Berkeley|
Brentwood|Brisbane|Burlingame|Campbell|Castro Valley|Clayton|Colma|Concord|
Corte Madera|Cupertino|Daly City|Danville|Dublin|East Palo Alto|El Cerrito|
Emeryville|Fairfax|Fairfield|Foster City|Fremont|Gilroy|Half Moon Bay|Hayward|
Hercules|Hillsborough|Lafayette|Larkspur|Livermore|Los Altos|Los Altos Hills|
Los Gatos|Martinez|Menlo Park|Mill Valley|Millbrae|Milpitas|Moraga|Morgan Hill|
Mountain View|Napa|Newark|Novato|Oakland|Oakley|Orinda|Pacifica|Palo Alto|
Petaluma|Piedmont|Pinole|Pittsburg|Pleasant Hill|Pleasanton|Portola Valley|
Redwood City|Richmond|Rohnert Park|Ross|San Anselmo|San Bruno|San Carlos|
San Francisco|San Jose|San Leandro|San Lorenzo|San Mateo|
San Pablo|San Rafael|San Ramon|Santa Clara|Santa Rosa|Saratoga|Sausalito|
Sebastopol|Sonoma|South San Francisco|Suisun City|Sunnyvale|Tiburon|
Union City|Vacaville|Vallejo|Walnut Creek|Woodside
""".replace("\n", "").casefold().split("|"))

DEFAULT_OVERLAY = "bay_area_enrichment.json"
logger = logging.getLogger(__name__)


def normalize(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def missing(value: object) -> bool:
    return normalize(value) in {"", "n/a", "na", "unknown", "none", "-", "not available"}


def compatible_bay_area_location(member: dict) -> bool:
    state, country = member.get("current-state"), member.get("current-country")
    return (missing(state) or normalize(state) in {"ca", "california"}) and (
        missing(country) or normalize(country).replace(".", "") in {
            "us", "usa", "united states", "united states of america"
        }
    )


def linkedin_path(value: object) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    try:
        parts = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    if (parts.scheme not in {"http", "https"} or parts.username or parts.password
            or (host != "linkedin.com" and not host.endswith(".linkedin.com"))):
        return ""
    clean = parts.path.strip("/").lower()
    return clean if re.fullmatch(r"(?:in|pub)/[a-z0-9_%.-]+(?:/[a-z0-9_%.-]+)*", clean) else ""


def public_work_text(value: object) -> str:
    if not isinstance(value, str) or missing(value):
        return ""
    value = value.strip()
    if (len(value) > 120 or not value.isprintable() or re.search(r"[@<>]|https?://|www\.", value, re.I)
            or sum(c.isdigit() for c in value) >= 7):
        return ""
    return value


def official_evidence_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 300:
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    hosts = {"www.garjemarathi.com", "garjemarathi.com", "www.maai-foundation.org", "maai-foundation.org", "luma.com"}
    if (parts.scheme == "https" and parts.netloc in hosts and value.isprintable()
            and not any(character.isspace() or character in "<>\")'(" for character in value)):
        return value
    return ""


def _directory_text(value: object) -> str:
    text = public_work_text(value)
    return "" if re.search(r"[\\\x60*_\[\]#]", text) else " ".join(text.split())


def load_directory_additions(users: list[dict], path: Path) -> None:
    """Load operator-approved profiles without changing the source snapshot."""
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, ValueError):
        logger.warning("Could not load local directory additions.")
        return
    if not isinstance(content, dict) or content.get("version") != 1 or not isinstance(content.get("members"), list):
        logger.warning("Invalid local directory additions schema.")
        return

    known_links: dict[str, list[dict]] = defaultdict(list)
    for member in users:
        if link := linkedin_path(member.get("profile_url_linkedin")):
            known_links[link].append(member)
    loaded_links = set()
    for entry in content["members"]:
        if not isinstance(entry, dict):
            continue
        name = _directory_text(entry.get("name"))
        link = linkedin_path(entry.get("linkedin"))
        if not name or not link or link in loaded_links:
            continue
        loaded_links.add(link)
        matches = known_links[link]
        if len(matches) > 1:
            continue
        if matches:
            member = matches[0]
        else:
            member = {
                "unique_profile_id": f"gmg-directory:linkedin:{link}",
                "name": name,
                "profile_url_linkedin": f"https://www.linkedin.com/{link}/",
                "current-city": "",
                "current-state": "",
                "current-country": "",
                "_gmg_enrichment_sources": {"linkedin": "GMG app directory"},
            }
            users.append(member)
        if summary := _directory_text(entry.get("linkedin_profile_summary")):
            member["_gmg_linkedin_profile_summary"] = summary


def load_enrichment(users: list[dict], path: Path) -> None:
    """Merge an allowlisted overlay at startup without importing contact fields."""
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, ValueError):
        logger.warning("Could not load Bay Area enrichment. Using the base member directory.")
        return
    if not isinstance(content, dict) or content.get("version") != 1 or not isinstance(content.get("members"), dict):
        logger.warning("Invalid Bay Area enrichment schema. Using the base member directory.")
        return

    ids = Counter(str(member.get("unique_profile_id") or "") for member in users)
    for member in users:
        member_id = str(member.get("unique_profile_id") or "")
        if not member_id or ids[member_id] != 1:
            continue
        fields = content["members"].get(member_id)
        if not isinstance(fields, dict):
            continue
        sources = {}
        company = public_work_text(fields.get("company"))
        title = public_work_text(fields.get("title"))
        linkedin_work = fields.get("linkedin_work")
        if isinstance(linkedin_work, dict):
            export_company = public_work_text(linkedin_work.get("company"))
            export_title = public_work_text(linkedin_work.get("designation"))
            if export_company and export_title:
                member["_gmg_linkedin_work"] = {"company": export_company, "designation": export_title}
        experience = fields.get("professional_evidence")
        if isinstance(experience, dict):
            description = public_work_text(experience.get("text"))
            source = public_work_text(experience.get("source"))
            url = official_evidence_url(experience.get("url"))
            if description and source and url:
                member["_gmg_professional_evidence"] = {"text": description, "source": source, "url": url}
        if not member.get("work_experiences") and company and title:
            member["work_experiences"] = [{"company": company, "designation": title}]
            sources["work"] = "LinkedIn export"
        link = linkedin_path(fields.get("linkedin"))
        if missing(member.get("profile_url_linkedin")) and link:
            member["profile_url_linkedin"] = f"https://www.linkedin.com/{link}"
            verified_source = (member.get("_gmg_professional_evidence") or {}).get("source")
            sources["linkedin"] = verified_source if verified_source and fields.get("linkedin_source") == verified_source else "LinkedIn export"
        city = fields.get("city")
        if (isinstance(city, str) and normalize(city) in BAY_AREA_CITIES
                and missing(member.get("current-city")) and compatible_bay_area_location(member)):
            member["current-city"] = city.strip()
            sources["city"] = "Bay Area contact list"
        if sources:
            member["_gmg_enrichment_sources"] = sources
