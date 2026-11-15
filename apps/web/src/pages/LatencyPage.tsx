import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchLatency } from "../api/client";
import type { LatencyGroupBy } from "../api/types";
import { QueryStatus } from "../components/QueryStatus";
import { WindowFilters } from "../components/WindowFilters";
import { useQueryWindow } from "../hooks/useQueryWindow";
import { formatMs, formatPercent } from "../lib/window";

const GROUP_OPTIONS: ReadonlyArray<{ value: LatencyGroupBy; label: string }> = [
  { value: "model", label: "Model" },
  { value: "operation", label: "Operation" },
  { value: "mcp_tool", label: "MCP tool" },
];

export function LatencyPage() {
  const { fromInput, toInput, setFromInput, setToInput, window, windowError } =
    useQueryWindow();
  const [groupBy, setGroupBy] = useState<LatencyGroupBy>("model");

  const query = useQuery({
    queryKey: ["latency", groupBy, window?.from, window?.to],
    queryFn: () => {
      if (window === null) {
        throw new Error("Window required");
      }
      return fetchLatency(window, groupBy);
    },
    enabled: window !== null,
  });

  const rows = query.data?.rows ?? [];
  const chartData = rows.map((row) => ({
    key: row.key,
    p50_ms: row.p50_ms,
    p95_ms: row.p95_ms,
  }));

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Latency</h2>
        <p className="mt-1 max-w-2xl text-[var(--muted)]">
          Latencia típica (mediana / p50), cola lenta (95% ≤ X ms / p95) and
          error_rate by model, operation or MCP tool. Percentiles include
          failed calls.
        </p>
      </div>

      <WindowFilters
        from={fromInput}
        to={toInput}
        onFromChange={setFromInput}
        onToChange={setToInput}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Group by</span>
          <select
            value={groupBy}
            onChange={(event) => {
              const next = event.target.value;
              if (
                next === "model" ||
                next === "operation" ||
                next === "mcp_tool"
              ) {
                setGroupBy(next);
              }
            }}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
          >
            {GROUP_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </WindowFilters>

      {windowError !== null ? (
        <p role="alert" className="text-sm text-red-800">
          {windowError}
        </p>
      ) : null}

      <QueryStatus
        isPending={query.isPending}
        error={query.error}
        isEmpty={rows.length === 0}
        emptyMessage="No latency samples in this window for this grouping."
      >
        <div className="h-64 rounded border border-[var(--line)] bg-[var(--panel)] p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
              <XAxis
                dataKey="key"
                tick={{ fontSize: 11 }}
                interval={0}
                angle={-20}
                textAnchor="end"
                height={48}
              />
              <YAxis unit="ms" tick={{ fontSize: 11 }} width={56} />
              <Tooltip formatter={(value) => formatMs(Number(value ?? 0))} />
              <Legend />
              <Bar
                dataKey="p50_ms"
                fill="var(--accent)"
                name="Latencia típica (mediana)"
              />
              <Bar
                dataKey="p95_ms"
                fill="#3d7a6c"
                name="Cola lenta (95% ≤ X ms)"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="overflow-x-auto rounded border border-[var(--line)] bg-[var(--panel)]">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--line)] text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2 font-medium">Key</th>
                <th className="px-3 py-2 font-medium">Count</th>
                <th
                  className="px-3 py-2 font-medium"
                  title="p50 — mitad de las requests ≤ este valor"
                >
                  Latencia típica (mediana)
                </th>
                <th
                  className="px-3 py-2 font-medium"
                  title="p95 — 95% de las requests ≤ este valor"
                >
                  Cola lenta (95% ≤ X ms)
                </th>
                <th className="px-3 py-2 font-medium">Error rate</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.key}
                  className="border-b border-[var(--line)] last:border-0"
                >
                  <td className="px-3 py-2 font-medium">{row.key}</td>
                  <td className="px-3 py-2">{row.count}</td>
                  <td className="px-3 py-2">{formatMs(row.p50_ms)}</td>
                  <td className="px-3 py-2">{formatMs(row.p95_ms)}</td>
                  <td className="px-3 py-2">{formatPercent(row.error_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </QueryStatus>
    </div>
  );
}
