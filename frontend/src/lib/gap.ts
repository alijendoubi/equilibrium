/**
 * Closest existing communities for diseases with no dedicated patient organization.
 * Mirrors `no_dedicated_org_found[].closest_communities` in data/curated/organizations.yaml
 * (static on purpose: the gap card must work with the backend down).
 */
export interface Community {
  id: string;
  label: string;
  url: string;
  why: string;
}

const NATIONAL_GAUCHER_FOUNDATION: Community = {
  id: "org:national-gaucher-foundation",
  label: "National Gaucher Foundation",
  url: "https://www.gaucherdisease.org",
  why: "US patient organization for all types of Gaucher disease; the symptoms overlap.",
};

const INTERNATIONAL_GAUCHER_ALLIANCE: Community = {
  id: "org:international-gaucher-alliance",
  label: "International Gaucher Alliance",
  url: "https://www.gaucheralliance.org",
  why: "Umbrella of national Gaucher groups; the natural home for atypical Gaucher families.",
};

const CLOSEST_COMMUNITIES: Record<string, Community[]> = {
  "MONDO:0012517": [INTERNATIONAL_GAUCHER_ALLIANCE, NATIONAL_GAUCHER_FOUNDATION],
};

export function closestCommunities(diseaseId: string): Community[] {
  return CLOSEST_COMMUNITIES[diseaseId] ?? [];
}
