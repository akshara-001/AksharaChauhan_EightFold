"""Unit tests for merger/merge.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from merger.merge import merge_records


def _make_record(source: str, **kwargs) -> dict:
    base = {
        "source": source,
        "full_name": None,
        "headline": None,
        "emails": [],
        "phones": [],
        "location": None,
        "skills": [],
        "experience": [],
        "education": [],
        "links": {"github": None, "linkedin": None},
    }
    base.update(kwargs)
    return base


class TestMergeRecords:

    def test_empty_list_returns_empty_candidate(self):
        result = merge_records([])
        assert result["full_name"] is None
        assert result["emails"] == []
        assert result["skills"] == []
        assert result["overall_confidence"] == 0.0

    def test_single_record(self):
        record = _make_record("resume", full_name="John Smith", emails=["john@example.com"])
        result = merge_records([record])
        assert result["full_name"] == "John Smith"
        assert "john@example.com" in result["emails"]

    def test_scalar_conflict_resume_wins_over_csv(self):
        resume = _make_record("resume", full_name="Priyanshu Choudhary")
        csv = _make_record("csv", full_name="P. Choudhary")
        result = merge_records([csv, resume])  # order shouldn't matter
        assert result["full_name"] == "Priyanshu Choudhary"

    def test_email_union_from_multiple_sources(self):
        resume = _make_record("resume", emails=["a@gmail.com"])
        github = _make_record("github", emails=["b@gmail.com"])
        result = merge_records([resume, github])
        assert "a@gmail.com" in result["emails"]
        assert "b@gmail.com" in result["emails"]

    def test_duplicate_emails_deduplicated(self):
        resume = _make_record("resume", emails=["abc@gmail.com"])
        csv = _make_record("csv", emails=["ABC@GMAIL.COM"])
        result = merge_records([resume, csv])
        assert result["emails"].count("abc@gmail.com") == 1

    def test_skills_merged_from_all_sources(self):
        resume = _make_record("resume", skills=["C++", "MongoDB"])
        github = _make_record("github", skills=["nodejs", "docker"])
        result = merge_records([resume, github])
        skill_names = [s["name"] for s in result["skills"]]
        assert "C++" in skill_names
        assert "MongoDB" in skill_names
        assert "Node.js" in skill_names

    def test_skill_sources_tracked(self):
        resume = _make_record("resume", skills=["C++"])
        github = _make_record("github", skills=["cpp"])  # same skill, different spelling
        result = merge_records([resume, github])
        cpp_skill = next((s for s in result["skills"] if s["name"] == "C++"), None)
        assert cpp_skill is not None
        assert "resume" in cpp_skill["sources"]
        assert "github" in cpp_skill["sources"]

    def test_multi_source_skill_has_higher_confidence(self):
        resume = _make_record("resume", skills=["Python"])
        result_one = merge_records([resume])
        one_source_conf = result_one["skills"][0]["confidence"]

        github = _make_record("github", skills=["python"])
        result_two = merge_records([resume, github])
        two_source_conf = next(
            s["confidence"] for s in result_two["skills"] if s["name"] == "Python"
        )
        assert two_source_conf > one_source_conf

    def test_candidate_id_is_deterministic(self):
        record = _make_record("resume", full_name="Jane Doe", emails=["jane@example.com"])
        r1 = merge_records([record])
        r2 = merge_records([record])
        assert r1["candidate_id"] == r2["candidate_id"]

    def test_provenance_populated(self):
        record = _make_record("resume", full_name="Alice Bob", emails=["alice@x.com"])
        result = merge_records([record])
        assert len(result["provenance"]) > 0

    def test_phone_normalized_in_output(self):
        record = _make_record("csv", phones=["9876543210"])
        result = merge_records([record])
        assert "+919876543210" in result["phones"]

    def test_overall_confidence_increases_with_sources(self):
        r1 = merge_records([_make_record("resume", full_name="X")])
        r2 = merge_records([
            _make_record("resume", full_name="X"),
            _make_record("csv", full_name="X"),
        ])
        assert r2["overall_confidence"] >= r1["overall_confidence"]

    def test_name_title_cased(self):
        record = _make_record("resume", full_name="john doe")
        result = merge_records([record])
        assert result["full_name"] == "John Doe"

    def test_empty_record_skipped(self):
        records = [
            {},
            _make_record("resume", full_name="Test User"),
            None,
        ]
        result = merge_records(records)
        assert result["full_name"] == "Test User"
