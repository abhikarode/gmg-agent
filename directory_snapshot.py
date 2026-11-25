"""Publish and read the versioned, minimized directory in Blob Storage."""

import hashlib
import json
import logging
import os
import re

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from azure_storage import runtime_identity, storage_endpoint

CONTAINER = "gmg-directory"
MANIFEST = "current.json"
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
logger = logging.getLogger(__name__)


def snapshot_container(connection: str | None = None, *, credential=None):
    """Use Azure identity in the cloud or a shared key for the local emulator."""
    options = {
        "api_version": "2023-11-03", "connection_timeout": 4, "read_timeout": 8,
        "retry_total": 0, "logger": logger,
    }
    endpoint = os.getenv("GMG_BLOB_ACCOUNT_URL")
    if endpoint and connection:
        raise ValueError("Select one directory storage authentication method.")
    if endpoint:
        service = BlobServiceClient(
            storage_endpoint(endpoint, "blob"), credential=credential or runtime_identity(), **options,
        )
    elif connection:
        service = BlobServiceClient.from_connection_string(connection, **options)
    else:
        raise ValueError("Configure Azure Blob Storage or Azurite for the directory.")
    return service.get_container_client(CONTAINER)


def snapshot_name(digest: str) -> str:
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid snapshot digest.")
    return f"snapshots/{digest}.json"


def decode_snapshot(contents: bytes, digest: str) -> dict:
    if hashlib.sha256(contents).hexdigest() != digest:
        raise ValueError("Directory snapshot checksum mismatch.")
    snapshot = json.loads(contents)
    if not isinstance(snapshot, dict):
        raise ValueError("Invalid directory snapshot.")
    users, jobs = snapshot.get("users"), snapshot.get("jobs")
    if not isinstance(users, list) or not users or not isinstance(jobs, list):
        raise ValueError("Directory snapshot must have member and job lists.")
    if any(not isinstance(u, dict) or not isinstance(u.get("unique_profile_id"), str)
           or not u["unique_profile_id"].strip() for u in users):
        raise ValueError("A directory member is missing its ID.")
    if len({u["unique_profile_id"] for u in users}) != len(users):
        raise ValueError("Duplicate directory member IDs.")
    if any(not isinstance(job, dict) for job in jobs):
        raise ValueError("Invalid directory job entry.")
    return snapshot


def read_blob(container, name: str, limit: int) -> bytes:
    contents = container.download_blob(name, offset=0, length=limit + 1).readall()
    if len(contents) > limit:
        raise ValueError("Directory storage object exceeds its size limit.")
    return contents


def current_snapshot_digest(container) -> str:
    manifest = json.loads(read_blob(container, MANIFEST, 4096))
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Invalid directory manifest.")
    digest = manifest.get("sha256")
    if not isinstance(digest, str):
        raise ValueError("Invalid snapshot digest.")
    return digest


def load_snapshot_version(container, digest: str) -> dict:
    contents = read_blob(container, snapshot_name(digest), MAX_SNAPSHOT_BYTES)
    return decode_snapshot(contents, digest)


def load_snapshot(connection: str | None = None) -> dict:
    container = snapshot_container(connection)
    return load_snapshot_version(container, current_snapshot_digest(container))


def activate_snapshot(container, digest: str) -> None:
    decode_snapshot(read_blob(container, snapshot_name(digest), MAX_SNAPSHOT_BYTES), digest)
    manifest = json.dumps({"version": 1, "sha256": digest}).encode()
    container.upload_blob(MANIFEST, manifest, overwrite=True)


def publish_snapshot(connection: str | None, snapshot: dict, *, credential=None) -> str:
    contents = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(contents) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Directory snapshot exceeds its size limit.")
    digest = hashlib.sha256(contents).hexdigest()
    decode_snapshot(contents, digest)
    container = snapshot_container(connection, credential=credential)
    if connection:
        try:
            container.create_container()
        except ResourceExistsError:
            pass
    try:
        container.upload_blob(snapshot_name(digest), contents, overwrite=False)
    except ResourceExistsError:
        pass
    activate_snapshot(container, digest)
    return digest
