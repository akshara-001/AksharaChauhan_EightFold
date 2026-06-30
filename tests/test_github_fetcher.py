"""
Unit tests for parsers/github_fetcher.py

Tests use mocking so no real network calls are made.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from parsers.github_fetcher import _parse_username, _extract_skills_from_repos, fetch


# ---------------------------------------------------------------------------
# Username parsing tests (no network)
# ---------------------------------------------------------------------------

class TestParseUsername:

    def test_plain_username(self):
        assert _parse_username("priyanshu-dev") == "priyanshu-dev"

    def test_full_https_url(self):
        assert _parse_username("https://github.com/priyanshu-dev") == "priyanshu-dev"

    def test_github_com_prefix(self):
        assert _parse_username("github.com/priyanshu-dev") == "priyanshu-dev"

    def test_trailing_slash(self):
        assert _parse_username("https://github.com/priyanshu-dev/") == "priyanshu-dev"

    def test_at_prefix(self):
        assert _parse_username("@torvalds") == "torvalds"

    def test_empty_returns_none(self):
        assert _parse_username("") is None

    def test_none_returns_none(self):
        assert _parse_username(None) is None

    def test_invalid_url_returns_none(self):
        assert _parse_username("not a url or username!!") is None

    def test_username_with_hyphen(self):
        assert _parse_username("john-doe") == "john-doe"

    def test_username_with_numbers(self):
        assert _parse_username("user123") == "user123"


# ---------------------------------------------------------------------------
# Skills extraction from repos (no network)
# ---------------------------------------------------------------------------

class TestExtractSkillsFromRepos:

    def test_extracts_languages(self):
        repos = [
            {"language": "Python", "topics": []},
            {"language": "Go", "topics": []},
        ]
        skills = _extract_skills_from_repos(repos)
        assert "Python" in skills
        assert "Go" in skills

    def test_extracts_topics(self):
        repos = [{"language": None, "topics": ["docker", "kubernetes", "rest-api"]}]
        skills = _extract_skills_from_repos(repos)
        assert "docker" in skills
        assert "kubernetes" in skills

    def test_deduplicates(self):
        repos = [
            {"language": "Python", "topics": ["python"]},
            {"language": "Python", "topics": []},
        ]
        skills = _extract_skills_from_repos(repos)
        assert skills.count("Python") == 1

    def test_null_language_skipped(self):
        repos = [{"language": None, "topics": ["nodejs"]}]
        skills = _extract_skills_from_repos(repos)
        assert "nodejs" in skills
        assert None not in skills

    def test_empty_repos(self):
        assert _extract_skills_from_repos([]) == []


# ---------------------------------------------------------------------------
# Full fetch() with mocked HTTP (no real network calls)
# ---------------------------------------------------------------------------

MOCK_PROFILE = {
    "login": "priyanshu-dev",
    "name": "Priyanshu Choudhary",
    "email": "priyanshu@gmail.com",
    "bio": "Backend Engineer",
    "location": "Bangalore, India",
    "html_url": "https://github.com/priyanshu-dev",
    "public_repos": 10,
    "followers": 42,
    "twitter_username": None,
    "blog": "",
}

MOCK_REPOS = [
    {
        "name": "my-project",
        "language": "Python",
        "topics": ["fastapi", "docker"],
        "stargazers_count": 15,
        "description": "A cool project",
    },
    {
        "name": "another-repo",
        "language": "JavaScript",
        "topics": ["nodejs", "express"],
        "stargazers_count": 5,
        "description": "Another project",
    },
]


class TestFetch:

    def _mock_get_json(self, url, **kwargs):
        if "/repos" in url:
            return MOCK_REPOS
        return MOCK_PROFILE

    def test_returns_correct_source(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        assert result.get("source") == "github"

    def test_extracts_name(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        assert result["full_name"] == "Priyanshu Choudhary"

    def test_extracts_email(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        assert "priyanshu@gmail.com" in result["emails"]

    def test_extracts_skills_from_repos(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        skills = result["skills"]
        assert "Python" in skills
        assert "JavaScript" in skills
        assert "fastapi" in skills
        assert "nodejs" in skills

    def test_extracts_github_link(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        assert result["links"]["github"] == "https://github.com/priyanshu-dev"

    def test_meta_contains_repo_count(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        assert result["_meta"]["public_repos"] == 10

    def test_meta_contains_top_repos(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("priyanshu-dev")
        assert len(result["_meta"]["top_repos"]) > 0

    def test_invalid_username_returns_empty(self):
        result = fetch("!!!invalid!!!")
        assert result == {}

    def test_api_failure_returns_empty(self):
        with patch("parsers.github_fetcher._get_json", return_value=None):
            result = fetch("priyanshu-dev")
        assert result == {}

    def test_accepts_full_url(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("https://github.com/priyanshu-dev")
        assert result["full_name"] == "Priyanshu Choudhary"

    def test_accepts_github_com_prefix(self):
        with patch("parsers.github_fetcher._get_json", side_effect=self._mock_get_json):
            result = fetch("github.com/priyanshu-dev")
        assert result["source"] == "github"

    def test_empty_email_not_added(self):
        profile_no_email = {**MOCK_PROFILE, "email": ""}
        def mock_get(url, **kwargs):
            if "/repos" in url:
                return MOCK_REPOS
            return profile_no_email
        with patch("parsers.github_fetcher._get_json", side_effect=mock_get):
            result = fetch("priyanshu-dev")
        assert result["emails"] == []
