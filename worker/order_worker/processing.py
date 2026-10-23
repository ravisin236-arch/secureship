"""Pure order-event processing logic.

Nothing here imports Kafka or a database driver, so every rule can be unit-tested
on its own. main.py wires this logic to the real Kafka consumer and Postgres.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

log = logging.getLogger(__name__)

MAX_QUANTITY = 100
CENTS = Decimal("0.01")

# ON CONFLICT makes the insert idempotent: if Kafka redelivers an event
# (at-least-once delivery), the order is not stored twice.
INSERT_SQL = (
    "INSERT INTO orders "
    "(order_id, customer_id, item, quantity, unit_price, total_price, created_at) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (order_id) DO NOTHING"
)

_TIMESTAMP = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<frac>\d+))?"
    r"(?P<tz>Z|[+-]\d{2}:\d{2})$"
)


class InvalidEvent(ValueError):
    """Raised when an incoming event fails validation."""


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    item: str
    quantity: int
    unit_price: Decimal
    created_at: datetime

    @property
    def total_price(self) -> Decimal:
        # Money is Decimal end to end - never float - and rounded explicitly.
        return (self.unit_price * self.quantity).quantize(CENTS, rounding=ROUND_HALF_UP)

    def insert_params(self) -> tuple:
        return (
            uuid.UUID(self.order_id),
            self.customer_id,
            self.item,
            self.quantity,
            self.unit_price,
            self.total_price,
            self.created_at,
        )


def _require_text(data: dict, key: str, max_len: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidEvent(f"{key} must be a non-empty string")
    value = value.strip()
    if len(value) > max_len:
        raise InvalidEvent(f"{key} exceeds {max_len} characters")
    return value


def _parse_quantity(value) -> int:
    # bool is a subclass of int in Python, so reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidEvent("quantity must be an integer")
    if not 1 <= value <= MAX_QUANTITY:
        raise InvalidEvent(f"quantity must be between 1 and {MAX_QUANTITY}")
    return value


def _parse_price(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise InvalidEvent("unitPrice must be a number")
    price = Decimal(value)
    if not price.is_finite() or price <= 0:
        raise InvalidEvent("unitPrice must be greater than zero")
    if price.as_tuple().exponent < -2:
        raise InvalidEvent("unitPrice must have at most 2 decimal places")
    return price


def _parse_timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise InvalidEvent("createdAt must be an ISO-8601 string")
    match = _TIMESTAMP.match(value.strip())
    if not match:
        raise InvalidEvent("createdAt must be an ISO-8601 timestamp with a timezone")
    # Java may send 0-9 fractional digits; Python accepts exactly 6.
    fraction = (match["frac"] or "")[:6].ljust(6, "0")
    tz = "+00:00" if match["tz"] == "Z" else match["tz"]
    try:
        return datetime.fromisoformat(f"{match['base']}.{fraction}{tz}")
    except ValueError as exc:
        raise InvalidEvent("createdAt is not a valid date/time") from exc


def parse_event(raw) -> Order:
    """Parse and validate one raw Kafka message value. Raises InvalidEvent on bad input."""
    try:
        # parse_float=Decimal keeps prices exact (12.50 stays 12.50, not 12.4999...).
        data = json.loads(raw, parse_float=Decimal)
    except (TypeError, ValueError) as exc:
        raise InvalidEvent("event is not valid JSON") from exc
    if not isinstance(data, dict):
        raise InvalidEvent("event must be a JSON object")

    try:
        order_id = str(uuid.UUID(str(data.get("orderId"))))
    except ValueError as exc:
        raise InvalidEvent("orderId must be a valid UUID") from exc

    return Order(
        order_id=order_id,
        customer_id=_require_text(data, "customerId", 64),
        item=_require_text(data, "item", 128),
        quantity=_parse_quantity(data.get("quantity")),
        unit_price=_parse_price(data.get("unitPrice")),
        created_at=_parse_timestamp(data.get("createdAt")),
    )


def process_message(raw, cursor) -> bool:
    """Validate one message and write it with the given DB cursor.

    Returns True if the order was written (or already existed), False if the event
    was rejected as invalid. Database errors are NOT caught: they propagate so the
    Kafka offset is not committed and the message is retried.
    """
    try:
        order = parse_event(raw)
    except InvalidEvent as exc:
        log.warning("Rejected invalid event: %s", exc)
        return False
    cursor.execute(INSERT_SQL, order.insert_params())
    return True
