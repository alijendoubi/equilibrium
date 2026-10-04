"""Ingestion layer: one small connector per source (fetch -> committed cache -> normalize).

Sources: Monarch (diseases, genes, gene-disease, phenotypes), HPO (phenotype IC), GO via Monarch
(mechanisms), ClinVar (variant counts), ClinicalTrials.gov (studies) and the hand-curated YAML
in data/curated/. Refresh the cache with ``uv run python -m atlas.ingest fetch``.
"""
