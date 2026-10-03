/**
 * Types mirroring the planned Atlas API (PROJECT_PLAN section 9, docs/EVIDENCE_MODEL.md).
 *
 * These are the wire shapes the backend must return under /api/v1. Field names are
 * snake_case on purpose so the JSON can be passed through without mapping.
 * Runtime validation lives in ./schemas.ts and is checked against these types.
 */

export type NodeType =
  | "disease"
  | "gene"
  | "variant"
  | "mechanism"
  | "phenotype"
  | "patient_group"
  | "publication"
  | "study"
  | "asset"
  | "investigator"
  | "funder";

/** How a claim was established. Inferred edges render dashed and labelled "hypothesis". */
export type EvidenceType = "observed" | "curated" | "inferred";

/** Why a search hit matched: label/xref, a stored synonym, or embedding similarity. */
export type MatchReason = "exact" | "synonym" | "semantic";

export type AttributeValue = string | number | boolean;

export interface AtlasNode {
  /** Stable CURIE-like id, e.g. "MONDO:0009267", "HGNC:4177", "NCT05778617". */
  id: string;
  type: NodeType;
  label: string;
  synonyms: string[];
  description?: string;
  xrefs?: string[];
  /** e.g. { ic: 6.1 } for phenotypes; { phase, status, enrollment } for studies; { url } for orgs. */
  attributes?: Record<string, AttributeValue>;
}

export interface Provenance {
  /** Source system: omim, hpo, go, ctgov, pubmed, curated, analytics, ... */
  source: string;
  /** The specific record that asserts the relation. */
  source_record_id: string;
  /** Human-checkable link. Null only when source === "analytics". */
  url: string | null;
  /** ISO 8601 UTC. */
  retrieved_at: string;
  /** Verbatim supporting text (required for extracted edges). */
  evidence_quote?: string;
  /** For computed (analytics) edges: the edges they were derived from. */
  supporting_edge_ids?: string[];
}

export interface Edge {
  /** Deterministic id ("e_" + sha1 prefix in the real snapshot). Explain cites these. */
  id: string;
  source_id: string;
  target_id: string;
  relation: string;
  provenance: Provenance;
  /** Rubric-derived, never LLM self-confidence. In [0, 1]. */
  confidence: number;
  /** Human-readable rubric lines, e.g. "curated KB base 0.90". */
  confidence_reasons: string[];
  evidence_type: EvidenceType;
  /** Ids of edges that contradict this one. */
  contradicted_by: string[];
  qualifiers?: Record<string, string>;
}

/** GET /api/v1/search?q=&types= */
export interface SearchResult {
  node: AtlasNode;
  score: number;
  match_reason: MatchReason;
  /** The text that matched (the label, the synonym, or the closest phrase for semantic). */
  matched_text: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  /** What was searched, so an empty result can be honest about coverage. */
  searched: string[];
}

export type CoverageStatus = "supported" | "weak" | "gap";

/** GET /api/v1/nodes/{id} */
export interface NodeSummary {
  node: AtlasNode;
  counts: { edges: number; by_relation: Record<string, number> };
  /** Top edges touching the node, best first. */
  edges: Edge[];
  /** Every node referenced by `edges` other than `node`. */
  neighbors: AtlasNode[];
  cluster_id: string | null;
  coverage_status: CoverageStatus;
}

export interface Path {
  /** Ordered nodes along the path: nodes[i] and nodes[i + 1] are joined by edges[i]. */
  nodes: AtlasNode[];
  edges: Edge[];
  /** Sum of -log(confidence); lower is better. */
  cost: number;
  has_inferred: boolean;
  has_contradiction: boolean;
}

/** GET /api/v1/paths?from=&to=&k=3 */
export interface PathResponse {
  from: string;
  to: string;
  paths: Path[];
  /** Present when no supported route exists. */
  coverage: CoverageReport | null;
}

export interface Partner {
  node: AtlasNode;
  /** One-line plain-language reason, e.g. "Same gene (GBA1); shared lysosomal mechanism". */
  why: string;
  edge_ids: string[];
}

export interface ReusableAsset {
  node: AtlasNode;
  reusable: string;
  differs: string;
  edge_ids: string[];
}

export interface NextExperiment {
  text: string;
  /** Always true today: a next experiment is a hypothesis, not proof. */
  is_hypothesis: boolean;
  edge_ids: string[];
}

/** GET /api/v1/actions/{disease_id} */
export interface ActionsResponse {
  disease_id: string;
  partners: Partner[];
  assets: ReusableAsset[];
  next_experiment: NextExperiment | null;
  review_checklist: string[];
  /** Present when the honest answer is "no supported route". */
  coverage: CoverageReport | null;
}

export interface SourceSearched {
  source: string;
  source_version?: string;
  query?: string;
  records_found: number;
}

export interface WeakLead {
  path_edge_ids: string[];
  min_confidence: number;
  why_weak: string;
}

/** GET /api/v1/coverage/{node_id} */
export interface CoverageReport {
  query: string;
  result: "supported" | "weak_routes_only" | "no_supported_route";
  searched: SourceSearched[];
  not_searched: string[];
  missing_evidence: string[];
  weak_leads: WeakLead[];
  next_questions: string[];
}
