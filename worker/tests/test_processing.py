import json
import uuid
from decimal import Decimal

import pytest

from order_worker.processing import INSERT_SQL, InvalidEvent, parse_event, process_message

ORDER_ID = "3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"


def make_event(**overrides) -> str:
    event = {
        "orderId": ORDER_ID,
        "customerId": "cust-42",
        "item": "Margherita pizza",
        "quantity": 3,
        "unitPrice": 12.50,
        "createdAt": "2026-10-19T10:15:30.123456Z",
    }
    event.update(overrides)
    return json.dumps(event)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_valid_event_is_parsed():
    order = parse_event(make_event())
    assert order.order_id == ORDER_ID
    assert order.customer_id == "cust-42"
    assert order.quantity == 3
    assert order.unit_price == Decimal("12.5")


def test_total_price_uses_exact_decimal_arithmetic():
    order = parse_event(make_event(quantity=3, unitPrice=0.10))
    # With floats, 3 * 0.1 = 0.30000000000000004. With Decimal it is exactly 0.30.
    assert order.total_price == Decimal("0.30")


def test_whitespace_is_trimmed():
    order = parse_event(make_event(customerId="  cust-42  "))
    assert order.customer_id == "cust-42"


@pytest.mark.parametrize("timestamp", [
    "2026-10-19T10:15:30Z",                 # no fraction
    "2026-10-19T10:15:30.123Z",             # millis
    "2026-10-19T10:15:30.123456789Z",       # nanos from Java Instant
    "2026-10-19T11:15:30.5+01:00",          # explicit offset
])
def test_java_timestamp_formats_are_accepted(timestamp):
    order = parse_event(make_event(createdAt=timestamp))
    assert order.created_at.tzinfo is not None


@pytest.mark.parametrize("raw, reason", [
    ("not json", "not valid JSON"),
    ("[1, 2, 3]", "JSON object"),
    (make_event(orderId="123"), "valid UUID"),
    (make_event(orderId=None), "valid UUID"),
    (make_event(customerId=""), "customerId"),
    (make_event(customerId="x" * 65), "exceeds 64"),
    (make_event(item=None), "item"),
    (make_event(quantity=0), "between 1 and 100"),
    (make_event(quantity=101), "between 1 and 100"),
    (make_event(quantity=True), "integer"),
    (make_event(quantity="3"), "integer"),
    (make_event(unitPrice=-1), "greater than zero"),
    (make_event(unitPrice=0), "greater than zero"),
    (make_event(unitPrice="12.50"), "must be a number"),
    (make_event(unitPrice=1.999), "2 decimal places"),
    (make_event(createdAt="2026-10-19T10:15:30"), "timezone"),
    (make_event(createdAt="yesterday"), "timezone"),
    (make_event(createdAt="2026-13-45T10:15:30Z"), "not a valid date"),
])
def test_invalid_events_are_rejected(raw, reason):
    with pytest.raises(InvalidEvent, match=reason):
        parse_event(raw)


def test_process_message_writes_valid_order():
    cursor = FakeCursor()
    assert process_message(make_event(quantity=2, unitPrice=12.50), cursor) is True

    sql, params = cursor.calls[0]
    assert sql == INSERT_SQL
    assert "ON CONFLICT (order_id) DO NOTHING" in sql
    assert params[0] == uuid.UUID(ORDER_ID)
    assert params[5] == Decimal("25.00")      # total_price
    assert sql.count("%s") == len(params)     # every placeholder has a value


def test_process_message_skips_invalid_order_without_writing():
    cursor = FakeCursor()
    assert process_message(make_event(quantity=0), cursor) is False
    assert cursor.calls == []


def test_sql_uses_placeholders_not_string_formatting():
    # A malicious-looking value is passed as a parameter, never spliced into the SQL.
    cursor = FakeCursor()
    process_message(make_event(customerId="x'); DROP TABLE orders;--"), cursor)
    sql, params = cursor.calls[0]
    assert "DROP TABLE" not in sql
    assert params[1] == "x'); DROP TABLE orders;--"
