"""Deterministic normalisation (atlas.reconcile.normalize)."""

import pytest

from atlas.reconcile.normalize import (
    content_tokens,
    match_key,
    normalize_text,
    token_jaccard,
    tokens,
    unique_keys,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gaucher disease, type II", "gaucher disease type 2"),
        ("GAUCHER DISEASE TYPE 2", "gaucher disease type 2"),
        ("Gaucher disease type III", "gaucher disease type 3"),
        ("Gaucher type I", "gaucher type 1"),
        ("vitamin D", "vitamin d"),
        ("Saposin-C deficiency", "saposin c deficiency"),
        ("Saposin–C deficiency", "saposin c deficiency"),
        ("GBA1‑associated Parkinson's disease", "gba1 associated parkinsons disease"),
        ("β-glucocerebrosidase", "beta glucocerebrosidase"),
        ("ＧＢＡ", "gba"),  # full-width letters via NFKC
        ("  many   spaces  ", "many spaces"),
        ("", ""),
        ("!!!", ""),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_type_variants_share_a_match_key() -> None:
    keys = {
        match_key(s)
        for s in (
            "Gaucher disease type II",
            "Gaucher disease, type 2",
            "Gaucher type 2",
            "gaucher-disease type ii",
        )
    }
    assert keys == {"gaucher 2"}


def test_qualifiers_are_kept_documented_behaviour() -> None:
    # "neuronopathic" is clinically meaningful; lexical matching does not drop it.
    assert match_key("neuronopathic Gaucher type 2") != match_key("Gaucher disease type 2")


def test_disease_and_syndrome_are_filler() -> None:
    assert match_key("Parkinson disease") == match_key("Parkinson syndrome") == "parkinson"


def test_content_tokens_fallback_when_all_filler() -> None:
    assert content_tokens("the disease") == ("the", "disease")
    assert tokens("") == ()


def test_token_jaccard() -> None:
    assert token_jaccard("Gaucher disease type 2", "Gaucher type II") == 1.0
    assert token_jaccard("Gaucher 2", "Gaucher 3") == pytest.approx(1 / 3)
    assert token_jaccard("", "x") == 0.0


def test_unique_keys_dedupes_in_order() -> None:
    assert unique_keys(["GBA", "gba", "", "GBA1"]) == ("gba", "gba1")
