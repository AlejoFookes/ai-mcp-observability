import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { fetchTrace, fetchTraceList } from "../api/client";
import type { TraceSpan, TraceSummary } from "../api/types";
import { QueryStatus } from "../components/QueryStatus";
import { WindowFilters } from "../components/WindowFilters";
import { useQueryWindow } from "../hooks/useQueryWindow";
import { formatMs, formatOccurredAt, toLocalInputValue } from "../lib/window";

function kindLabel(kind: TraceSpan["kind"]): string {
  return kind === "genai" ? "model" : "tool";
}

function detailEntries(detail: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(detail)) {
    if (value === null || value === undefined) {
      continue;
    }
    if (
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      parts.push(`${key}=${String(value)}`);
    }
  }
  return parts.join(" · ");
}

export function TracesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("trace_id");
  const {
    fromInput,
    toInput,
    setFromInput,
    setToInput,
    window: queryWindow,
    windowError,
  } = useQueryWindow();
  const [draft, setDraft] = useState(selectedId ?? "");

  // Keep the visible "To" filter near wall-clock so new RAG/Playground events appear.
  useEffect(() => {
    const id = globalThis.setInterval(() => {
      setToInput(toLocalInputValue(new Date()));
    }, 30_000);
    return () => globalThis.clearInterval(id);
  }, [setToInput]);

  const listQuery = useQuery({
    queryKey: ["traces", queryWindow?.from, queryWindow?.to],
    queryFn: () => {
      if (queryWindow === null) {
        throw new Error("Window required");
      }
      return fetchTraceList(queryWindow, 50);
    },
    enabled: queryWindow !== null,
    refetchInterval: 5_000,
  });

  const rows = listQuery.data?.rows ?? [];

  useEffect(() => {
    if (selectedId !== null || rows.length === 0) {
      return;
    }
    const newest = rows[0];
    if (newest === undefined) {
      return;
    }
    setSearchParams({ trace_id: newest.trace_id }, { replace: true });
    setDraft(newest.trace_id);
  }, [rows, selectedId, setSearchParams]);

  const detailQuery = useQuery({
    queryKey: ["trace", selectedId],
    queryFn: () => {
      if (selectedId === null) {
        throw new Error("trace_id required");
      }
      return fetchTrace(selectedId);
    },
    enabled: selectedId !== null && selectedId.length > 0,
    retry: false,
  });

  function selectTrace(traceId: string) {
    setDraft(traceId);
    setSearchParams({ trace_id: traceId });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = draft.trim();
    if (next === "") {
      setSearchParams({});
      return;
    }
    selectTrace(next);
  }

  const spans = detailQuery.data?.spans ?? [];

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Traces</h2>
        <p className="mt-1 max-w-2xl text-[var(--muted)]">
          Lista automática de traces recientes (el primero es el más nuevo). Hacé click
          para abrir la timeline GenAI + MCP.
        </p>
      </div>

      <WindowFilters
        from={fromInput}
        to={toInput}
        onFromChange={setFromInput}
        onToChange={setToInput}
      />
      {windowError !== null ? (
        <p role="alert" className="text-sm text-red-800">
          {windowError}
        </p>
      ) : null}

      <form
        onSubmit={handleSubmit}
        className="flex flex-wrap items-end gap-3 border-b border-[var(--line)] pb-4"
      >
        <label className="flex min-w-[18rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">trace_id (manual)</span>
          <input
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="pega un id o elegí de la lista"
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

      <div className="grid gap-6 lg:grid-cols-[minmax(16rem,22rem)_1fr]">
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium uppercase tracking-wide text-[var(--muted)]">
            Recientes
          </h3>
          <QueryStatus
            isPending={listQuery.isPending}
            error={listQuery.error}
            isEmpty={rows.length === 0}
            emptyMessage="No traces in this window yet. Run the RAG chat or Playground."
          >
            <ul className="flex flex-col gap-2">
              {rows.map((row) => (
                <TraceListItem
                  key={row.trace_id}
                  row={row}
                  active={row.trace_id === selectedId}
                  onSelect={selectTrace}
                />
              ))}
            </ul>
          </QueryStatus>
        </section>

        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-medium uppercase tracking-wide text-[var(--muted)]">
            Timeline
          </h3>
          {selectedId === null ? (
            <p className="rounded border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 py-6 text-sm text-[var(--muted)]">
              Seleccioná un trace de la lista.
            </p>
          ) : (
            <QueryStatus
              isPending={detailQuery.isPending}
              error={detailQuery.error}
              isEmpty={spans.length === 0}
              emptyMessage="Trace returned no spans."
            >
              <div className="flex flex-col gap-3">
                <p className="text-sm text-[var(--muted)]">
                  <span className="font-medium text-[var(--ink)]">
                    {detailQuery.data?.trace_id}
                  </span>
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
                          span.kind === "genai"
                            ? "bg-[var(--accent)]"
                            : "bg-[#5c5c5c]",
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
                            {formatOccurredAt(span.occurred_at)} ·{" "}
                            {formatMs(span.latency_ms)}
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
        </section>
      </div>
    </div>
  );
}

function TraceListItem({
  row,
  active,
  onSelect,
}: {
  row: TraceSummary;
  active: boolean;
  onSelect: (traceId: string) => void;
}) {
  return (
    <li>
      <Link
        to={`/traces?trace_id=${encodeURIComponent(row.trace_id)}`}
        onClick={(event) => {
          event.preventDefault();
          onSelect(row.trace_id);
        }}
        className={[
          "block rounded border px-3 py-3 text-left text-sm",
          active
            ? "border-[var(--accent)] bg-[var(--accent)] text-white"
            : "border-[var(--line)] bg-[var(--panel)]",
        ].join(" ")}
      >
        <p className="font-mono text-xs break-all">{row.trace_id}</p>
        <p
          className={[
            "mt-1 text-xs",
            active ? "text-white/80" : "text-[var(--muted)]",
          ].join(" ")}
        >
          {formatOccurredAt(row.last_occurred_at)} · {row.span_count} span
          {row.span_count === 1 ? "" : "s"}
          {row.prompt_version !== null ? ` · ${row.prompt_version}` : ""}
        </p>
        {row.label !== null ? (
          <p className={["mt-1 truncate", active ? "" : "font-medium"].join(" ")}>
            {row.label}
          </p>
        ) : null}
      </Link>
    </li>
  );
}
