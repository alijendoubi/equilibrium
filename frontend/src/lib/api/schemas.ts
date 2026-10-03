import { z } from "zod";
import type {
  ActionsResponse,
  AtlasNode,
  CoverageReport,
  Edge,
  NodeSummary,
  PathResponse,
  SearchResponse,
} from "./types";

/** Runtime validators for the wire types in ./types.ts. */

const CURIE = /^[A-Za-z][A-Za-z0-9_.-]*:\S+$/;
const STUDY_ID = /^NCT\d{8}$/;
const nodeId = z.string().refine((v) => CURIE.test(v) || STUDY_ID.test(v), {
  message: "must be a CURIE (PREFIX:local) or an NCT id",
});

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

export const evidenceTypeSchema = z.enum(["observed", "curated", "inferred"]);
export const matchReasonSchema = z.enum(["exact", "synonym", "semantic"]);

export const nodeSchema = z.object({
  id: nodeId,
  type: nodeTypeSchema,
  label: z.string().min(1),
  synonyms: z.array(z.string().min(1)),
  description: z.string().optional(),
  xrefs: z.array(z.string().min(1)).optional(),
  attributes: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])).optional(),
});

export const provenanceSchema = z
  .object({
    source: z.string().min(1),
    source_record_id: z.string().min(1),
    url: z.url({ protocol: /^https?$/ }).nullable(),
    retrieved_at: z.iso.datetime(),
    evidence_quote: z.string().min(1).optional(),
    supporting_edge_ids: z.array(z.string().min(1)).optional(),
  })
  .refine((p) => p.url !== null || p.source === "analytics", {
    message: "url is required unless source is analytics",
    path: ["url"],
  });

export const edgeSchema = z.object({
  id: z.string().regex(/^e_[a-z0-9_]+$/),
  source_id: nodeId,
  target_id: nodeId,
  relation: z.string().min(1),
  provenance: provenanceSchema,
  confidence: z.number().min(0).max(1),
  confidence_reasons: z.array(z.string().min(1)),
  evidence_type: evidenceTypeSchema,
  contradicted_by: z.array(z.string().min(1)),
  qualifiers: z.record(z.string(), z.string()).optional(),
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
  query: z.string(),
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
      path_edge_ids: z.array(z.string()),
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
  from: z.string(),
  to: z.string(),
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
  disease_id: z.string(),
  partners: z.array(z.object({ node: nodeSchema, why: z.string(), edge_ids: z.array(z.string()) })),
  assets: z.array(
    z.object({
      node: nodeSchema,
      reusable: z.string(),
      differs: z.string(),
      edge_ids: z.array(z.string()),
    }),
  ),
  next_experiment: z
    .object({ text: z.string(), is_hypothesis: z.boolean(), edge_ids: z.array(z.string()) })
    .nullable(),
  review_checklist: z.array(z.string()),
  coverage: coverageReportSchema.nullable(),
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
];
