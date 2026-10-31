"""Unit tests for data_processor.formatter."""

from data_processor.formatter import format_currency, truncate_text


def test_format_currency():
    assert format_currency(12.345) == "$12.35"
    assert format_currency(0.0) == "$0.00"
    assert format_currency(99.9, "€") == "€99.90"


def test_truncate_text():
    assert truncate_text("Short", 10) == "Short"
    assert truncate_text("Hello World! This is a long sentence.", 15) == "Hello World!..."

