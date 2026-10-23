"""Runs the worker: Kafka consumer -> validation -> Postgres."""
from __future__ import annotations

import logging
import os
import signal

import psycopg
from confluent_kafka import Consumer

from order_worker.processing import process_message

log = logging.getLogger("order_worker")


def build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": os.environ.get("KAFKA_GROUP_ID", "order-worker"),
        "auto.offset.reset": "earliest",
        # Offsets are committed manually, only after the database commit succeeds.
        "enable.auto.commit": False,
        # Notice the topic quickly if the worker starts before the API creates it.
        "topic.metadata.refresh.interval.ms": 10000,
    })


def run() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    topic = os.environ.get("KAFKA_TOPIC", "orders")
    dsn = os.environ["DATABASE_URL"]

    running = True

    def stop(signum, frame):
        nonlocal running
        log.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    consumer = build_consumer()
    consumer.subscribe([topic])
    log.info("Worker started, consuming topic '%s'", topic)

    try:
        with psycopg.connect(dsn) as conn:
            while running:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.error("Kafka error: %s", msg.error())
                    continue

                with conn.cursor() as cur:
                    stored = process_message(msg.value(), cur)
                conn.commit()
                # At-least-once delivery + idempotent insert = no lost and no duplicate orders.
                consumer.commit(message=msg, asynchronous=False)

                if stored:
                    log.info("Stored order (partition %s, offset %s)", msg.partition(), msg.offset())
    finally:
        consumer.close()
        log.info("Worker stopped")


if __name__ == "__main__":
    run()
