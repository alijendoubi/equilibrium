import { OG_CONTENT_TYPE, OG_SIZE, ogCard } from "@/lib/og/card";

export const alt = "Equilibrium, an evidence-first rare disease atlas";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default function Image() {
  return ogCard({
    eyebrow: "Rare disease atlas",
    title: "Make the connections that isolated evidence keeps hidden.",
    detail: "Sourced links · visible contradictions · honest gaps",
  });
}
