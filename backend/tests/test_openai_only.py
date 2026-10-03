"""Guard: Atlas uses OpenAI as its only LLM provider (challenge requirement, PROJECT_PLAN 8a).

Walks backend/src with `ast`, so comments and strings that merely mention a provider are fine,
but any import of a non-OpenAI LLM SDK fails the suite.
"""

import ast
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SRC = BACKEND / "src"
PYPROJECT = BACKEND / "pyproject.toml"

BANNED_MODULES = frozenset(
    {
        "anthropic",
        "claude_agent_sdk",
        "google.generativeai",
        "google.genai",
        "google.ai.generativelanguage",
        "vertexai",
        "mistralai",
        "cohere",
        "ollama",
        "groq",
        "together",
        "replicate",
        "fireworks",
        "ai21",
        "voyageai",
        "huggingface_hub",
        "litellm",
        "langchain_anthropic",
        "langchain_google_genai",
        "langchain_google_vertexai",
        "langchain_mistralai",
        "langchain_cohere",
        "langchain_ollama",
        "langchain_groq",
        "langchain_together",
        "langchain_fireworks",
        "langchain_aws",
    }
)
_DYNAMIC_IMPORTERS = frozenset({"import_module", "__import__"})


def _is_banned(module: str) -> bool:
    return any(module == banned or module.startswith(f"{banned}.") for banned in BANNED_MODULES)


def _imported_modules(tree: ast.AST) -> Iterator[str]:
    """Absolute module names imported statically, or dynamically with a literal name."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
            yield from (f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            first = node.args[0]
            if (
                name in _DYNAMIC_IMPORTERS
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
            ):
                yield first.value


def banned_imports(source: str) -> list[str]:
    return sorted({m for m in _imported_modules(ast.parse(source)) if _is_banned(m)})


def _dependency_names() -> set[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    requirements = data["project"]["dependencies"]
    return {re.split(r"[\s\[<>=!~;]", req, maxsplit=1)[0].lower() for req in requirements}


def test_backend_src_imports_no_other_llm_sdk() -> None:
    files = sorted(SRC.rglob("*.py"))
    assert files, f"no Python files found under {SRC}"

    offenders = {
        str(path.relative_to(BACKEND)): found
        for path in files
        if (found := banned_imports(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}, f"non-OpenAI LLM SDK imports found: {offenders}"


def test_openai_is_a_declared_dependency() -> None:
    assert "openai" in _dependency_names()


def test_no_other_llm_sdk_is_a_declared_dependency() -> None:
    names = {name.replace("-", "_") for name in _dependency_names()}
    top_level = {module.split(".")[0] for module in BANNED_MODULES} - {"google"}

    assert names & top_level == set()
    assert not names & {"google_generativeai", "google_genai"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import anthropic", ["anthropic"]),
        ("import anthropic as a", ["anthropic"]),
        ("from anthropic import Anthropic", ["anthropic", "anthropic.Anthropic"]),
        ("import google.generativeai as genai", ["google.generativeai"]),
        ("from google import genai", ["google.genai"]),
        ("from google.genai import types", ["google.genai", "google.genai.types"]),
        ("from mistralai.client import Mistral", ["mistralai.client", "mistralai.client.Mistral"]),
        ("import cohere, os", ["cohere"]),
        (
            "from langchain_anthropic import ChatAnthropic",
            ["langchain_anthropic", "langchain_anthropic.ChatAnthropic"],
        ),
        ("def f():\n    import ollama", ["ollama"]),
        ("import importlib\nimportlib.import_module('groq')", ["groq"]),
        ("__import__('together')", ["together"]),
    ],
)
def test_detector_catches_banned_imports(source: str, expected: list[str]) -> None:
    assert banned_imports(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "import openai",
        "from openai import OpenAI",
        "from langchain_openai import ChatOpenAI",
        "from google.protobuf import message",
        "import anthropicish",
        "# import anthropic\nx = 'import cohere'",
        "from . import anthropic",
        "import importlib\nimportlib.import_module(name)",
    ],
)
def test_detector_allows_openai_and_non_llm_imports(source: str) -> None:
    assert banned_imports(source) == []
