import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchCompare } from "../api/client";
import type { CompareDimension, CompareSide } from "../api/types";
import { QueryStatus } from "../components/QueryStatus";
import { WindowFilters } from "../components/WindowFilters";
import { useQueryWindow } from "../hooks/useQueryWindow";
import { formatMs, formatPercent, formatUsd } from "../lib/window";

const DIMENSIONS: ReadonlyArray<{ value: CompareDimension; label: string }> = [
  { value: "prompt_version", label: "prompt_version" },
  { value: "model", label: "model (provider/model)" },
];

function SideCard({ title, side }: { title: string; side: CompareSide }) {
  return (
    <article className="flex flex-1 flex-col gap-3 rounded border border-[var(--line)] bg-[var(--panel)] p-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{title}</p>
        <h3 className="mt-1 break-all text-lg font-semibold">{side.key}</h3>
        <p className="mt-2 text-sm">
          <span className="text-2xl font-semibold tabular-nums">{side.request_count}</span>
          <span className="ml-2 text-[var(--muted)]">samples</span>
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-[var(--muted)]">Errors</dt>
        <dd className="tabular-nums">{side.error_count}</dd>
        <dt className="text-[var(--muted)]">Input tokens</dt>
        <dd className="tabular-nums">{side.input_tokens}</dd>
        <dt className="text-[var(--muted)]">Output tokens</dt>
        <dd className="tabular-nums">{side.output_tokens}</dd>
        <dt className="text-[var(--muted)]">Est. cost</dt>
        <dd className="tabular-nums">{formatUsd(side.estimated_cost_usd)}</dd>
        <dt className="text-[var(--muted)]">Unpriced</dt>
        <dd className="tabular-nums">{side.unpriced_count}</dd>
        <dt
          className="text-[var(--muted)]"
          title="p50 — mitad de las requests ≤ este valor"
        >
          Latencia típica (mediana)
        </dt>
        <dd className="tabular-nums">
          {side.p50_ms === null ? "—" : formatMs(side.p50_ms)}
        </dd>
        <dt
          className="text-[var(--muted)]"
          title="p95 — 95% de las requests ≤ este valor"
        >
          Cola lenta (95% ≤ X ms)
        </dt>
        <dd className="tabular-nums">
          {side.p95_ms === null ? "—" : formatMs(side.p95_ms)}
        </dd>
        <dt className="text-[var(--muted)]">Error rate</dt>
        <dd className="tabular-nums">{formatPercent(side.error_rate)}</dd>
      </dl>
    </article>
  );
}

export function ComparePage() {
  const { fromInput, toInput, setFromInput, setToInput, window, windowError } =
    useQueryWindow();
  const [dimension, setDimension] = useState<CompareDimension>("prompt_version");
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [submitted, setSubmitted] = useState<{
    dimension: CompareDimension;
    left: string;
    right: string;
  } | null>(null);

  const canQuery =
    window !== null &&
    submitted !== null &&
    submitted.left.length > 0 &&
    submitted.right.length > 0;

  const query = useQuery({
    queryKey: [
      "compare",
      submitted?.dimension,
      submitted?.left,
      submitted?.right,
      window?.from,
      window?.to,
    ],
    queryFn: () => {
      if (window === null || submitted === null) {
        throw new Error("Compare params required");
      }
      return fetchCompare(window, submitted.dimension, submitted.left, submitted.right);
    },
    enabled: canQuery,
  });

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Compare</h2>
        <p className="mt-1 max-w-2xl text-[var(--muted)]">
          Side-by-side FinOps and latency snapshots for two prompt_version or model
          keys. Sample counts stay visible so a tiny window is not mistaken for a
          conclusion.
        </p>
      </div>

      <WindowFilters
        from={fromInput}
        to={toInput}
        onFromChange={setFromInput}
        onToChange={setToInput}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Dimension</span>
          <select
            value={dimension}
            onChange={(event) => {
              const next = event.target.value;
              if (next === "prompt_version" || next === "model") {
                setDimension(next);
              }
            }}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
          >
            {DIMENSIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-[10rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Left</span>
          <input
            type="text"
            value={left}
            onChange={(event) => setLeft(event.target.value)}
            placeholder={dimension === "model" ? "openai/gpt-5.5" : "v1"}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
          />
        </label>
        <label className="flex min-w-[10rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Right</span>
          <input
            type="text"
            value={right}
            onChange={(event) => setRight(event.target.value)}
            placeholder={dimension === "model" ? "anthropic/claude-sonnet-4" : "v2"}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
          />
        </label>
        <button
          type="button"
          className="rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
          onClick={() => {
            const nextLeft = left.trim();
            const nextRight = right.trim();
            if (nextLeft === "" || nextRight === "") {
              setSubmitted(null);
              return;
            }
            setSubmitted({
              dimension,
              left: nextLeft,
              right: nextRight,
            });
          }}
        >
          Compare
        </button>
      </WindowFilters>

      {windowError !== null ? (
        <p role="alert" className="text-sm text-red-800">
          {windowError}
        </p>
      ) : null}

      {submitted === null ? (
        <p className="rounded border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 py-6 text-sm text-[var(--muted)]">
          Choose a dimension, enter both keys, and run Compare.
        </p>
      ) : (
        <QueryStatus
          isPending={query.isPending}
          error={query.error}
          isEmpty={query.data === undefined}
          emptyMessage="No comparison result."
        >
          {query.data !== undefined ? (
            <div className="flex flex-col gap-4 lg:flex-row">
              <SideCard title="Left" side={query.data.left} />
              <SideCard title="Right" side={query.data.right} />
            </div>
          ) : null}
        </QueryStatus>
      )}
    </div>
  );
}
