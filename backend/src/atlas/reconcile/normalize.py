"""Deterministic string normalisation for entity names. Pure functions, no I/O.

Two levels:

* `normalize_text` is a faithful canonical form: NFKC, casefold, Greek letters spelled out,
  hyphen/punctuation variants collapsed to spaces, roman numerals II..X turned into digits.
  "Gaucher disease, type II" and "gaucher disease type 2" normalise to the same string.
* `match_key` additionally drops generic filler words ("disease", "syndrome", "disorder",
  "type", "the", "of", ...) so "Gaucher disease type 2" == "Gaucher type II" == "gaucher 2".
  Clinically meaningful qualifiers are KEPT: "neuronopathic Gaucher type 2" does NOT equal
  "Gaucher disease type 2" lexically. That pairing is left to embeddings or the LLM step.
"""

import re
import unicodedata
from collections.abc import Iterable

GREEK_LETTERS: dict[str, str] = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "ζ": "zeta",
    "η": "eta",
    "θ": "theta",
    "ι": "iota",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "ν": "nu",
    "ξ": "xi",
    "π": "pi",
    "ρ": "rho",
    "σ": "sigma",
    "ς": "sigma",
    "τ": "tau",
    "φ": "phi",
    "χ": "chi",
    "ψ": "psi",
    "ω": "omega",
}

# Numerals that are unambiguous as standalone tokens.
_ROMAN_ALWAYS: dict[str, str] = {
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
}
# Single letters are only numerals right after "type" ("type I", but not "vitamin D" style).
_ROMAN_AFTER_TYPE: dict[str, str] = {"i": "1", "v": "5", "x": "10"}

FILLER_WORDS: frozenset[str] = frozenset(
    {"disease", "syndrome", "disorder", "type", "the", "of", "a", "an", "and", "form"}
)

_DASHES = re.compile(r"[‐-―−­_/]")
_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def _spell_greek(text: str) -> str:
    return "".join(f" {GREEK_LETTERS[ch]} " if ch in GREEK_LETTERS else ch for ch in text)


def _convert_numerals(tokens: list[str]) -> list[str]:
    converted: list[str] = []
    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index > 0 else ""
        if token in _ROMAN_ALWAYS:
            converted.append(_ROMAN_ALWAYS[token])
        elif previous == "type" and token in _ROMAN_AFTER_TYPE:
            converted.append(_ROMAN_AFTER_TYPE[token])
        else:
            converted.append(token)
    return converted


def normalize_text(text: str) -> str:
    """Canonical lower-case form with punctuation, dashes, Greek letters and numerals unified."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = _spell_greek(value)
    value = _DASHES.sub(" ", value).replace("-", " ")
    value = value.replace("'", "")  # "Parkinson's" -> "parkinsons"
    value = _NON_WORD.sub(" ", value)
    tokens = _SPACES.sub(" ", value).strip().split(" ")
    return " ".join(_convert_numerals([t for t in tokens if t]))


def tokens(text: str) -> tuple[str, ...]:
    """Tokens of the normalised text, in order."""
    normalised = normalize_text(text)
    return tuple(normalised.split(" ")) if normalised else ()


def content_tokens(text: str) -> tuple[str, ...]:
    """Tokens with filler words removed (falls back to all tokens if nothing is left)."""
    all_tokens = tokens(text)
    kept = tuple(t for t in all_tokens if t not in FILLER_WORDS)
    return kept or all_tokens


def match_key(text: str) -> str:
    """Lexical identity key: normalised content tokens joined by spaces."""
    return " ".join(content_tokens(text))


def token_jaccard(left: str, right: str) -> float:
    """Jaccard overlap of content-token sets, in [0, 1]."""
    a, b = set(content_tokens(left)), set(content_tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def unique_keys(texts: Iterable[str]) -> tuple[str, ...]:
    """Distinct non-empty match keys, first occurrence order."""
    seen: dict[str, None] = {}
    for text in texts:
        key = match_key(text)
        if key:
            seen.setdefault(key, None)
    return tuple(seen)
