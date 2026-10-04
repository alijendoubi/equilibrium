import { z } from "zod";
import type {
  ActionsResponse,
  AtlasNode,
  ClusterDetail,
  ClustersResponse,
  CoverageReport,
  Edge,
  ExplainRequest,
  ExplainResponse,
  NodeSummary,
  PathResponse,
  SearchResponse,
} from "./types";

/**
 * Runtime validators. They mirror backend/src/atlas/models/evidence.py (the source of truth):
 * node ids are CURIEs, edge ids are "E:" + 16 lowercase hex, and fields the backend may omit
 * are defaulted so the parsed shapes match ./types.ts exactly.
 */

export const CURIE_PATTERN = /^[A-Za-z][A-Za-z0-9_.-]*:\S+$/;
export const EDGE_ID_PATTERN = /^E:[0-9a-f]{16}$/;
const EXTRACTOR_PATTERN = /^[a-z][a-z0-9_-]*:\S+$/;
const LLM_EXTRACTOR_PREFIX = "openai:";

export const curie = z.string().trim().regex(CURIE_PATTERN, "must be a CURIE (PREFIX:local)");
export const edgeId = z.string().trim().regex(EDGE_ID_PATTERN, 'must be "E:" + 16 lowercase hex');
const nonBlank = z.string().trim().min(1);
const strMap = z.record(nonBlank, z.string());

export const nodeTypeSchema = z.enum([
  "disease",
  "gene",
  "variant",
  "mechanism",
  "phenotype",
  "patient_group",
  "publication",
  "study",
  "asset",
  "investigator",
  "funder",
]);

export const relationSchema = z.enum([
  "caused_by",
  "risk_factor_for",
  "has_variant",
  "variant_associated_with",
  "has_mechanism",
  "participates_in",
  "has_phenotype",
  "shares_mechanism_with",
  "similar_phenotype_to",
  "mentions",
  "claims",
  "authored_by",
  "studies_condition",
  "tests_intervention",
  "investigates",
  "funds",
  "works_on",
  "represents",
  "operates",
  "contradicts",
]);

export const evidenceTypeSchema = z.enum(["observed", "curated", "inferred"]);
export const matchReasonSchema = z.enum(["exact", "synonym", "semantic"]);

export const nodeSchema = z.object({
  id: curie,
  type: nodeTypeSchema,
  label: nonBlank,
  synonyms: z.array(z.string()).default([]),
  xrefs: z.array(curie).default([]),
  attributes: strMap.default({}),
});

export const provenanceSchema = z.object({
  source: nonBlank,
  source_record_id: nonBlank,
  url: z
    .url({ protocol: /^https?$/ })
    .nullable()
    .default(null),
  retrieved_at: z.iso.datetime({ offset: true }),
  source_version: nonBlank.nullish(),
  evidence_quote: nonBlank.nullish(),
  extractor: z.string().regex(EXTRACTOR_PATTERN).nullish(),
  supporting_edge_ids: z.array(edgeId).default([]),
});

export const edgeSchema = z
  .object({
    id: edgeId,
    source_id: curie,
    target_id: curie,
    relation: relationSchema,
    provenance: provenanceSchema,
    confidence: z.number().min(0).max(1),
    confidence_reasons: z.array(nonBlank).default([]),
    evidence_type: evidenceTypeSchema,
    contradicted_by: z.array(nonBlank).default([]),
    qualifiers: strMap.default({}),
  })
  .superRefine((edge, ctx) => {
    // Same rules as backend Edge._evidence_is_checkable.
    const p = edge.provenance;
    if (p.url === null && edge.evidence_type !== "inferred") {
      ctx.addIssue({
        code: "custom",
        path: ["provenance", "url"],
        message: `${edge.evidence_type} edges must have provenance.url`,
      });
    }
    if (p.url === null && edge.evidence_type === "inferred" && p.supporting_edge_ids.length === 0) {
      ctx.addIssue({
        code: "custom",
        path: ["provenance", "supporting_edge_ids"],
        message: "inferred edges without provenance.url must list supporting_edge_ids",
      });
    }
    if (p.extractor?.startsWith(LLM_EXTRACTOR_PREFIX) && edge.evidence_type !== "inferred") {
      ctx.addIssue({
        code: "custom",
        path: ["evidence_type"],
        message: "LLM-extracted edges must have evidence_type 'inferred'",
      });
    }
    if (p.supporting_edge_ids.includes(edge.id)) {
      ctx.addIssue({ code: "custom", message: "an edge cannot list itself as supporting" });
    }
  });

export const searchResponseSchema = z.object({
  query: z.string(),
  results: z.array(
    z.object({
      node: nodeSchema,
      score: z.number(),
      match_reason: matchReasonSchema,
      matched_text: z.string(),
    }),
  ),
  searched: z.array(z.string()),
});

export const coverageReportSchema = z.object({
  query: curie,
  result: z.enum(["supported", "weak_routes_only", "no_supported_route"]),
  searched: z.array(
    z.object({
      source: z.string().min(1),
      source_version: z.string().optional(),
      query: z.string().optional(),
      records_found: z.number().int().min(0),
    }),
  ),
  not_searched: z.array(z.string()),
  missing_evidence: z.array(z.string()),
  weak_leads: z.array(
    z.object({
      path_edge_ids: z.array(edgeId),
      min_confidence: z.number().min(0).max(1),
      why_weak: z.string(),
    }),
  ),
  next_questions: z.array(z.string()),
});

export const nodeSummarySchema = z.object({
  node: nodeSchema,
  counts: z.object({
    edges: z.number().int().min(0),
    by_relation: z.record(z.string(), z.number().int().min(0)),
  }),
  edges: z.array(edgeSchema),
  neighbors: z.array(nodeSchema),
  cluster_id: z.string().nullable(),
  coverage_status: z.enum(["supported", "weak", "gap"]),
});

export const pathResponseSchema = z.object({
  from: curie,
  to: curie,
  paths: z.array(
    z.object({
      nodes: z.array(nodeSchema),
      edges: z.array(edgeSchema),
      cost: z.number().min(0),
      has_inferred: z.boolean(),
      has_contradiction: z.boolean(),
    }),
  ),
  coverage: coverageReportSchema.nullable(),
});

export const actionsResponseSchema = z.object({
  disease_id: curie,
  partners: z.array(z.object({ node: nodeSchema, why: z.string(), edge_ids: z.array(edgeId) })),
  assets: z.array(
    z.object({
      node: nodeSchema,
      reusable: z.string(),
      differs: z.string(),
      edge_ids: z.array(edgeId),
    }),
  ),
  next_experiment: z
    .object({ text: z.string(), is_hypothesis: z.boolean(), edge_ids: z.array(edgeId) })
    .nullable(),
  review_checklist: z.array(z.string()),
  coverage: coverageReportSchema.nullable(),
});

export const MAX_EXPLAIN_EDGES = 12;
export const explainAudienceSchema = z.enum(["family", "researcher"]);

export const explainRequestSchema = z.object({
  edge_ids: z.array(nonBlank).min(1).max(MAX_EXPLAIN_EDGES),
  audience: explainAudienceSchema,
});

export const explainStepSchema = z.object({
  text: nonBlank,
  edge_ids: z.array(nonBlank).min(1),
  is_hypothesis: z.boolean().default(false),
});

export const explainResponseSchema = z.object({
  steps: z.array(explainStepSchema),
  summary: z.string(),
  caveats: z.array(z.string()),
  source: z.enum(["cache", "live", "template"]),
  model: z.string().nullable(),
  prompt_version: z.string(),
  ai_generated: z.boolean(),
});

const unitScore = z.number().min(0).max(1);

export const clusterSummarySchema = z.object({
  id: nonBlank,
  label: nonBlank,
  size: z.number().int().min(1),
  member_ids: z.array(curie).min(1),
});

export const clustersResponseSchema = z.object({
  clusters: z.array(clusterSummarySchema),
  method: z.object({
    description: z.string(),
    weights: z.record(z.string(), z.number()),
    phenotype_ic_floor: z.number(),
    edge_threshold: z.number(),
    seed: z.number().int(),
  }),
});

const sharedFeatureSchema = z.object({
  node: nodeSchema,
  member_ids: z.array(curie),
  ic: z.number().nullable().default(null),
});

export const clusterDetailSchema = z.object({
  id: nonBlank,
  label: nonBlank,
  size: z.number().int().min(1),
  member_ids: z.array(curie).min(1),
  nodes: z.array(
    z.object({
      node: nodeSchema,
      cluster_id: nonBlank,
      is_member: z.boolean(),
      degree: z.number().int().min(0),
    }),
  ),
  features: z.object({
    genes: z.array(sharedFeatureSchema),
    mechanisms: z.array(sharedFeatureSchema),
    phenotypes: z.array(sharedFeatureSchema),
  }),
  edges: z.array(
    z.object({
      source_id: curie,
      target_id: curie,
      kind: z.enum(["within", "bridge"]),
      score: unitScore,
      phenotype_score: unitScore,
      gene_score: unitScore,
      mechanism_score: unitScore,
      reasons: z.array(z.string()),
    }),
  ),
  bridges: z.array(
    z.object({
      member_id: curie,
      other_id: curie,
      other_cluster_id: nonBlank,
      score: unitScore,
      reasons: z.array(z.string()),
    }),
  ),
  counterexamples: z.array(
    z.object({
      gene: nodeSchema,
      member_id: curie,
      other_id: curie,
      other_cluster_id: nonBlank,
      score: unitScore,
      note: z.string(),
    }),
  ),
});

// Compile-time guard: the schemas and the hand-written types must stay in sync.
type MutuallyAssignable<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
type Assert<T extends true> = T;
export type SchemaTypeChecks = [
  Assert<MutuallyAssignable<z.infer<typeof nodeSchema>, AtlasNode>>,
  Assert<MutuallyAssignable<z.infer<typeof edgeSchema>, Edge>>,
  Assert<MutuallyAssignable<z.infer<typeof searchResponseSchema>, SearchResponse>>,
  Assert<MutuallyAssignable<z.infer<typeof nodeSummarySchema>, NodeSummary>>,
  Assert<MutuallyAssignable<z.infer<typeof pathResponseSchema>, PathResponse>>,
  Assert<MutuallyAssignable<z.infer<typeof actionsResponseSchema>, ActionsResponse>>,
  Assert<MutuallyAssignable<z.infer<typeof coverageReportSchema>, CoverageReport>>,
  Assert<MutuallyAssignable<z.infer<typeof explainRequestSchema>, ExplainRequest>>,
  Assert<MutuallyAssignable<z.infer<typeof explainResponseSchema>, ExplainResponse>>,
  Assert<MutuallyAssignable<z.infer<typeof clustersResponseSchema>, ClustersResponse>>,
  Assert<MutuallyAssignable<z.infer<typeof clusterDetailSchema>, ClusterDetail>>,
];
