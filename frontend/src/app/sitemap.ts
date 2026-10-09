import type { MetadataRoute } from "next";
import { getAtlasClient } from "@/lib/api/client";
import { nodeHref } from "@/lib/format";
import { absoluteUrl } from "@/lib/site";

const STATIC_ROUTES = ["/", "/map", "/clusters"] as const;

/** Static entry points, every cluster, and every disease that belongs to one. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const { clusters } = await getAtlasClient().getClusters();
  const diseaseIds = [...new Set(clusters.flatMap((cluster) => cluster.member_ids))].sort();
  return [
    ...STATIC_ROUTES.map((path) => ({
      url: absoluteUrl(path),
      changeFrequency: "weekly" as const,
      priority: path === "/" ? 1 : 0.8,
    })),
    ...clusters.map((cluster) => ({
      url: absoluteUrl(`/clusters/${encodeURIComponent(cluster.id)}`),
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
    ...diseaseIds.map((id) => ({
      url: absoluteUrl(nodeHref(id)),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}
