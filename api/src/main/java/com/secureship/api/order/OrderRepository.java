package com.secureship.api.order;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public class OrderRepository {

    // Parameterised query: user input is never concatenated into SQL.
    private static final String FIND_BY_ID = """
            SELECT order_id, customer_id, item, quantity, unit_price, total_price, status, created_at
            FROM orders
            WHERE order_id = ?
            """;

    private final JdbcTemplate jdbc;

    public OrderRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<OrderView> findById(UUID orderId) {
        return jdbc.query(FIND_BY_ID, (rs, rowNum) -> new OrderView(
                        rs.getObject("order_id", UUID.class),
                        rs.getString("customer_id"),
                        rs.getString("item"),
                        rs.getInt("quantity"),
                        rs.getBigDecimal("unit_price"),
                        rs.getBigDecimal("total_price"),
                        rs.getString("status"),
                        rs.getObject("created_at", OffsetDateTime.class)),
                orderId)
                .stream()
                .findFirst();
    }
}
