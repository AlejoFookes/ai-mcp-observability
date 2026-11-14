import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { fetchTrace } from "../api/client";
import type { TraceSpan } from "../api/types";
import { QueryStatus } from "../components/QueryStatus";
import { formatMs, formatOccurredAt } from "../lib/window";

function kindLabel(kind: TraceSpan["kind"]): string {
  return kind === "genai" ? "model" : "tool";
}

function detailEntries(detail: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(detail)) {
    if (value === null || value === undefined) {
      continue;
    }
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      parts.push(`${key}=${String(value)}`);
    }
  }
  return parts.join(" · ");
}

export function TracesPage() {
  const [draft, setDraft] = useState("");
  const [traceId, setTraceId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => {
      if (traceId === null) {
        throw new Error("trace_id required");
      }
      return fetchTrace(traceId);
    },
    enabled: traceId !== null && traceId.length > 0,
    retry: false,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = draft.trim();
    setTraceId(next === "" ? null : next);
  }

  const spans = query.data?.spans ?? [];

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Traces</h2>
        <p className="mt-1 max-w-2xl text-[var(--muted)]">
          Look up a trace_id and render the merged GenAI + MCP timeline ordered by
          occurred_at. A missing id surfaces the API 404.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex flex-wrap items-end gap-3 border-b border-[var(--line)] pb-4"
      >
        <label className="flex min-w-[18rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">trace_id</span>
          <input
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="e.g. trace-xyz"
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2 font-mono text-sm"
          />
        </label>
        <button
          type="submit"
          className="rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
        >
          Inspect
        </button>
      </form>

      {traceId === null ? (
        <p className="rounded border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 py-6 text-sm text-[var(--muted)]">
          Enter a trace_id to load the timeline.
        </p>
      ) : (
        <QueryStatus
          isPending={query.isPending}
          error={query.error}
          isEmpty={spans.length === 0}
          emptyMessage="Trace returned no spans."
        >
          <div className="flex flex-col gap-3">
            <p className="text-sm text-[var(--muted)]">
              <span className="font-medium text-[var(--ink)]">{query.data?.trace_id}</span>
              {" · "}
              {spans.length} span{spans.length === 1 ? "" : "s"}
            </p>
            <ol className="relative flex flex-col gap-0 border-l border-[var(--line)] pl-6">
              {spans.map((span) => (
                <li key={span.event_id} className="relative pb-6 last:pb-0">
                  <span
                    aria-hidden
                    className={[
                      "absolute -left-[1.55rem] top-1.5 h-3 w-3 rounded-full border-2 border-[var(--bg)]",
                      span.kind === "genai" ? "bg-[var(--accent)]" : "bg-[#5c5c5c]",
                    ].join(" ")}
                  />
                  <div className="rounded border border-[var(--line)] bg-[var(--panel)] px-4 py-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="font-medium">
                        <span className="mr-2 text-xs uppercase tracking-wide text-[var(--muted)]">
                          {kindLabel(span.kind)}
                        </span>
                        {span.label}
                      </p>
                      <p className="text-xs text-[var(--muted)]">
                        {formatOccurredAt(span.occurred_at)} · {formatMs(span.latency_ms)}
                      </p>
                    </div>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      status={span.status}
                      {detailEntries(span.detail) !== ""
                        ? ` · ${detailEntries(span.detail)}`
                        : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </QueryStatus>
      )}
    </div>
  );
}
