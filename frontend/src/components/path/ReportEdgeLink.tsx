"use client";

import { useEffect, useState } from "react";
import type { Edge } from "@/lib/api/types";
import { edgeReportUrl } from "@/lib/report";

/** "Report a problem" for one edge: a prefilled GitHub issue form, no account needed here. */
export function ReportEdgeLink({ edge, labelOf }: { edge: Edge; labelOf: (id: string) => string }) {
  // The page URL is only known in the browser; render without it first to match the server.
  const [page, setPage] = useState<string | undefined>(undefined);
  useEffect(() => setPage(window.location.href), [edge.id]);

  return (
    <p className="mt-4 border-t border-border pt-3 text-xs text-muted">
      Something wrong with this link?{" "}
      <a
        href={edgeReportUrl(edge, labelOf, page)}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-cluster underline underline-offset-4"
      >
        Report a problem
        <span className="sr-only"> (opens GitHub in a new tab)</span>
      </a>
      . Do not include personal health information.
    </p>
  );
}
