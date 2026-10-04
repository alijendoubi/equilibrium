/** Shown on every data page while NEXT_PUBLIC_USE_MOCKS is on, so nobody mistakes mocks for the atlas. */
export function MockBanner({ isMock }: { isMock: boolean }) {
  if (!isMock) return null;
  return (
    <p
      role="note"
      className="rounded-xl border border-dashed border-evidence px-4 py-2 text-xs text-evidence"
    >
      <strong className="font-semibold">Mock data.</strong> This view uses example data that the
      real snapshot will replace. Ids, the trial and the publication are real; confidence scores are
      illustrative.
    </p>
  );
}

export const FALLBACK_NOTICE = "Showing cached demo data";

/** Shown when the live API failed and the page fell back to the bundled demo data. */
export function FallbackNotice({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <p
      role="status"
      className="rounded-xl border border-dashed border-muted px-4 py-2 text-xs text-muted"
    >
      <strong className="font-semibold">{FALLBACK_NOTICE}.</strong> The live atlas did not answer
      in time, so this view uses the demo data bundled with the app.
    </p>
  );
}

/** One slot for both notices: mock mode, or live mode that had to fall back. */
export function DataNotice({ isMock, usedFallback }: { isMock: boolean; usedFallback: boolean }) {
  if (!isMock && !usedFallback) return null;
  return (
    <div className="mt-6">
      {isMock ? <MockBanner isMock /> : <FallbackNotice show={usedFallback} />}
    </div>
  );
}
