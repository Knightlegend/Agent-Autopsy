"""Validator module for user and transaction data."""

from __future__ import annotations

import re


def validate_email(email: str) -> bool:
    """Validate whether an email string matches standard RFC pattern."""
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def validate_positive_number(val: float) -> bool:
    """Check if number is strictly positive."""
    return isinstance(val, (int, float)) and val > 0

