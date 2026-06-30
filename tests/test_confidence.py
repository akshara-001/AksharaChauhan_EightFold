"""Unit tests for merger/confidence.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from merger.confidence import calculate_confidence, explain_confidence, SOURCE_WEIGHTS


class TestCalculateConfidence:

    def test_empty_sources_returns_zero(self):
        assert calculate_confidence([]) == 0.0

    def test_single_resume(self):
        result = calculate_confidence(["resume"])
        assert result == pytest.approx(0.85, abs=0.01)

    def test_single_github(self):
        result = calculate_confidence(["github"])
        assert result == pytest.approx(0.90, abs=0.01)

    def test_single_csv(self):
        result = calculate_confidence(["csv"])
        assert result == pytest.approx(0.75, abs=0.01)

    def test_resume_plus_github(self):
        # 1 - (1-0.85)(1-0.90) = 1 - 0.015 = 0.985
        result = calculate_confidence(["resume", "github"])
        assert result == pytest.approx(0.985, abs=0.001)

    def test_all_sources_capped_at_099(self):
        result = calculate_confidence(["resume", "github", "ats", "csv"])
        assert result <= 0.99

    def test_unknown_source_defaults_to_05(self):
        result = calculate_confidence(["unknown_source"])
        assert result == pytest.approx(0.50, abs=0.01)

    def test_case_insensitive(self):
        assert calculate_confidence(["Resume"]) == calculate_confidence(["resume"])
        assert calculate_confidence(["GITHUB"]) == calculate_confidence(["github"])

    def test_probabilistic_or_is_greater_than_max_single(self):
        single = calculate_confidence(["resume"])
        combined = calculate_confidence(["resume", "csv"])
        assert combined > single


class TestExplainConfidence:

    def test_returns_string(self):
        result = explain_confidence(["resume", "github"])
        assert isinstance(result, str)

    def test_contains_source_names(self):
        result = explain_confidence(["resume", "github"])
        assert "resume" in result
        assert "github" in result

    def test_empty_sources(self):
        result = explain_confidence([])
        assert "no sources" in result.lower()
