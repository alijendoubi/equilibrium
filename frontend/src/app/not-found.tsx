import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-2xl font-semibold">Not in the atlas</h1>
      <p className="mt-2 text-muted">
        We could not find that page or node. It may not be in the current snapshot.
      </p>
      <Link href="/" className="mt-6 inline-block text-cluster underline-offset-4 hover:underline">
        Back to search
      </Link>
    </main>
  );
}
