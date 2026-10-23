package com.secureship.api.order;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Event published to Kafka. createdAt is an ISO-8601 string (e.g. 2026-10-19T10:15:30Z)
 * so every consumer, in any language, parses it the same way.
 */
public record OrderEvent(
        String orderId,
        String customerId,
        String item,
        int quantity,
        BigDecimal unitPrice,
        String createdAt) {

    public static OrderEvent from(UUID orderId, OrderRequest request, Instant now) {
        return new OrderEvent(
                orderId.toString(),
                request.customerId().trim(),
                request.item().trim(),
                request.quantity(),
                request.unitPrice(),
                now.toString());
    }
}
