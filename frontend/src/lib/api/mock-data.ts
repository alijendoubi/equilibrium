import { z } from "zod";
import actionsJson from "@/mocks/actions.json";
import coverageJson from "@/mocks/coverage.json";
import edgesJson from "@/mocks/edges.json";
import nodesJson from "@/mocks/nodes.json";
import pathsJson from "@/mocks/paths.json";
import { coverageReportSchema, curie, edgeId, edgeSchema, nodeSchema } from "./schemas";

/** Mock store: the raw JSON in src/mocks, validated and checked for broken references. */

const storedPathSchema = z.object({
  id: z.string().min(1),
  node_ids: z.array(curie).min(2),
  edge_ids: z.array(edgeId).min(1),
});

const storedActionsSchema = z.object({
  disease_id: curie,
  partners: z.array(
    z.object({ node_id: curie, why: z.string().min(1), edge_ids: z.array(edgeId) }),
  ),
  assets: z.array(
    z.object({
      node_id: curie,
      reusable: z.string().min(1),
      differs: z.string().min(1),
      edge_ids: z.array(edgeId),
    }),
  ),
  next_experiment: z
    .object({ text: z.string().min(1), is_hypothesis: z.boolean(), edge_ids: z.array(edgeId) })
    .nullable(),
  review_checklist: z.array(z.string()),
});

export const mockDatasetSchema = z
  .object({
    nodes: z.array(nodeSchema),
    edges: z.array(edgeSchema),
    paths: z.array(storedPathSchema),
    actions: z.array(storedActionsSchema),
    coverage: z.array(coverageReportSchema),
  })
  .superRefine((data, ctx) => {
    const nodeIds = new Set(data.nodes.map((n) => n.id));
    const edgeById = new Map(data.edges.map((e) => [e.id, e]));
    const issue = (message: string) => ctx.addIssue({ code: "custom", message });

    if (nodeIds.size !== data.nodes.length) issue("duplicate node ids");
    if (edgeById.size !== data.edges.length) issue("duplicate edge ids");

    const checkNode = (id: string, where: string) => {
      if (!nodeIds.has(id)) issue(`${where}: unknown node ${id}`);
    };
    const checkEdge = (id: string, where: string) => {
      if (!edgeById.has(id)) issue(`${where}: unknown edge ${id}`);
    };

    for (const e of data.edges) {
      checkNode(e.source_id, `edge ${e.id} source`);
      checkNode(e.target_id, `edge ${e.id} target`);
      e.contradicted_by.forEach((id) => checkEdge(id, `edge ${e.id} contradicted_by`));
      e.provenance.supporting_edge_ids?.forEach((id) => checkEdge(id, `edge ${e.id} supporting`));
    }

    for (const p of data.paths) {
      if (p.edge_ids.length !== p.node_ids.length - 1) {
        issue(`path ${p.id}: needs exactly one edge between each pair of nodes`);
        continue;
      }
      p.node_ids.forEach((id) => checkNode(id, `path ${p.id}`));
      p.edge_ids.forEach((id, i) => {
        const edge = edgeById.get(id);
        if (!edge) return checkEdge(id, `path ${p.id}`);
        const pair = [p.node_ids[i], p.node_ids[i + 1]];
        if (!pair.includes(edge.source_id) || !pair.includes(edge.target_id)) {
          issue(`path ${p.id}: edge ${id} does not join ${pair.join(" and ")}`);
        }
      });
    }

    for (const a of data.actions) {
      checkNode(a.disease_id, "actions");
      for (const item of [...a.partners, ...a.assets]) {
        checkNode(item.node_id, `actions ${a.disease_id}`);
        item.edge_ids.forEach((id) => checkEdge(id, `actions ${a.disease_id}`));
      }
      a.next_experiment?.edge_ids.forEach((id) => checkEdge(id, `actions ${a.disease_id}`));
    }

    for (const c of data.coverage) {
      checkNode(c.query, "coverage");
      c.weak_leads.forEach((l) => l.path_edge_ids.forEach((id) => checkEdge(id, "coverage")));
    }
  });

export type MockDataset = z.infer<typeof mockDatasetSchema>;

export const RAW_MOCK_DATA: unknown = {
  nodes: nodesJson,
  edges: edgesJson,
  paths: pathsJson,
  actions: actionsJson,
  coverage: coverageJson,
};

/** Parses the mock JSON. Throws one readable error listing every problem. */
export function parseMockDataset(raw: unknown): MockDataset {
  const parsed = mockDatasetSchema.safeParse(raw);
  if (!parsed.success) {
    const details = parsed.error.issues
      .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
      .join("; ");
    throw new Error(`Invalid mock data: ${details}`);
  }
  return parsed.data;
}

let cached: MockDataset | null = null;

export function loadMockDataset(): MockDataset {
  cached ??= parseMockDataset(RAW_MOCK_DATA);
  return cached;
}
