"""Unit tests for data_processor.calculator."""

import pytest
from data_processor.calculator import calculate_average, calculate_discount


def test_calculate_discount_normal():
    """Test standard discount calculation.

    Fails when intentional bug in calculate_discount is present!
    """
    # 200 with 10% discount should be 180.0
    result = calculate_discount(200.0, 10.0)
    assert result == 180.0, f"Expected 180.0, got {result}"

    # 50 with 20% discount should be 40.0
    result2 = calculate_discount(50.0, 20.0)
    assert result2 == 40.0, f"Expected 40.0, got {result2}"


def test_calculate_discount_zero():
    """Test 0% discount."""
    assert calculate_discount(150.0, 0.0) == 150.0


def test_calculate_discount_full():
    """Test 100% discount."""
    assert calculate_discount(150.0, 100.0) == 0.0


def test_calculate_discount_invalid_inputs():
    """Test input validations."""
    with pytest.raises(ValueError, match="Price cannot be negative"):
        calculate_discount(-10.0, 10.0)

    with pytest.raises(ValueError, match="Discount percent must be between 0 and 100"):
        calculate_discount(100.0, 105.0)

    with pytest.raises(ValueError, match="Discount percent must be between 0 and 100"):
        calculate_discount(100.0, -5.0)


def test_calculate_average():
    """Test mean calculation."""
    assert calculate_average([10.0, 20.0, 30.0]) == 20.0
    assert calculate_average([]) == 0.0

