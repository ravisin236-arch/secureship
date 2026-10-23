package com.secureship.api.order;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(OrderController.class)
class OrderControllerTest {

    @Autowired
    private MockMvc mvc;

    @MockBean
    private KafkaTemplate<String, OrderEvent> kafkaTemplate;

    @MockBean
    private OrderRepository repository;

    private static final String VALID_ORDER = """
            {"customerId":"cust-42","item":"Margherita pizza","quantity":2,"unitPrice":12.50}
            """;

    @Test
    void validOrderIsAcceptedAndPublished() throws Exception {
        mvc.perform(post("/orders").contentType(MediaType.APPLICATION_JSON).content(VALID_ORDER))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.orderId").isNotEmpty())
                .andExpect(jsonPath("$.status").value("PENDING"));

        verify(kafkaTemplate).send(eq("orders"), anyString(), any(OrderEvent.class));
    }

    @Test
    void zeroQuantityIsRejectedAndNothingIsPublished() throws Exception {
        String body = """
                {"customerId":"cust-42","item":"Margherita pizza","quantity":0,"unitPrice":12.50}
                """;
        mvc.perform(post("/orders").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(kafkaTemplate);
    }

    @Test
    void negativePriceIsRejected() throws Exception {
        String body = """
                {"customerId":"cust-42","item":"Margherita pizza","quantity":1,"unitPrice":-5}
                """;
        mvc.perform(post("/orders").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(kafkaTemplate);
    }

    @Test
    void blankCustomerIsRejected() throws Exception {
        String body = """
                {"customerId":"  ","item":"Margherita pizza","quantity":1,"unitPrice":9.99}
                """;
        mvc.perform(post("/orders").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(kafkaTemplate);
    }

    @Test
    void existingOrderIsReturned() throws Exception {
        UUID id = UUID.randomUUID();
        when(repository.findById(id)).thenReturn(Optional.of(new OrderView(
                id, "cust-42", "Margherita pizza", 2,
                new BigDecimal("12.50"), new BigDecimal("25.00"), "PROCESSED", OffsetDateTime.now())));

        mvc.perform(get("/orders/{id}", id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalPrice").value(25.00))
                .andExpect(jsonPath("$.status").value("PROCESSED"));
    }

    @Test
    void unknownOrderReturns404() throws Exception {
        when(repository.findById(any())).thenReturn(Optional.empty());

        mvc.perform(get("/orders/{id}", UUID.randomUUID()))
                .andExpect(status().isNotFound());
    }

    @Test
    void malformedOrderIdReturns400() throws Exception {
        mvc.perform(get("/orders/not-a-uuid"))
                .andExpect(status().isBadRequest());
    }
}
