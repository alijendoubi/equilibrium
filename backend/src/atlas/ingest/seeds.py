"""Seed identifiers for the gba1 slice, copied from docs/DATA_SOURCES.md (verified 2026-10-03).

Do not add ids here that are not in the verified seed list.
"""

from typing import Final

SLICE_SLUG: Final = "gba1"

# MONDO id -> role in the story (see docs/DATA_SOURCES.md "Diseases").
SEED_DISEASES: Final[dict[str, str]] = {
    "MONDO:0018150": "search_entry",  # Gaucher disease (grouping)
    "MONDO:0009265": "context",  # Gaucher disease type I
    "MONDO:0009266": "hero",  # Gaucher disease type II
    "MONDO:0009267": "hero",  # Gaucher disease type III
    "MONDO:0011945": "context",  # Gaucher disease perinatal lethal
    "MONDO:0009268": "optional",  # Gaucher-ophthalmoplegia-cardiovascular calcification
    "MONDO:0008199": "partner",  # late-onset Parkinson disease (GBA1-PD susceptibility)
    "MONDO:0007488": "optional",  # Lewy body dementia
    "MONDO:0012517": "gap",  # Gaucher disease due to saposin C deficiency
    "MONDO:0012719": "neighbour",  # combined PSAP deficiency
    "MONDO:0859183": "hypothesis",  # Parkinson disease 24, susceptibility to (PSAP; contested)
    "MONDO:0009699": "neighbour",  # action myoclonus-renal failure syndrome (SCARB2)
    "MONDO:0009756": "neighbour",  # Niemann-Pick disease type A (SMPD1)
    "MONDO:0011871": "neighbour",  # Niemann-Pick disease type B (SMPD1)
    "MONDO:0011706": "neighbour",  # Kufor-Rakeb syndrome (ATP13A2)
    "MONDO:0012414": "neighbour",  # neuronal ceroid lipofuscinosis 10 (CTSD)
    "MONDO:0013737": "neighbour",  # hereditary spastic paraplegia 46 (GBA2)
}

# HGNC id -> approved symbol (see docs/DATA_SOURCES.md "Genes").
SEED_GENES: Final[dict[str, str]] = {
    "HGNC:4177": "GBA1",
    "HGNC:9498": "PSAP",
    "HGNC:1665": "SCARB2",
    "HGNC:11120": "SMPD1",
    "HGNC:18986": "GBA2",
    "HGNC:30213": "ATP13A2",
    "HGNC:2529": "CTSD",
    "HGNC:18618": "LRRK2",
    "HGNC:11138": "SNCA",
}

# Trials and registries verified on ClinicalTrials.gov (docs/DATA_SOURCES.md "Trials").
SEED_TRIALS: Final[tuple[str, ...]] = (
    "NCT05778617",
    "NCT04388969",
    "NCT04127578",
    "NCT04411654",
    "NCT05222906",
    "NCT02906020",
    "NCT05819359",
    "NCT00358943",
    "NCT03291223",
)

HERO_DISEASES: Final = ("MONDO:0009266", "MONDO:0009267")
PARTNER_DISEASE: Final = "MONDO:0008199"
GAP_DISEASE: Final = "MONDO:0012517"
HERO_GENE: Final = "HGNC:4177"
