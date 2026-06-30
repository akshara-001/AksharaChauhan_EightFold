"""
Skill normalizer.
Maps variant spellings to canonical names using:
  1. Exact match in canonical map (lowercased key)
  2. Fuzzy match via rapidfuzz (threshold 85)
  3. Passthrough if no match found
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Canonical skill map: lowercased variant -> canonical form
CANONICAL: dict[str, str] = {
    # JavaScript ecosystem
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "node_js": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "express js": "Express.js",
    "react": "React.js",
    "reactjs": "React.js",
    "react.js": "React.js",
    "react js": "React.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "next js": "Next.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "vue js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    # C family
    "cpp": "C++",
    "c++": "C++",
    "c plus plus": "C++",
    "c#": "C#",
    "csharp": "C#",
    "c sharp": "C#",
    # Python
    "python3": "Python",
    "python 3": "Python",
    "py": "Python",
    "python": "Python",
    # Databases
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "mongo db": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "redis": "Redis",
    "elastic": "Elasticsearch",
    "elasticsearch": "Elasticsearch",
    # Cloud / DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    # Languages
    "java": "Java",
    "golang": "Go",
    "go lang": "Go",
    "rust": "Rust",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "ruby": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "kotlin": "Kotlin",
    # Other
    "graphql": "GraphQL",
    "rest": "REST API",
    "rest api": "REST API",
    "restapi": "REST API",
    "git": "Git",
    "github": "GitHub",
    "linux": "Linux",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
}

# Build reverse lookup: canonical (lowercased) -> canonical
_CANONICAL_LOWER = {v.lower(): v for v in CANONICAL.values()}


def normalize_skill(raw: str) -> str:
    """
    Normalize a single skill string to its canonical form.

    1. Strip, lowercase, check canonical map.
    2. Fuzzy match against all canonical keys (threshold 85).
    3. Return as-is (title-cased) if no match.
    """
    if not raw or not isinstance(raw, str):
        return raw

    stripped = raw.strip()
    if not stripped:
        return stripped

    lowered = stripped.lower()

    # 1. Exact match in canonical map
    if lowered in CANONICAL:
        return CANONICAL[lowered]

    # 2. Check if it's already a canonical value
    if lowered in _CANONICAL_LOWER:
        return _CANONICAL_LOWER[lowered]

    # 3. Fuzzy match
    try:
        from rapidfuzz import process, fuzz

        all_keys = list(CANONICAL.keys())
        match = process.extractOne(
            lowered,
            all_keys,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=85,
        )
        if match:
            return CANONICAL[match[0]]
    except ImportError:
        logger.debug("rapidfuzz not installed; fuzzy matching skipped")
    except Exception as e:
        logger.debug(f"Fuzzy match error for {raw!r}: {e}")

    # 4. Passthrough — title-case unknown skills
    return stripped.title() if stripped.islower() else stripped


def normalize_skills(raw_list: List[str]) -> List[str]:
    """
    Normalize a list of skills and deduplicate (case-insensitive).
    Preserves order of first occurrence.
    """
    seen: dict[str, str] = {}  # lowercased -> canonical
    for raw in raw_list:
        canonical = normalize_skill(raw)
        if canonical:
            key = canonical.lower()
            if key not in seen:
                seen[key] = canonical
    return list(seen.values())
