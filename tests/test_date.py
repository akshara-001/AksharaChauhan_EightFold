"""Unit tests for normalizers/date.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from normalizers.date import normalize_date


class TestNormalizeDate:

    def test_iso_format(self):
        assert normalize_date("2023-01") == "2023-01"

    def test_month_name_year(self):
        assert normalize_date("Jan 2023") == "2023-01"
        assert normalize_date("January 2023") == "2023-01"
        assert normalize_date("jun 2021") == "2021-06"

    def test_slash_format_mm_yyyy(self):
        assert normalize_date("01/2023") == "2023-01"
        assert normalize_date("6/2021") == "2021-06"

    def test_year_only(self):
        assert normalize_date("2022") == "2022-01"

    def test_year_month_reversed(self):
        assert normalize_date("2023-06") == "2023-06"

    def test_quarter_format(self):
        result = normalize_date("Q1 2023")
        assert result == "2023-01"
        result = normalize_date("Q3 2022")
        assert result == "2022-07"

    def test_present_returns_none(self):
        assert normalize_date("Present") is None
        assert normalize_date("present") is None
        assert normalize_date("current") is None

    def test_empty_returns_none(self):
        assert normalize_date("") is None
        assert normalize_date(None) is None

    def test_garbage_returns_none(self):
        assert normalize_date("not-a-date") is None

    def test_dash_separator(self):
        assert normalize_date("2023-06") == "2023-06"
