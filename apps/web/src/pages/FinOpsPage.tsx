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

function allUnpriced(rows: FinOpsRow[]): boolean {
  return (
    rows.length > 0 &&
    rows.every((row) => row.unpriced_count >= row.request_count) &&
    rows.every((row) => costNumber(row) === 0)
  );
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
  const unpricedOnly = metric === "cost" && allUnpriced(rows);
  const chartData =
    metric === "cost"
      ? rows.map((row) => ({
          key: row.key,
          input_tokens: row.input_tokens,
          output_tokens: row.output_tokens,
          requests: row.request_count,
        }))
      : rows.map((row) => ({
          key: row.key,
          requests: row.request_count,
        }));

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        <p className="text-sm text-[var(--muted)]">{summary}</p>
        {unpricedOnly ? (
          <p className="mt-1 text-sm text-[var(--muted)]">
            Modelos sin tarifa en el catálogo: el gráfico usa tokens y requests
            (est. cost queda en $0 / unpriced).
          </p>
        ) : null}
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
              <XAxis
                dataKey="key"
                tick={{ fontSize: 11 }}
                interval={0}
                angle={-20}
                textAnchor="end"
                height={48}
              />
              {metric === "cost" ? (
                <>
                  <YAxis
                    yAxisId="tokens"
                    tick={{ fontSize: 11 }}
                    width={56}
                    label={{
                      value: "tokens",
                      angle: -90,
                      position: "insideLeft",
                      style: { fontSize: 10, fill: "var(--muted)" },
                    }}
                  />
                  <YAxis
                    yAxisId="requests"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    width={40}
                    allowDecimals={false}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar
                    yAxisId="tokens"
                    dataKey="input_tokens"
                    fill="var(--accent)"
                    name="In tokens"
                  />
                  <Bar
                    yAxisId="tokens"
                    dataKey="output_tokens"
                    fill="#3d7a6c"
                    name="Out tokens"
                  />
                  <Bar
                    yAxisId="requests"
                    dataKey="requests"
                    fill="#8a6a3d"
                    name="Requests"
                  />
                </>
              ) : (
                <>
                  <YAxis tick={{ fontSize: 11 }} width={56} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey="requests"
                    fill="var(--accent)"
                    name="Requests"
                  />
                </>
              )}
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
                <tr
                  key={row.key}
                  className="border-b border-[var(--line)] last:border-0"
                >
                  <td className="px-3 py-2 font-medium">{row.key}</td>
                  <td className="px-3 py-2">{row.request_count}</td>
                  <td className="px-3 py-2">{row.error_count}</td>
                  {metric === "cost" ? (
                    <>
                      <td className="px-3 py-2">{row.input_tokens}</td>
                      <td className="px-3 py-2">{row.output_tokens}</td>
                      <td className="px-3 py-2">
                        {formatUsd(row.estimated_cost_usd)}
                      </td>
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
          Tokens and requests by model and prompt_version (cost when priced),
          plus MCP server volume. Judge spend stays out unless you opt in.
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
        summary="In/out tokens and requests grouped as provider/model. Est. cost when priced."
        groupBy="model"
        includeJudge={includeJudge}
        window={window}
        metric="cost"
      />
      <FinOpsSection
        title="By prompt_version"
        summary="Same measures rolled up by prompt_version — useful when cost is unpriced."
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
