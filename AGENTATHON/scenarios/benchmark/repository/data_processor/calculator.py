"""Calculator module for numerical data processing."""

from __future__ import annotations

from typing import List


def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate final price after applying a percentage discount.

    Args:
        price: The original price before discount.
        discount_percent: Percentage discount (0 to 100).

    Returns:
        The final discounted price rounded to 2 decimal places.

    Raises:
        ValueError: If price is negative or discount_percent is out of [0, 100].
    """
    if price < 0:
        raise ValueError("Price cannot be negative")
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount percent must be between 0 and 100")

    # INTENTIONAL BUG FOR AGENT EVALUATION:
    # Subtracts discount_percent flat value instead of calculating percentage of price:
    # e.g., 200.0 with 10% discount gives 190.0 instead of 180.0
    return round(price - discount_percent, 2)


def calculate_average(numbers: List[float]) -> float:
    """Calculate arithmetic mean of a sequence of numbers."""
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), 4)

