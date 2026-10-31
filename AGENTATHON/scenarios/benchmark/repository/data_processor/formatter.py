"""String and numeric formatting utilities."""

from __future__ import annotations


def format_currency(amount: float, symbol: str = "$") -> str:
    """Format floating point currency value."""
    return f"{symbol}{amount:.2f}"


def truncate_text(text: str, max_chars: int = 50) -> str:
    """Truncate text to max_chars with ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."

