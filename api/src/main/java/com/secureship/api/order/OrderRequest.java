package com.secureship.api.order;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;

/** Incoming order. Every field is validated before anything is published. */
public record OrderRequest(
        @NotBlank @Size(max = 64) String customerId,
        @NotBlank @Size(max = 128) String item,
        @Min(1) @Max(100) int quantity,
        @NotNull @DecimalMin("0.01") @Digits(integer = 10, fraction = 2) BigDecimal unitPrice) {
}
