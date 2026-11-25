"""Azure service endpoints and the shared Container Apps runtime identity."""

import os
import re
from functools import lru_cache

from azure.identity import ManagedIdentityCredential


def storage_endpoint(value: str, service: str) -> str:
    endpoint = value.rstrip("/")
    if not re.fullmatch(rf"https://[a-z0-9]{{3,24}}\.{service}\.core\.windows\.net", endpoint):
        raise ValueError(f"Configure a public Azure {service} service URL.")
    return endpoint


@lru_cache(maxsize=1)
def runtime_identity() -> ManagedIdentityCredential:
    return ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID") or None)
