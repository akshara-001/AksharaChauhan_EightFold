"""
GitHub API Fetcher — Live data from real GitHub REST API.

Fetches public profile + repositories for any GitHub user.
No authentication required for public profiles.
Rate limit: 60 requests/hour (unauthenticated).

Endpoints used:
    GET https://api.github.com/users/{login}
    GET https://api.github.com/users/{login}/repos?per_page=30&sort=updated

Usage:
    from parsers.github_fetcher import fetch

    record = fetch("priyanshu-dev")
    record = fetch("github.com/priyanshu-dev")
    record = fetch("https://github.com/priyanshu-dev")
"""

import logging
import re
import time
import urllib.error
import urllib.request
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 10  # seconds
MAX_REPOS = 30        # fetch this many repos per user


# ---------------------------------------------------------------------------
# Username extraction
# ---------------------------------------------------------------------------

def _parse_username(raw: str) -> Optional[str]:
    """
    Extract a GitHub username from any reasonable input.

    Handles:
        "priyanshu-dev"
        "github.com/priyanshu-dev"
        "https://github.com/priyanshu-dev"
        "https://github.com/priyanshu-dev/"
        "@priyanshu-dev"

    Returns:
        Cleaned username string, or None if not parseable.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip().lstrip("@")

    # Full URL
    m = re.search(r"github\.com/([a-zA-Z0-9\-_]+)", raw, re.IGNORECASE)
    if m:
        return m.group(1)

    # Plain username (only alphanumeric + hyphens/underscores)
    if re.match(r"^[a-zA-Z0-9\-_]+$", raw):
        return raw

    logger.warning(f"[github_fetcher] Cannot parse username from: {raw!r}")
    return None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_json(url: str, token: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT) -> Optional[Any]:
    """
    Make a GET request and return parsed JSON.

    Args:
        url:     Full API URL.
        token:   Optional GitHub personal access token (raises rate limit to 5000/hr).
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON (dict or list), or None on failure.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "candidate-transformer/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Check rate limit headers
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            logger.debug(f"[github_fetcher] GET {url} → {resp.status} (rate limit remaining: {remaining})")

            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
            else:
                logger.warning(f"[github_fetcher] Unexpected status {resp.status} for {url}")
                return None

    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.warning(f"[github_fetcher] User not found (404): {url}")
        elif e.code == 403:
            logger.warning(f"[github_fetcher] Rate limit hit (403). Add --github-token to increase limit.")
        elif e.code == 401:
            logger.error(f"[github_fetcher] Invalid token (401)")
        else:
            logger.error(f"[github_fetcher] HTTP {e.code} for {url}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"[github_fetcher] Network error for {url}: {e.reason}")
        return None
    except Exception as exc:
        logger.error(f"[github_fetcher] Unexpected error for {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Data extractors
# ---------------------------------------------------------------------------

def _extract_skills_from_repos(repos: List[Dict[str, Any]]) -> List[str]:
    """
    Pull programming languages and topics from repo objects.
    Returns deduplicated list preserving order.
    """
    seen: dict[str, str] = {}  # lowercased -> original

    for repo in repos:
        # Primary language
        lang = repo.get("language")
        if lang and isinstance(lang, str):
            key = lang.lower()
            if key not in seen:
                seen[key] = lang

        # Topics (e.g. ["nodejs", "rest-api", "docker"])
        for topic in repo.get("topics", []):
            if isinstance(topic, str) and topic:
                key = topic.lower()
                if key not in seen:
                    seen[key] = topic

    return list(seen.values())


def _fetch_repos(username: str, token: Optional[str], timeout: int) -> List[Dict[str, Any]]:
    """Fetch user's repositories from GitHub API."""
    url = (
        f"{GITHUB_API_BASE}/users/{username}/repos"
        f"?per_page={MAX_REPOS}&sort=updated&type=owner"
    )
    result = _get_json(url, token=token, timeout=timeout)
    if not isinstance(result, list):
        logger.warning(f"[github_fetcher] Could not fetch repos for {username!r}")
        return []
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch(
    username_or_url: str,
    token: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Fetch a GitHub user's public profile and return a raw candidate record.

    Args:
        username_or_url: GitHub username, profile URL, or github.com/username.
        token:           Optional GitHub personal access token.
        timeout:         HTTP request timeout in seconds.

    Returns:
        Raw candidate record dict with source="github".
        Returns {} on failure — never raises.
    """
    username = _parse_username(username_or_url)
    if not username:
        return {}

    logger.info(f"[github_fetcher] Fetching profile for: {username}")

    # ── 1. User profile ───────────────────────────────────────────────────────
    profile_url = f"{GITHUB_API_BASE}/users/{username}"
    profile = _get_json(profile_url, token=token, timeout=timeout)

    if not profile or not isinstance(profile, dict):
        logger.error(f"[github_fetcher] Failed to fetch profile for {username!r}")
        return {}

    # ── 2. Repositories (for skills) ──────────────────────────────────────────
    logger.info(f"[github_fetcher] Fetching repos for: {username}")
    repos = _fetch_repos(username, token=token, timeout=timeout)
    logger.info(f"[github_fetcher] Found {len(repos)} repo(s)")

    # ── 3. Build record ───────────────────────────────────────────────────────
    try:
        email = profile.get("email") or ""
        emails: List[str] = [email.strip().lower()] if email and email.strip() else []

        # Skills = explicit skills field (if present) + repo languages/topics
        explicit_skills: List[str] = profile.get("skills", [])  # custom field, may not exist
        repo_skills: List[str] = _extract_skills_from_repos(repos)
        all_skills = list(dict.fromkeys(explicit_skills + repo_skills))  # dedup, preserve order

        github_url = profile.get("html_url") or f"https://github.com/{username}"

        # Count stars for context (stored in _meta, not merged into output)
        total_stars = sum(r.get("stargazers_count", 0) for r in repos)
        top_repos = [
            {
                "name": r.get("name"),
                "language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "description": r.get("description"),
                "topics": r.get("topics", []),
            }
            for r in sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:5]
        ]

        record: Dict[str, Any] = {
            "source":    "github",
            "full_name": profile.get("name") or None,
            "headline":  profile.get("bio") or None,
            "emails":    emails,
            "phones":    [],
            "location":  profile.get("location") or None,
            "skills":    all_skills,
            "experience": [],
            "education":  [],
            "links": {
                "github":   github_url,
                "linkedin": None,
                "twitter":  profile.get("twitter_username") and f"https://twitter.com/{profile['twitter_username']}",
                "blog":     profile.get("blog") or None,
            },
            "_meta": {
                "github_login":   username,
                "public_repos":   profile.get("public_repos", 0),
                "followers":      profile.get("followers", 0),
                "total_stars":    total_stars,
                "top_repos":      top_repos,
                "fetched_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

        logger.info(
            f"[github_fetcher] Done: name={record['full_name']!r}, "
            f"skills={len(record['skills'])}, repos={len(repos)}, "
            f"stars={total_stars}"
        )
        return record

    except Exception as exc:
        logger.error(f"[github_fetcher] Error building record for {username!r}: {exc}")
        return {}
