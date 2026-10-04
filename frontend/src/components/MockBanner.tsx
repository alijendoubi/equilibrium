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
