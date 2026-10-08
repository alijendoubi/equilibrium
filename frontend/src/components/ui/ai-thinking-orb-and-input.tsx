"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { TraceResultView } from "@/components/home/TraceResultView";
import { EXAMPLE_QUERIES, SEARCH_PLACEHOLDER } from "@/components/GlobalSearch";
import type { SearchResult } from "@/lib/api/types";
import { traceNode, traceQuery } from "@/lib/trace";
import {
  MAX_TRACE_QUERY_LENGTH,
  normalizeQuery,
  type GraphResult,
  type TraceResult,
} from "@/lib/trace-result";
import { ThinkingOrb } from "./thinking-orb";

type Phase = "idle" | "thinking" | "result";
type Shown = Exclude<TraceResult, { status: "invalid" }>;

const STEPS = ["Searching the atlas", "Picking the best match", "Loading sourced links"] as const;
const STEP_MS = 700;
const UNREACHABLE = "The atlas could not be reached. Try again.";

export interface AiThinkingOrbAndInputProps {
  /** Injected in tests; defaults to the server actions. */
  trace?: (query: string) => Promise<TraceResult>;
  pick?: (id: string) => Promise<GraphResult>;
  /** Keeps the orb on screen long enough to read, even when the answer is instant. */
  minThinkMs?: number;
}

/**
 * Home hero: type a disease, gene or symptom, watch the orb while the atlas is searched, then see
 * the best match's real depth-1 evidence map. Without JavaScript the form falls back to /search.
 */
export function AiThinkingOrbAndInput({
  trace = traceQuery,
  pick = traceNode,
  minThinkMs = 900,
}: AiThinkingOrbAndInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef(0);
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Shown | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => {
    if (phase !== "thinking") return;
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), STEP_MS);
    return () => window.clearInterval(id);
  }, [phase]);

  async function run(raw: string) {
    const query = normalizeQuery(raw);
    if (!query) {
      setError("Type a disease, gene or symptom first.");
      inputRef.current?.focus();
      return;
    }
    const request = ++requestRef.current;
    setText(query);
    setError(null);
    setStep(0);
    setPhase("thinking");
    const started = performance.now();
    let next: TraceResult;
    try {
      next = await trace(query);
    } catch {
      next = { status: "error", query, message: UNREACHABLE };
    }
    const wait = minThinkMs - (performance.now() - started);
    if (wait > 0) await new Promise((resolve) => window.setTimeout(resolve, wait));
    if (request !== requestRef.current) return;
    if (next.status === "invalid") {
      setError(next.message);
      setPhase("idle");
      return;
    }
    setResult(next);
    setPhase("result");
  }

  async function choose(alternative: SearchResult) {
    if (result?.status !== "found" || pendingId) return;
    const current = result;
    const request = requestRef.current;
    setPendingId(alternative.node.id);
    let next: GraphResult;
    try {
      next = await pick(alternative.node.id);
    } catch {
      next = { status: "error", message: UNREACHABLE };
    }
    if (request !== requestRef.current) return;
    setPendingId(null);
    if (next.status === "error") {
      setResult({ status: "error", query: current.query, message: next.message });
      return;
    }
    setResult({
      ...current,
      match: alternative,
      alternatives: [
        current.match,
        ...current.alternatives.filter((a) => a.node.id !== alternative.node.id),
      ],
      graph: next.graph,
      isMock: next.isMock,
      usedFallback: next.usedFallback,
    });
  }

  function reset() {
    requestRef.current++;
    setPhase("idle");
    setResult(null);
    setPendingId(null);
    setText("");
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(text);
  }

  return (
    <section
      aria-label="Trace a disease"
      className="relative isolate flex min-h-[100dvh] items-center justify-center overflow-hidden px-4 py-10 sm:px-6"
    >
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_50%_42%,color-mix(in_oklab,var(--cluster)_12%,transparent),transparent_32%),radial-gradient(circle_at_86%_18%,color-mix(in_oklab,var(--evidence)_10%,transparent),transparent_22%)]"
      />
      <div className={`w-full text-center ${phase === "result" ? "max-w-6xl" : "max-w-2xl"}`}>
        <h1 className="text-xs font-semibold tracking-[0.18em] text-cluster uppercase">
          Equilibrium · Rare Disease Atlas
        </h1>

        {phase === "idle" && (
          <>
            <p className="mx-auto mt-5 max-w-xl text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-6xl">
              Where should your disease connect next?
            </p>
            <p className="mx-auto mt-5 max-w-lg text-base leading-relaxed text-muted sm:text-lg">
              Start with a disease, gene or symptom. We trace the sourced evidence, shared biology
              and the work that could matter to you.
            </p>
            <form
              role="search"
              action="/search"
              method="get"
              onSubmit={onSubmit}
              className="mx-auto mt-10 flex max-w-xl gap-2 rounded-full border border-border bg-surface p-2 shadow-[0_18px_55px_color-mix(in_oklab,var(--cluster)_12%,transparent)] focus-within:border-cluster"
            >
              <label htmlFor="global-search" className="sr-only">
                Search the atlas
              </label>
              <input
                ref={inputRef}
                id="global-search"
                name="q"
                type="search"
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder={SEARCH_PLACEHOLDER}
                aria-describedby="trace-hint"
                aria-invalid={error ? true : undefined}
                autoComplete="off"
                maxLength={MAX_TRACE_QUERY_LENGTH}
                className="min-w-0 flex-1 bg-transparent px-4 py-3 text-base outline-none placeholder:text-muted"
              />
              <button
                type="submit"
                className="shrink-0 rounded-full bg-cluster px-5 py-3 text-sm font-semibold text-background transition-transform hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus active:scale-[0.98]"
              >
                Trace it
              </button>
            </form>
            <p
              id="trace-hint"
              aria-live="polite"
              className={`mt-3 text-sm ${error ? "text-contradiction" : "text-muted"}`}
            >
              {error ?? "Diseases, genes, symptoms, patient groups and mechanisms."}
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <span className="text-sm text-muted">Try:</span>
              {EXAMPLE_QUERIES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => void run(example)}
                  className="rounded-full border border-border px-3 py-1 text-sm hover:border-cluster"
                >
                  {example}
                </button>
              ))}
            </div>
          </>
        )}

        {phase === "thinking" && (
          <div className="mt-7 flex flex-col items-center" role="status" aria-live="polite">
            <ThinkingOrb label={STEPS[step] ?? STEPS[0]} />
            <p className="mt-3 text-sm font-medium text-cluster">{STEPS[step]}</p>
            <p className="mt-2 text-2xl font-semibold break-words">Tracing {text}</p>
          </div>
        )}

        {phase === "result" && result && (
          <TraceResultView
            result={result}
            pendingId={pendingId}
            onPick={(alt) => void choose(alt)}
            onRetry={() => void run(result.query)}
            onReset={reset}
          />
        )}
      </div>
    </section>
  );
}
