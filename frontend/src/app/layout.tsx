import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Equilibrium · Rare Disease Atlas",
  description:
    "An explainable knowledge graph of the world's rare diseases, built for patient-group leaders.",
};

// Next.js stamps its inline scripts with the per-request CSP nonce from src/middleware.ts, which
// only works for pages rendered per request; a prerendered page would ship scripts the CSP blocks.
export const dynamic = "force-dynamic";

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfbf9" },
    { media: "(prefers-color-scheme: dark)", color: "#0e1014" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-dvh bg-background text-foreground">{children}</body>
    </html>
  );
}
