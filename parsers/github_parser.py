"""
GitHub Parser — Semi-structured source.
Accepts a GitHub API-style JSON payload (user profile + pinned repos).
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _extract_skills_from_repos(repos: List[Dict[str, Any]]) -> List[str]:
    """Pull programming language names from repo objects."""
    langs: List[str] = []
    for repo in repos:
        lang = repo.get("language")
        if lang and isinstance(lang, str):
            langs.append(lang)
        # Also check 'topics' list
        for topic in repo.get("topics", []):
            if isinstance(topic, str):
                langs.append(topic)
    return list(dict.fromkeys(langs))  # deduplicate, preserve order


def parse(path: str) -> Dict[str, Any]:
    """
    Parse a GitHub user JSON file.

    Expected shape (subset of GitHub API /users/{login}):
    {
        "login": "priyanshu-dev",
        "name": "Priyanshu Choudhary",
        "email": "abc@gmail.com",
        "bio": "Backend Engineer",
        "location": "Bangalore",
        "html_url": "https://github.com/priyanshu-dev",
        "skills": ["cpp", "nodejs", "mongodb"],   // optional custom field
        "repos": [{"language": "Python", "topics": ["fastapi"]}]
    }

    Args:
        path: Path to the GitHub JSON file.

    Returns:
        Raw candidate record dict. Returns {} on failure.
    """
    logger.info(f"[github_parser] Parsing: {path}")

    try:
        with open(path, encoding="utf-8") as fh:
            data: Dict[str, Any] = json.load(fh)
    except FileNotFoundError:
        logger.warning(f"[github_parser] File not found: {path!r}")
        return {}
    except json.JSONDecodeError as exc:
        logger.error(f"[github_parser] Invalid JSON in {path!r}: {exc}")
        return {}
    except Exception as exc:
        logger.error(f"[github_parser] Failed to read {path!r}: {exc}")
        return {}

    try:
        email = data.get("email", "")
        emails: List[str] = [email.strip().lower()] if email and email.strip() else []

        # Skills from explicit field OR from repos
        explicit_skills: List[str] = data.get("skills", [])
        repo_skills: List[str] = _extract_skills_from_repos(data.get("repos", []))
        all_skills = list(dict.fromkeys(explicit_skills + repo_skills))

        github_url = data.get("html_url") or (
            f"https://github.com/{data['login']}" if data.get("login") else None
        )

        record: Dict[str, Any] = {
            "source": "github",
            "full_name": data.get("name") or None,
            "headline": data.get("bio") or None,
            "emails": emails,
            "phones": [],
            "location": data.get("location") or None,
            "skills": all_skills,
            "experience": [],
            "education": [],
            "links": {
                "github": github_url,
                "linkedin": None,
            },
        }

        logger.info(
            f"[github_parser] Extracted: name={record['full_name']!r}, "
            f"skills={len(record['skills'])}"
        )
        return record

    except Exception as exc:
        logger.error(f"[github_parser] Unexpected error: {exc}")
        return {}
