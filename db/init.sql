-- Orders written by the worker. Constraints mirror the API validation,
-- so bad data is rejected even if it bypasses the application.
CREATE TABLE IF NOT EXISTS orders (
    order_id      UUID          PRIMARY KEY,
    customer_id   VARCHAR(64)   NOT NULL,
    item          VARCHAR(128)  NOT NULL,
    quantity      INTEGER       NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    unit_price    NUMERIC(12,2) NOT NULL CHECK (unit_price > 0),
    total_price   NUMERIC(12,2) NOT NULL CHECK (total_price > 0),
    status        VARCHAR(16)   NOT NULL DEFAULT 'PROCESSED',
    created_at    TIMESTAMPTZ   NOT NULL,
    processed_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);
