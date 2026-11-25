"""Small inbound-only WhatsApp help desk for enrolled GMG pilot testers."""

import hashlib
import hmac
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlsplit

import requests
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from inference_budget import quota_table_from_environment

MAX_WEBHOOK_BYTES = 64 * 1024
MAX_REPLY_ATTEMPTS = 200
MAX_EVENT_AGE_SECONDS = 900
PHONE = re.compile(r"[1-9][0-9]{6,14}")
MESSAGE_ID = re.compile(r"wamid\.[A-Za-z0-9+.=_/-]{1,250}")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pilot:
    app_secret: str = field(repr=False)
    verify_token: str = field(repr=False)
    access_token: str = field(repr=False)
    phone_number_id: str
    testers: frozenset[str] = field(repr=False)
    desk_url: str
    graph_version: str
    monthly_limit: int


def configured_pilot() -> Pilot | None:
    if os.getenv("GMG_WHATSAPP_ENABLED") != "1":
        return None
    app_secret, verify_token, access_token = (
        os.getenv(f"GMG_WHATSAPP_{name}", "") for name in ("APP_SECRET", "VERIFY_TOKEN", "ACCESS_TOKEN")
    )
    testers = frozenset(number.strip().lstrip("+") for number in os.getenv("GMG_WHATSAPP_TESTERS", "").split(","))
    phone = os.getenv("GMG_WHATSAPP_PHONE_NUMBER_ID", "")
    desk = os.getenv("GMG_WHATSAPP_DESK_URL", "")
    version = os.getenv("GMG_WHATSAPP_GRAPH_VERSION", "v27.0")
    limit = int(os.getenv("GMG_WHATSAPP_MONTHLY_LIMIT", "100"))
    url = urlsplit(desk)
    if (not all((app_secret, verify_token, access_token)) or not re.fullmatch(r"[0-9]{5,30}", phone)
            or not 1 <= len(testers) <= 5 or not all(PHONE.fullmatch(number) for number in testers)
            or url.scheme != "https" or not url.hostname or url.username or url.password
            or url.path != "/login" or url.query or url.fragment or any(char.isspace() for char in desk)
            or not re.fullmatch(r"v[0-9]{2}\.0", version) or not 1 <= limit <= MAX_REPLY_ATTEMPTS):
        raise ValueError("Invalid WhatsApp pilot configuration")
    return Pilot(app_secret, verify_token, access_token, phone, testers, desk, version, limit)


def valid_signature(pilot: Pilot, raw_body: bytes, signature: str) -> bool:
    if not re.fullmatch(r"sha256=[a-f0-9]{64}", signature):
        return False
    expected = hmac.digest(pilot.app_secret.encode(), raw_body, "sha256").hex()
    return hmac.compare_digest(signature, f"sha256={expected}")


def answer_for(text: str, desk: str) -> str:
    question = " ".join(text.casefold().split())
    marathi = bool(re.search(r"[\u0900-\u097f]", question))
    if re.search(r"sign[ -]?in|log[ -]?in|log[ -]?on|linkedin|access|blocked|denied|लॉगिन|प्रवेश", question):
        reply = (
            "LinkedIn वर साइन इन करा. प्रवेशासाठी LinkedIn ने सत्यापित केलेला ईमेल तुमच्या सक्रिय GMG सदस्य नोंदीशी जुळला पाहिजे. "
            "ईमेल वेगळा असल्यास GMG शी संपर्क साधा."
            if marathi else
            "Sign in with LinkedIn. Your verified primary LinkedIn email must match your active GMG member record. "
            "If access is denied or the email differs, contact GMG through garjemarathi.com."
        )
    elif re.search(r"expertise|skills?|topic|कौशल्य|तज्ज्ञता", question):
        reply = ("Community Desk मध्ये My expertise उघडा. आठपर्यंत विषय निवडा आणि जतन करा." if marathi else
                 "In the Community Desk, open My expertise, choose up to eight topics, and save.")
    elif re.search(r"member|people|directory|mentor|jobs?|opportunit|सदस्य|मार्गदर्शक|नोकरी", question):
        reply = ("सदस्य किंवा मार्गदर्शक शोधण्यासाठी Community Desk मधील Find people वापरा. नोकरीसाठी Opportunities निवडा." if marathi else
                 "Open Find people in the Community Desk. Search by name or describe what you need. Use Opportunities to explore jobs.")
    elif re.search(r"what is|about gmg|garje marathi|गरजे मराठी|जीएमजी", question):
        reply = ("गरजे मराठी ग्लोबल मराठी समुदायाला व्यावसायिक संपर्क, मार्गदर्शन आणि ज्ञानाची देवाणघेवाण करण्यासाठी एकत्र आणते." if marathi else
                 "Garje Marathi Global connects the Marathi community for professional networking, mentoring, and knowledge sharing.")
    else:
        reply = ("नमस्कार! GMG, LinkedIn प्रवेश, सदस्य शोध किंवा My expertise याबद्दल विचारा." if marathi else
                 "Namaskar! Ask about GMG, LinkedIn sign-in, finding members, or updating your expertise.")
    return f"{reply}\n\nGMG Community Desk: {desk}"


def _objects(value: object):
    return (item for item in value if isinstance(item, dict)) if isinstance(value, list) else ()


def inbound_texts(payload: object, pilot: Pilot, now: datetime):
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return
    for entry in _objects(payload.get("entry")):
        for change in _objects(entry.get("changes")):
            data = change.get("value")
            if change.get("field") != "messages" or not isinstance(data, dict) or data.get("group_id"):
                continue
            metadata = data.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != pilot.phone_number_id:
                continue
            for message in _objects(data.get("messages")):
                sender, message_id, timestamp = (message.get(key) for key in ("from", "id", "timestamp"))
                text = message.get("text")
                if (message.get("type") != "text" or message.get("group_id") or message.get("group")
                        or not isinstance(sender, str) or sender not in pilot.testers
                        or not isinstance(message_id, str) or not MESSAGE_ID.fullmatch(message_id)
                        or not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp)
                        or not -30 <= now.timestamp() - int(timestamp) <= MAX_EVENT_AGE_SECONDS
                        or not isinstance(text, dict) or not isinstance(text.get("body"), str)):
                    continue
                if body := text["body"].strip():
                    yield sender, message_id, body[:1000]


@lru_cache(maxsize=1)
def reply_table() -> TableClient:
    return quota_table_from_environment()


def reserve_reply(table: TableClient, message_id: str, month: str, limit: int) -> bool:
    partition, key = "gmg-whatsapp", "reply-ledger"
    digest = hashlib.sha256(message_id.encode()).hexdigest()
    for _ in range(6):
        try:
            record = table.get_entity(partition, key)
        except ResourceNotFoundError:
            try:
                table.create_entity({"PartitionKey": partition, "RowKey": key, "Month": month,
                                     "Current": json.dumps([digest]), "Previous": "[]"})
                return True
            except HttpResponseError as error:
                if error.status_code != 409:
                    raise
                continue
        saved_month = record["Month"]
        current, previous = json.loads(record["Current"]), json.loads(record["Previous"])
        if any(not isinstance(items, list) or len(items) > MAX_REPLY_ATTEMPTS or
               any(not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{64}", item) for item in items)
               for items in (current, previous)):
            raise ValueError("Invalid WhatsApp reply ledger")
        if month < saved_month or digest in current or digest in previous:
            return False
        if month > saved_month:
            current, previous = [], current
        if len(current) >= limit:
            return False
        record.update(Month=month, Current=json.dumps([*current, digest]), Previous=json.dumps(previous))
        try:
            table.update_entity(record, mode=UpdateMode.REPLACE, etag=record.metadata["etag"],
                                match_condition=MatchConditions.IfNotModified)
            return True
        except HttpResponseError as error:
            if error.status_code != 412:
                raise
    raise ValueError("Could not reserve a WhatsApp reply")


def handle_inbound(payload: object, pilot: Pilot) -> None:
    now = datetime.now(timezone.utc)
    endpoint = f"https://graph.facebook.com/{pilot.graph_version}/{pilot.phone_number_id}/messages"
    for sender, message_id, body in inbound_texts(payload, pilot, now):
        if not reserve_reply(reply_table(), message_id, now.strftime("%Y-%m"), pilot.monthly_limit):
            continue
        try:
            result = requests.post(endpoint, headers={"Authorization": f"Bearer {pilot.access_token}"}, json={
                "messaging_product": "whatsapp", "recipient_type": "individual", "to": sender, "type": "text",
                "text": {"preview_url": False, "body": answer_for(body, pilot.desk_url)},
            }, timeout=(2, 4), allow_redirects=False)
            if not 200 <= result.status_code < 300:
                logger.warning("WhatsApp pilot send returned HTTP %d", result.status_code)
        except requests.RequestException as error:
            logger.warning("WhatsApp pilot send failed: %s", type(error).__name__)
