"""A durable, fail-closed call allowance shared by every app replica."""

import os
from datetime import datetime, timezone

from azure.core import MatchConditions
from azure.core.exceptions import AzureError, HttpResponseError, ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from azure_storage import runtime_identity, storage_endpoint

TABLE = "gmginference"
DAILY_LIMIT = 500
MONTHLY_LIMIT = 6000
COUNTER_PARTITION = "gpt-6-luna"


def quota_table_from_environment() -> TableClient:
    endpoint = os.getenv("GMG_QUOTA_TABLE_URL")
    connection = os.getenv("GMG_QUOTA_TABLE_CONNECTION_STRING")
    if bool(endpoint) == bool(connection):
        raise ValueError("Select one counter storage authentication method.")
    options = {"table_name": TABLE, "connection_timeout": 2, "read_timeout": 3, "retry_total": 0}
    if endpoint:
        return TableClient(storage_endpoint(endpoint, "table"), credential=runtime_identity(), **options)
    return TableClient.from_connection_string(connection, **options)


class InferenceBudgetUnavailable(RuntimeError):
    """No call can be sent without a confirmed reservation."""


class InferenceBudget:
    def __init__(self, table: TableClient, daily: int, monthly: int, authorized_until: datetime | None = None):
        if not (0 <= daily <= DAILY_LIMIT and 0 <= monthly <= MONTHLY_LIMIT):
            raise ValueError("Inference allowance exceeds the pilot limits.")
        if authorized_until is not None and authorized_until.utcoffset() is None:
            raise ValueError("The inference deadline must include a time zone.")
        self.table = table
        self.daily = daily
        self.monthly = monthly
        self.authorized_until = authorized_until

    @classmethod
    def from_environment(cls):
        deadline = os.getenv("GMG_INFERENCE_AUTHORIZED_UNTIL")
        return cls(
            quota_table_from_environment(), int(os.getenv("GMG_INFERENCE_DAILY_CALLS", "0")),
            int(os.getenv("GMG_INFERENCE_MONTHLY_CALLS", "0")),
            datetime.fromisoformat(deadline) if deadline else None,
        )

    def reserve(self) -> None:
        """Increment both periods in one conditional write before any provider call."""
        now = datetime.now(timezone.utc)
        if not self.daily or not self.monthly or self.authorized_until is None or now >= self.authorized_until:
            raise InferenceBudgetUnavailable("Hosted inference is paused.")
        try:
            self._reserve(now)
        except (AzureError, OSError, ValueError, TypeError, KeyError) as error:
            raise InferenceBudgetUnavailable("Could not confirm the inference allowance.") from error

    def _reserve(self, now: datetime) -> None:
        # One row per UTC month preserves previous days when requests overlap midnight.
        partition, month, day = COUNTER_PARTITION, now.strftime("%Y-%m"), now.strftime("Day%d")
        for _ in range(8):
            try:
                entity = self.table.get_entity(partition, month)
            except ResourceNotFoundError:
                try:
                    self.table.create_entity({
                        "PartitionKey": partition, "RowKey": month, "Calls": 1, day: 1,
                    })
                    return
                except HttpResponseError as error:
                    if error.status_code != 409:
                        raise
                    continue
            total, today = entity["Calls"], entity.get(day, 0)
            daily_counts = [value for key, value in entity.items() if key.startswith("Day")]
            if (
                type(total) is not int or total < 1
                or any(type(value) is not int or value < 1 for value in daily_counts)
                or sum(daily_counts) != total
            ):
                raise ValueError("Invalid inference counter.")
            if total >= self.monthly or today >= self.daily:
                raise InferenceBudgetUnavailable("Hosted inference allowance reached.")
            entity["Calls"], entity[day] = total + 1, today + 1
            try:
                self.table.update_entity(
                    entity, mode=UpdateMode.REPLACE, etag=entity.metadata["etag"],
                    match_condition=MatchConditions.IfNotModified,
                )
                return
            except HttpResponseError as error:
                if error.status_code != 412:
                    raise
        raise InferenceBudgetUnavailable("Could not reserve an inference call.")
