import type { EvidenceType, MatchReason, NodeType } from "@/lib/api/types";

/** Colour carries meaning: teal = who shares this, amber = what exists, violet = who to act with. */
export type Tone = "cluster" | "evidence" | "action";

export const NODE_TYPE_LABEL: Record<NodeType, string> = {
  disease: "Disease",
  gene: "Gene",
  variant: "Variant",
  mechanism: "Mechanism",
  phenotype: "Symptom",
  patient_group: "Patient group",
  publication: "Publication",
  study: "Study",
  asset: "Asset",
  investigator: "Investigator",
  funder: "Funder",
};

export const NODE_TYPE_TONE: Record<NodeType, Tone> = {
  disease: "cluster",
  gene: "cluster",
  variant: "cluster",
  mechanism: "cluster",
  phenotype: "cluster",
  patient_group: "action",
  investigator: "action",
  funder: "action",
  publication: "evidence",
  study: "evidence",
  asset: "evidence",
};

export const TONE_TEXT: Record<Tone, string> = {
  cluster: "text-cluster",
  evidence: "text-evidence",
  action: "text-action",
};

export const TONE_BORDER: Record<Tone, string> = {
  cluster: "border-cluster",
  evidence: "border-evidence",
  action: "border-action",
};

export const TONE_BG: Record<Tone, string> = {
  cluster: "bg-cluster",
  evidence: "bg-evidence",
  action: "bg-action",
};

export const MATCH_REASON_LABEL: Record<MatchReason, string> = {
  exact: "Exact match",
  synonym: "Synonym match",
  semantic: "Related meaning",
};

export const EVIDENCE_LABEL: Record<EvidenceType, string> = {
  observed: "Observed",
  curated: "Curated",
  inferred: "Hypothesis",
};

export const EVIDENCE_DESCRIPTION: Record<EvidenceType, string> = {
  observed: "Stated directly by a primary record, such as a trial registry entry.",
  curated: "Asserted by an expert-curated knowledge base, or by our team with a cited source.",
  inferred:
    "Produced by our pipeline (text extraction or graph analytics). A hypothesis, not proof.",
};

const RELATION_LABEL: Record<string, string> = {
  caused_by: "caused by",
  risk_factor_for: "is a risk factor for",
  participates_in: "takes part in",
  has_mechanism: "has mechanism",
  has_phenotype: "has symptom",
  represents: "represents",
  funds: "funds",
  studies_condition: "studies",
  tests_intervention: "tests",
  mentions: "mentions",
  claims: "reports on",
  shares_mechanism_with: "shares mechanism with",
  similar_phenotype_to: "has similar symptoms to",
};

export function relationLabel(relation: string): string {
  return RELATION_LABEL[relation] ?? relation.replaceAll("_", " ");
}

/** Prefixes shown without the namespace, e.g. "clinicaltrials:NCT05778617" -> "NCT05778617". */
const BARE_DISPLAY_PREFIXES = ["clinicaltrials:"];

/** Human display text for a node id. The full CURIE stays the key in data and URLs. */
export function displayId(id: string): string {
  const prefix = BARE_DISPLAY_PREFIXES.find((p) => id.startsWith(p));
  return prefix ? id.slice(prefix.length) : id;
}

/** Page for a node. Every node type uses the summary-first node page. */
export function nodeHref(id: string): string {
  return `/disease/${encodeURIComponent(id)}`;
}

/** Patient action view for a disease (ids are URL-encoded, so "MONDO:0009266" -> "MONDO%3A0009266"). */
export function actionsHref(id: string): string {
  return `/actions/${encodeURIComponent(id)}`;
}

/** Cluster view (ids are URL-encoded like node ids). */
export function clusterHref(id: string): string {
  return `/clusters/${encodeURIComponent(id)}`;
}

export function pathHref(from: string, to: string): string {
  return `/path?${new URLSearchParams({ from, to }).toString()}`;
}

export function searchHref(q: string): string {
  return `/search?${new URLSearchParams({ q }).toString()}`;
}

export function formatConfidence(value: number): string {
  return value.toFixed(2);
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
