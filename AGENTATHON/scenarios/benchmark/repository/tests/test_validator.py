"""Unit tests for data_processor.validator."""

from data_processor.validator import validate_email, validate_positive_number


def test_validate_email_valid():
    assert validate_email("developer@trinity.exe") is True
    assert validate_email("test.user+tag@sub.domain.org") is True


def test_validate_email_invalid():
    assert validate_email("") is False
    assert validate_email("plainaddress") is False
    assert validate_email("@missingusername.com") is False
    assert validate_email(None) is False


def test_validate_positive_number():
    assert validate_positive_number(42) is True
    assert validate_positive_number(0.01) is True
    assert validate_positive_number(0) is False
    assert validate_positive_number(-5) is False

