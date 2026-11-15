/** Hand-typed contracts mirroring SPEC §6.3. No OpenAPI codegen in 0.1. */

export type SchemaVersion = "1.0";

export type ApiErrorCode =
  | "unauthorized"
  | "validation_error"
  | "not_found"
  | "payload_too_large"
  | "storage_unavailable"
  | "internal_error";

export interface ApiErrorBody {
  schema_version: SchemaVersion;
  error: {
    code: ApiErrorCode;
    message: string;
    details: unknown[];
  };
}

export interface HealthResponse {
  schema_version: SchemaVersion;
  status: "ok" | "degraded";
  storage_backend: "postgres" | "bigquery" | "memory";
}

export type FinOpsGroupBy =
  | "model"
  | "provider"
  | "prompt_version"
  | "mcp_server";

export interface FinOpsRow {
  key: string;
  request_count: number;
  error_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: string;
  unpriced_count: number;
}

export interface FinOpsSummaryResponse {
  schema_version: SchemaVersion;
  currency: "USD";
  rows: FinOpsRow[];
}

export type LatencyGroupBy = "model" | "operation" | "mcp_tool";

export interface LatencyRow {
  key: string;
  count: number;
  p50_ms: number;
  p95_ms: number;
  error_rate: number;
}

export interface LatencyResponse {
  schema_version: SchemaVersion;
  rows: LatencyRow[];
}

export interface WindowParams {
  from: string;
  to: string;
}

export interface TraceSpan {
  kind: "genai" | "mcp";
  event_id: string;
  occurred_at: string;
  trace_id: string;
  status: string;
  latency_ms: number;
  label: string;
  detail: Record<string, unknown>;
}

export interface TraceResponse {
  schema_version: SchemaVersion;
  trace_id: string;
  spans: TraceSpan[];
}

export interface TraceSummary {
  trace_id: string;
  last_occurred_at: string;
  span_count: number;
  label: string | null;
  prompt_version: string | null;
}

export interface TraceListResponse {
  schema_version: SchemaVersion;
  rows: TraceSummary[];
}

export interface CompareSide {
  key: string;
  request_count: number;
  error_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: string;
  unpriced_count: number;
  p50_ms: number | null;
  p95_ms: number | null;
  error_rate: number;
}

export type CompareDimension = "prompt_version" | "model";

export interface CompareResponse {
  schema_version: SchemaVersion;
  left: CompareSide;
  right: CompareSide;
}

export interface DualPlaygroundRequest {
  schema_version: SchemaVersion;
  prompt: string;
  left_model: string;
  right_model: string;
  prompt_version: string;
}

export interface DualPlaygroundSide {
  model: string;
  answer: string;
  latency_ms: number | null;
}

export interface DualPlaygroundResponse {
  schema_version: SchemaVersion;
  trace_id: string;
  prompt_version: string;
  left: DualPlaygroundSide;
  right: DualPlaygroundSide;
}
