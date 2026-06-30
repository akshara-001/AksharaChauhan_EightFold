"""Unit tests for projector/config_projection.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from projector.config_projection import apply_projection, _resolve


SAMPLE_DATA = {
    "candidate_id": "cand_abc123",
    "full_name": "Priyanshu Choudhary",
    "emails": ["priyanshu@gmail.com", "priyanshu@work.com"],
    "phones": ["+919876543210"],
    "location": "Bangalore",
    "headline": "Backend Engineer",
    "overall_confidence": 0.97,
    "skills": [
        {"name": "C++", "confidence": 0.99, "sources": ["resume", "github"]},
        {"name": "Node.js", "confidence": 0.98, "sources": ["resume", "github", "ats"]},
    ],
    "links": {
        "github": "https://github.com/priyanshu-dev",
        "linkedin": "https://linkedin.com/in/priyanshu-dev",
    },
    "experience": [],
    "education": [],
    "provenance": [],
}


class TestResolve:

    def test_simple_field(self):
        assert _resolve(SAMPLE_DATA, "full_name") == "Priyanshu Choudhary"

    def test_list_index(self):
        assert _resolve(SAMPLE_DATA, "emails[0]") == "priyanshu@gmail.com"
        assert _resolve(SAMPLE_DATA, "emails[1]") == "priyanshu@work.com"

    def test_list_index_out_of_range(self):
        assert _resolve(SAMPLE_DATA, "emails[99]") is None

    def test_nested_dict(self):
        assert _resolve(SAMPLE_DATA, "links.github") == "https://github.com/priyanshu-dev"

    def test_list_index_subfield(self):
        assert _resolve(SAMPLE_DATA, "skills[0].name") == "C++"
        assert _resolve(SAMPLE_DATA, "skills[1].name") == "Node.js"
        assert _resolve(SAMPLE_DATA, "skills[0].confidence") == 0.99

    def test_missing_field_returns_none(self):
        assert _resolve(SAMPLE_DATA, "nonexistent_field") is None

    def test_empty_expr_returns_none(self):
        assert _resolve(SAMPLE_DATA, "") is None


class TestApplyProjection:

    def test_basic_remap(self):
        config = {
            "fields": [
                {"path": "name", "from": "full_name"},
                {"path": "primary_email", "from": "emails[0]"},
            ]
        }
        result = apply_projection(SAMPLE_DATA, config)
        assert result["name"] == "Priyanshu Choudhary"
        assert result["primary_email"] == "priyanshu@gmail.com"

    def test_unmapped_fields_excluded_by_default(self):
        config = {"fields": [{"path": "name", "from": "full_name"}]}
        result = apply_projection(SAMPLE_DATA, config)
        assert "emails" not in result
        assert "skills" not in result

    def test_include_unmapped(self):
        config = {
            "fields": [{"path": "name", "from": "full_name"}],
            "include_unmapped": True,
        }
        result = apply_projection(SAMPLE_DATA, config)
        assert "name" in result
        # Unmapped fields should be included
        assert "emails" in result or "skills" in result

    def test_empty_config_returns_data_unchanged(self):
        result = apply_projection(SAMPLE_DATA, {})
        assert result == SAMPLE_DATA

    def test_missing_source_field_maps_to_none(self):
        config = {"fields": [{"path": "missing", "from": "nonexistent"}]}
        result = apply_projection(SAMPLE_DATA, config)
        assert result["missing"] is None

    def test_nested_link_remap(self):
        config = {"fields": [{"path": "github_url", "from": "links.github"}]}
        result = apply_projection(SAMPLE_DATA, config)
        assert result["github_url"] == "https://github.com/priyanshu-dev"

    def test_skill_name_remap(self):
        config = {"fields": [{"path": "top_skill", "from": "skills[0].name"}]}
        result = apply_projection(SAMPLE_DATA, config)
        assert result["top_skill"] == "C++"

    def test_invalid_mapping_skipped(self):
        config = {
            "fields": [
                {"path": "name", "from": "full_name"},
                {"path": "", "from": ""},  # invalid, should be skipped
            ]
        }
        result = apply_projection(SAMPLE_DATA, config)
        assert "name" in result
