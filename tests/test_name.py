"""Unit tests for normalizers/name.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from normalizers.name import normalize_name


class TestNormalizeName:

    def test_lowercase_input(self):
        assert normalize_name("priyanshu choudhary") == "Priyanshu Choudhary"

    def test_uppercase_input(self):
        assert normalize_name("JOHN SMITH") == "John Smith"

    def test_extra_spaces(self):
        assert normalize_name("  John   Smith  ") == "John Smith"

    def test_particle_de(self):
        assert normalize_name("JOHN DE SOUZA") == "John de Souza"

    def test_particle_van(self):
        # "van" and "der" are both particles — stay lowercase
        assert normalize_name("jan van der berg") == "Jan van der Berg"

    def test_empty_returns_none(self):
        assert normalize_name("") is None
        assert normalize_name("   ") is None

    def test_none_returns_none(self):
        assert normalize_name(None) is None

    def test_single_name(self):
        # Single word is not a valid name (less than 2 words), should still normalize
        result = normalize_name("priyanshu")
        assert result == "Priyanshu"

    def test_mixed_case(self):
        assert normalize_name("priYANSHU CHOUDHARY") == "Priyanshu Choudhary"
