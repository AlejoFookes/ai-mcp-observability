import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PlaceholderPage } from "./PlaceholderPage";

const sample = [
  { label: "p50", ms: 0 },
  { label: "p95", ms: 0 },
] as const;

export function LatencyPage() {
  return (
    <div className="flex flex-col gap-6">
      <PlaceholderPage
        title="Latency"
        summary="p50, p95 and error_rate by model, operation and MCP tool."
      />
      <div className="h-48 rounded border border-[var(--line)] bg-[var(--panel)] p-4">
        <p className="mb-2 text-xs uppercase tracking-wide text-[var(--muted)]">
          Recharts ready
        </p>
        <ResponsiveContainer width="100%" height="85%">
          <LineChart data={[...sample]}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis unit="ms" />
            <Tooltip />
            <Line type="monotone" dataKey="ms" stroke="var(--accent)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
