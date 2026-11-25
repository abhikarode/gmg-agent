"""Store standardized, member-selected expertise in a private Azure table."""

import json
import os
from functools import lru_cache
from pathlib import Path
from time import monotonic

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from azure_storage import runtime_identity, storage_endpoint

TABLE = "gmgexpertise"
PARTITION = "member-expertise"
MAX_TOPICS = 8
CATALOG = json.loads(Path(__file__).with_name("expertise_catalog.json").read_text(encoding="utf-8"))
LABELS = {key: label for group in CATALOG.values() for key, label in group.items()}


def validate_topics(topics: list[str]) -> list[str]:
    if len(topics) > MAX_TOPICS or any(topic not in LABELS for topic in topics):
        raise ValueError("Select up to eight topics from the expertise list.")
    return [key for key in LABELS if key in topics]


@lru_cache(maxsize=1)
def table_client() -> TableClient:
    endpoint = os.getenv("GMG_EXPERTISE_TABLE_URL")
    connection = os.getenv("GMG_EXPERTISE_TABLE_CONNECTION_STRING")
    if bool(endpoint) == bool(connection):
        raise ValueError("Select one expertise storage authentication method.")
    options = {"table_name": TABLE, "connection_timeout": 2, "read_timeout": 3, "retry_total": 0}
    if endpoint:
        return TableClient(storage_endpoint(endpoint, "table"), credential=runtime_identity(), **options)
    return TableClient.from_connection_string(connection, **options)


def _topics(row: dict) -> list[str]:
    # Retain the remaining choices if an administrator retires a topic.
    return [topic for topic in json.loads(row["Topics"]) if topic in LABELS]


def load_topics(key: str) -> list[str]:
    try:
        return _topics(table_client().get_entity(PARTITION, key))
    except ResourceNotFoundError as error:
        if error.error_code in ("ResourceNotFound", "EntityNotFound"):
            return []
        raise


def save_topics(key: str, topics: list[str]) -> list[str]:
    choices = validate_topics(topics)
    table_client().upsert_entity(
        {"PartitionKey": PARTITION, "RowKey": key, "Topics": json.dumps(choices)},
        mode=UpdateMode.REPLACE,
    )
    _expertise_entries.cache_clear()
    return choices


@lru_cache(maxsize=1)
def _expertise_entries(_period: int) -> tuple[tuple[str, tuple[str, ...]], ...]:
    rows = table_client().query_entities("PartitionKey eq @partition", parameters={"partition": PARTITION})
    return tuple(sorted((row["RowKey"], tuple(LABELS[topic] for topic in _topics(row))) for row in rows))


def expertise_entries() -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not (os.getenv("GMG_EXPERTISE_TABLE_URL") or os.getenv("GMG_EXPERTISE_TABLE_CONNECTION_STRING")):
        return ()
    return _expertise_entries(int(monotonic() // 30))
