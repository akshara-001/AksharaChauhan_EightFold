"""Unit tests for normalizers/email.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from normalizers.email import normalize_email, normalize_emails


class TestNormalizeEmail:

    def test_valid_email_lowercased(self):
        assert normalize_email("Priyanshu@Gmail.COM") == "priyanshu@gmail.com"

    def test_valid_email_already_lowercase(self):
        assert normalize_email("abc@gmail.com") == "abc@gmail.com"

    def test_strips_whitespace(self):
        assert normalize_email("  abc@gmail.com  ") == "abc@gmail.com"

    def test_invalid_no_at(self):
        assert normalize_email("notanemail") is None

    def test_invalid_no_tld(self):
        assert normalize_email("abc@gmail") is None

    def test_empty_returns_none(self):
        assert normalize_email("") is None

    def test_none_returns_none(self):
        assert normalize_email(None) is None

    def test_normalize_emails_dedup(self):
        emails = ["abc@gmail.com", "ABC@GMAIL.COM", "xyz@yahoo.com"]
        result = normalize_emails(emails)
        assert result.count("abc@gmail.com") == 1
        assert "xyz@yahoo.com" in result
        assert len(result) == 2

    def test_normalize_emails_drops_invalid(self):
        emails = ["valid@example.com", "not-an-email", "also_valid@test.org"]
        result = normalize_emails(emails)
        assert "valid@example.com" in result
        assert "also_valid@test.org" in result
        assert len(result) == 2

    def test_normalize_emails_empty_list(self):
        assert normalize_emails([]) == []

    def test_subdomain_email(self):
        assert normalize_email("user@mail.company.co.uk") == "user@mail.company.co.uk"
