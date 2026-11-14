import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchFinOpsSummary } from "../api/client";
import type { FinOpsGroupBy, FinOpsRow } from "../api/types";
import { QueryStatus } from "../components/QueryStatus";
import { WindowFilters } from "../components/WindowFilters";
import { useQueryWindow } from "../hooks/useQueryWindow";
import { formatUsd } from "../lib/window";

function costNumber(row: FinOpsRow): number {
  const n = Number(row.estimated_cost_usd);
  return Number.isNaN(n) ? 0 : n;
}

function FinOpsSection({
  title,
  summary,
  groupBy,
  includeJudge,
  window,
  metric,
}: {
  title: string;
  summary: string;
  groupBy: FinOpsGroupBy;
  includeJudge: boolean;
  window: { from: string; to: string } | null;
  metric: "cost" | "volume";
}) {
  const query = useQuery({
    queryKey: ["finops", groupBy, includeJudge, window?.from, window?.to],
    queryFn: () => {
      if (window === null) {
        throw new Error("Window required");
      }
      return fetchFinOpsSummary(window, groupBy, includeJudge);
    },
    enabled: window !== null,
  });

  const rows = query.data?.rows ?? [];
  const chartData = rows.map((row) => ({
    key: row.key,
    value: metric === "cost" ? costNumber(row) : row.request_count,
  }));

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        <p className="text-sm text-[var(--muted)]">{summary}</p>
      </div>
      <QueryStatus
        isPending={query.isPending}
        error={query.error}
        isEmpty={rows.length === 0}
        emptyMessage="No events in this window for this grouping."
      >
        <div className="h-56 rounded border border-[var(--line)] bg-[var(--panel)] p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
              <XAxis dataKey="key" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={48} />
              <YAxis tick={{ fontSize: 11 }} width={56} />
              <Tooltip
                formatter={(value) =>
                  metric === "cost"
                    ? formatUsd(String(value ?? 0))
                    : String(value ?? 0)
                }
              />
              <Bar dataKey="value" fill="var(--accent)" name={metric === "cost" ? "USD" : "requests"} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="overflow-x-auto rounded border border-[var(--line)] bg-[var(--panel)]">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--line)] text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2 font-medium">Key</th>
                <th className="px-3 py-2 font-medium">Requests</th>
                <th className="px-3 py-2 font-medium">Errors</th>
                {metric === "cost" ? (
                  <>
                    <th className="px-3 py-2 font-medium">In tokens</th>
                    <th className="px-3 py-2 font-medium">Out tokens</th>
                    <th className="px-3 py-2 font-medium">Est. cost</th>
                    <th className="px-3 py-2 font-medium">Unpriced</th>
                  </>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-b border-[var(--line)] last:border-0">
                  <td className="px-3 py-2 font-medium">{row.key}</td>
                  <td className="px-3 py-2">{row.request_count}</td>
                  <td className="px-3 py-2">{row.error_count}</td>
                  {metric === "cost" ? (
                    <>
                      <td className="px-3 py-2">{row.input_tokens}</td>
                      <td className="px-3 py-2">{row.output_tokens}</td>
                      <td className="px-3 py-2">{formatUsd(row.estimated_cost_usd)}</td>
                      <td className="px-3 py-2">{row.unpriced_count}</td>
                    </>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </QueryStatus>
    </section>
  );
}

export function FinOpsPage() {
  const { fromInput, toInput, setFromInput, setToInput, window, windowError } =
    useQueryWindow();
  const [includeJudge, setIncludeJudge] = useState(false);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">FinOps</h2>
        <p className="mt-1 max-w-2xl text-[var(--muted)]">
          Spend by model and prompt_version, plus MCP server volume. Judge spend
          stays out unless you opt in.
        </p>
      </div>

      <WindowFilters
        from={fromInput}
        to={toInput}
        onFromChange={setFromInput}
        onToChange={setToInput}
      >
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={includeJudge}
            onChange={(event) => setIncludeJudge(event.target.checked)}
          />
          <span>Include judge spend</span>
        </label>
      </WindowFilters>

      {windowError !== null ? (
        <p role="alert" className="text-sm text-red-800">
          {windowError}
        </p>
      ) : null}

      <FinOpsSection
        title="By model"
        summary="Estimated USD and tokens grouped as provider/model."
        groupBy="model"
        includeJudge={includeJudge}
        window={window}
        metric="cost"
      />
      <FinOpsSection
        title="By prompt_version"
        summary="Same FinOps measures rolled up by prompt_version metadata."
        groupBy="prompt_version"
        includeJudge={includeJudge}
        window={window}
        metric="cost"
      />
      <FinOpsSection
        title="MCP server volume"
        summary="Tool call volume from mcp_events. Token and cost fields stay at zero."
        groupBy="mcp_server"
        includeJudge={includeJudge}
        window={window}
        metric="volume"
      />
    </div>
  );
}
