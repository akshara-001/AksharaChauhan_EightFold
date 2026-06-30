"""Unit tests for normalizers/skill.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from normalizers.skill import normalize_skill, normalize_skills


class TestNormalizeSkill:

    def test_nodejs_variants(self):
        assert normalize_skill("nodejs") == "Node.js"
        assert normalize_skill("Node JS") == "Node.js"
        assert normalize_skill("NODE.JS") == "Node.js"
        assert normalize_skill("node.js") == "Node.js"

    def test_cpp_variants(self):
        assert normalize_skill("cpp") == "C++"
        assert normalize_skill("c++") == "C++"
        assert normalize_skill("C++") == "C++"

    def test_mongodb_variants(self):
        assert normalize_skill("mongodb") == "MongoDB"
        assert normalize_skill("mongo") == "MongoDB"
        assert normalize_skill("Mongo DB") == "MongoDB"

    def test_expressjs_variants(self):
        assert normalize_skill("expressjs") == "Express.js"
        assert normalize_skill("express.js") == "Express.js"
        assert normalize_skill("Express JS") == "Express.js"

    def test_unknown_skill_passthrough(self):
        result = normalize_skill("SomeObscureLib")
        assert result == "SomeObscureLib"

    def test_empty_string(self):
        result = normalize_skill("")
        assert result == ""

    def test_none_passthrough(self):
        result = normalize_skill(None)
        assert result is None

    def test_normalize_skills_dedup(self):
        skills = ["nodejs", "Node.js", "NODE.JS", "mongodb", "MongoDB"]
        result = normalize_skills(skills)
        names = [s for s in result]
        assert names.count("Node.js") == 1
        assert names.count("MongoDB") == 1

    def test_normalize_skills_preserves_unknowns(self):
        skills = ["nodejs", "QuantumComputing"]
        result = normalize_skills(skills)
        assert "Node.js" in result
        assert "Quantumcomputing" in result or "QuantumComputing" in result

    def test_kubernetes_alias(self):
        assert normalize_skill("k8s") == "Kubernetes"


class TestNormalizeSkillsFuzzy:

    def test_fuzzy_match_close_spelling(self):
        # "postgressql" should fuzzy-match to "PostgreSQL"
        result = normalize_skill("postgres")
        assert result == "PostgreSQL"

    def test_typescript_alias(self):
        assert normalize_skill("typescript") == "TypeScript"
        assert normalize_skill("ts") == "TypeScript"
