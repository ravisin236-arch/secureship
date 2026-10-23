package com.secureship.api.order;

import com.secureship.api.config.KafkaConfig;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/orders")
public class OrderController {

    private final KafkaTemplate<String, OrderEvent> kafkaTemplate;
    private final OrderRepository repository;

    public OrderController(KafkaTemplate<String, OrderEvent> kafkaTemplate, OrderRepository repository) {
        this.kafkaTemplate = kafkaTemplate;
        this.repository = repository;
    }

    /** Validates the order and publishes it. 202 = accepted for processing, not yet stored. */
    @PostMapping
    public ResponseEntity<Map<String, String>> create(@Valid @RequestBody OrderRequest request) {
        UUID orderId = UUID.randomUUID();
        OrderEvent event = OrderEvent.from(orderId, request, Instant.now());
        // Keyed by orderId so all events for one order land on the same partition.
        kafkaTemplate.send(KafkaConfig.ORDERS_TOPIC, orderId.toString(), event);
        return ResponseEntity.accepted().body(Map.of("orderId", orderId.toString(), "status", "PENDING"));
    }

    /** A malformed UUID is rejected with 400 by Spring before reaching this method. */
    @GetMapping("/{orderId}")
    public ResponseEntity<OrderView> get(@PathVariable UUID orderId) {
        return repository.findById(orderId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
