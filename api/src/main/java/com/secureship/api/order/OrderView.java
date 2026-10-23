package com.secureship.api.order;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

/** An order as stored by the worker and returned by GET /orders/{id}. */
public record OrderView(
        UUID orderId,
        String customerId,
        String item,
        int quantity,
        BigDecimal unitPrice,
        BigDecimal totalPrice,
        String status,
        OffsetDateTime createdAt) {
}
