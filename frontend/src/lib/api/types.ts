/**
 * Types mirroring the planned Atlas API (PROJECT_PLAN section 9, docs/EVIDENCE_MODEL.md).
 *
 * Field names are snake_case so backend JSON (backend/src/atlas/models/evidence.py,
 * the source of truth) passes through without mapping.
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

/** Controlled edge vocabulary, identical to backend `Relation`. Direction is source -> target. */
export type Relation =
  | "caused_by"
  | "risk_factor_for"
  | "has_variant"
  | "variant_associated_with"
  | "has_mechanism"
  | "participates_in"
  | "has_phenotype"
  | "shares_mechanism_with"
  | "similar_phenotype_to"
  | "mentions"
  | "claims"
  | "authored_by"
  | "studies_condition"
  | "tests_intervention"
  | "investigates"
  | "funds"
  | "works_on"
  | "represents"
  | "operates"
  | "contradicts";

/*
 * Shapes below are what the UI holds AFTER zod parsing (src/lib/api/schemas.ts).
 * Fields the backend may omit (lists, maps, optional provenance fields) are defaulted
 * during parsing, so components never deal with `undefined` for them.
 */

export interface AtlasNode {
  /** CURIE, e.g. "MONDO:0009267", "HGNC:4177", "clinicaltrials:NCT05778617". */
  id: string;
  type: NodeType;
  label: string;
  /** Defaulted to [] when omitted. */
  synonyms: string[];
  /** CURIEs. Defaulted to [] when omitted. */
  xrefs: string[];
  /**
   * str -> str card data (backend `FrozenStrMap`), e.g. { ic: "6.1" } for phenotypes,
   * { phase, status, enrollment } for studies, { url } for orgs, { description } for any node.
   * Defaulted to {} when omitted.
   */
  attributes: Record<string, string>;
}

export interface Provenance {
  /** Source system: omim, hpo, go, ctgov, pubmed, curated, analytics, ... */
  source: string;
  /** The specific record that asserts the relation. */
  source_record_id: string;
  /** Human-checkable link. Null only for inferred edges that list supporting_edge_ids. */
  url: string | null;
  /** ISO 8601 with timezone. */
  retrieved_at: string;
  /** Release or dump date of the source. Optional. */
  source_version?: string | null;
  /** Verbatim supporting text (expected for extracted edges). Optional. */
  evidence_quote?: string | null;
  /** `<kind>:<name>`, e.g. "openai:gpt-...". "openai:" edges must be inferred. Optional. */
  extractor?: string | null;
  /** Edges a computed edge was derived from. Defaulted to [] when omitted. */
  supporting_edge_ids: string[];
}

export interface Edge {
  /** Deterministic backend id: "E:" + first 16 hex of sha256. Explain cites these. */
  id: string;
  source_id: string;
  target_id: string;
  relation: Relation;
  provenance: Provenance;
  /** Rubric-derived, never LLM self-confidence. In [0, 1]. */
  confidence: number;
  /** Human-readable rubric lines, e.g. "curated KB base 0.90". Defaulted to []. */
  confidence_reasons: string[];
  evidence_type: EvidenceType;
  /** Ids of edges that contradict this one. Defaulted to []. */
  contradicted_by: string[];
  /** str -> str, e.g. { zygosity: "heterozygous" }. Defaulted to {}. */
  qualifiers: Record<string, string>;
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

/* Explain: POST /api/v1/explain (backend/src/atlas/explain/models.py). */

export type ExplainAudience = "family" | "researcher";

/** cache = stored OpenAI answer, live = fresh OpenAI call, template = deterministic, no AI. */
export type ExplainSource = "cache" | "live" | "template";

export interface ExplainRequest {
  /** 1..12 edge ids, in path order. */
  edge_ids: string[];
  audience: ExplainAudience;
}

export interface ExplainStep {
  text: string;
  /** Edges this step rests on (at least one). */
  edge_ids: string[];
  is_hypothesis: boolean;
}

export interface ExplainResponse {
  steps: ExplainStep[];
  summary: string;
  caveats: string[];
  source: ExplainSource;
  model: string | null;
  prompt_version: string;
  ai_generated: boolean;
}

/* Clusters: GET /api/v1/clusters and /clusters/{id} (backend/src/atlas/models/clusters.py). */

export interface ClusterSummary {
  id: string;
  /** Top shared gene and mechanism, e.g. "GBA1 · lysosomal protein catabolic process". */
  label: string;
  size: number;
  member_ids: string[];
}

/** How the clusters were computed, so the page can say it plainly. */
export interface ClusterMethod {
  description: string;
  weights: Record<string, number>;
  phenotype_ic_floor: number;
  edge_threshold: number;
  seed: number;
}

/** GET /api/v1/clusters */
export interface ClustersResponse {
  clusters: ClusterSummary[];
  method: ClusterMethod;
}

/** A disease drawn in the cluster view: a member, or the far end of a bridge/counterexample. */
export interface ClusterNode {
  node: AtlasNode;
  cluster_id: string;
  is_member: boolean;
  /** Similarity links above the threshold; drives node size. */
  degree: number;
}

/** A gene, GO mechanism or symptom shared by two or more members. */
export interface SharedFeature {
  node: AtlasNode;
  member_ids: string[];
  /** Information content (symptoms only); higher is more specific. */
  ic: number | null;
}

export interface ClusterFeatures {
  genes: SharedFeature[];
  mechanisms: SharedFeature[];
  phenotypes: SharedFeature[];
}

/** within = solid link inside the cluster; bridge = dashed link to another cluster. */
export type ClusterEdgeKind = "within" | "bridge";

export interface ClusterEdge {
  source_id: string;
  target_id: string;
  kind: ClusterEdgeKind;
  score: number;
  phenotype_score: number;
  gene_score: number;
  mechanism_score: number;
  reasons: string[];
}

export interface ClusterBridge {
  member_id: string;
  other_id: string;
  other_cluster_id: string;
  score: number;
  reasons: string[];
}

/** Same gene, different cluster: the gene alone does not decide the grouping. */
export interface Counterexample {
  gene: AtlasNode;
  member_id: string;
  other_id: string;
  other_cluster_id: string;
  score: number;
  note: string;
}

/** GET /api/v1/clusters/{id} */
export interface ClusterDetail {
  id: string;
  label: string;
  size: number;
  member_ids: string[];
  nodes: ClusterNode[];
  features: ClusterFeatures;
  edges: ClusterEdge[];
  bridges: ClusterBridge[];
  counterexamples: Counterexample[];
}

/* Evidence map: GET /api/v1/graph (backend/src/atlas/models/graph_map.py). */

/** A node drawn on the evidence map. */
export interface MapNode {
  node: AtlasNode;
  /** Edges touching the node on this map (drives node size). */
  degree: number;
  /** Edges touching the node in the whole snapshot. */
  total_degree: number;
  /** Disease cluster (diseases only). */
  cluster_id: string | null;
  /** Hops from the center (0 = center); null on the overview. */
  distance: number | null;
}

/** What the map left out, per node type, so the UI can say "+41 symptoms" instead of hiding it. */
export interface MapTruncation {
  by_type: Record<string, number>;
  nodes_hidden: number;
  edges_hidden: number;
}

/** Counts of what is drawn. */
export interface MapLegend {
  node_types: Record<string, number>;
  relations: Record<string, number>;
  evidence_types: Record<string, number>;
}

/** GET /api/v1/graph?center=&depth=&types=&relations=&min_confidence=&limit= */
export interface GraphMapResponse {
  /** Null for the overview of the whole slice. */
  center: string | null;
  /** 0 for the overview. */
  depth: number;
  nodes: MapNode[];
  edges: Edge[];
  /** Edges that are a `contradicts` claim, or that another edge contradicts. */
  contradiction_edge_ids: string[];
  truncated: MapTruncation;
  legend: MapLegend;
}

/** Query for the evidence map. Omit `center` for the overview. */
export interface GraphQuery {
  center?: string | null;
  depth?: 1 | 2;
  /** Node types to draw. Omitted: everything except symptoms. */
  types?: NodeType[];
  relations?: Relation[];
  minConfidence?: number;
  limit?: number;
}
