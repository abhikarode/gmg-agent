"""Private in-memory Blob fixture for same-origin handoff tests."""

from io import BytesIO
from types import SimpleNamespace

from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError


class RelayFixture:
    def __init__(self):
        self.tickets = {}

    def blob(self, code):
        return RelayBlob(self.tickets, code)


class RelayBlob:
    def __init__(self, tickets, key):
        self.tickets = tickets
        self.key = key

    def upload_blob(self, payload, *, overwrite):
        if not overwrite and self.key in self.tickets:
            raise ResourceExistsError
        self.tickets[self.key] = payload

    def download_blob(self, *, offset, length):
        if self.key not in self.tickets:
            raise ResourceNotFoundError
        return SimpleNamespace(
            readall=BytesIO(self.tickets[self.key][offset:offset + length]).read,
            properties=SimpleNamespace(etag=self.key),
        )

    def delete_blob(self, *, etag, match_condition):
        assert match_condition == MatchConditions.IfNotModified
        if etag != self.key or self.key not in self.tickets:
            raise ResourceModifiedError
        del self.tickets[self.key]
