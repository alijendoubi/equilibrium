import Link from "next/link";
import type { AtlasNode } from "@/lib/api/types";
import { NODE_TYPE_LABEL, NODE_TYPE_TONE, TONE_BORDER, TONE_TEXT, nodeHref } from "@/lib/format";

/** A node as a small linked chip: type label plus name. */
export function NodeChip({ node }: { node: AtlasNode }) {
  const tone = NODE_TYPE_TONE[node.type];
  return (
    <Link
      href={nodeHref(node.id)}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm hover:bg-background ${TONE_BORDER[tone]}`}
    >
      <span className={`text-xs font-medium ${TONE_TEXT[tone]}`}>{NODE_TYPE_LABEL[node.type]}</span>
      <span>{node.label}</span>
    </Link>
  );
}
