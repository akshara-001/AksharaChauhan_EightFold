"""Unit tests for normalizers/phone.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from normalizers.phone import normalize_phone, normalize_phones


class TestNormalizePhone:

    def test_10_digit_indian_number(self):
        assert normalize_phone("9876543210") == "+919876543210"

    def test_plus91_with_space(self):
        assert normalize_phone("+91 9876543210") == "+919876543210"

    def test_91_dash_format(self):
        assert normalize_phone("91-9876543210") == "+919876543210"

    def test_formatted_with_parens(self):
        assert normalize_phone("(800) 555-1234", default_region="US") == "+18005551234"

    def test_invalid_phone_returns_none(self):
        assert normalize_phone("not-a-phone") is None

    def test_empty_string_returns_none(self):
        assert normalize_phone("") is None

    def test_none_input_returns_none(self):
        assert normalize_phone(None) is None

    def test_too_short_returns_none(self):
        assert normalize_phone("12345") is None

    def test_normalize_phones_list(self):
        phones = ["9876543210", "+91 9876543210", "9999999999"]
        result = normalize_phones(phones)
        assert "+919876543210" in result
        assert "+919999999999" in result
        # Duplicate should be collapsed
        assert result.count("+919876543210") == 1

    def test_normalize_phones_dedup(self):
        phones = ["+91 9876543210", "9876543210"]
        result = normalize_phones(phones)
        assert len(result) == 1

    def test_normalize_phones_drops_invalids(self):
        phones = ["9876543210", "bad-number"]
        result = normalize_phones(phones)
        assert len(result) == 1
        assert result[0] == "+919876543210"
