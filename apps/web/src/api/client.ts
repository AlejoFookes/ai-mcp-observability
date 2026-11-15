import type {
  ApiErrorBody,
  CompareDimension,
  CompareResponse,
  DualPlaygroundRequest,
  DualPlaygroundResponse,
  FinOpsGroupBy,
  FinOpsSummaryResponse,
  HealthResponse,
  LatencyGroupBy,
  LatencyResponse,
  TraceListResponse,
  TraceResponse,
  WindowParams,
} from "./types";
import { getIngestToken } from "./token";

export class ApiClientError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error.message ?? fallback);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }
}

function apiBase(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (typeof fromEnv === "string" && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, "");
  }
  return "";
}

async function parseError(response: Response): Promise<ApiErrorBody | null> {
  try {
    const data: unknown = await response.json();
    if (
      typeof data === "object" &&
      data !== null &&
      "error" in data &&
      "schema_version" in data
    ) {
      return data as ApiErrorBody;
    }
  } catch {
    return null;
  }
  return null;
}

async function apiRequest<T>(
  path: string,
  init: RequestInit,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const token = getIngestToken();
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new ApiClientError(
      response.status,
      await parseError(response),
      `Request failed with ${response.status}`,
    );
  }

  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchHealth(ready = false): Promise<HealthResponse> {
  const query = ready ? "?ready=true" : "";
  return apiGet<HealthResponse>(`/api/v1/health${query}`);
}

function withWindow(
  path: string,
  window: WindowParams,
  extra: Record<string, string | boolean>,
): string {
  const params = new URLSearchParams({
    from: window.from,
    to: window.to,
  });
  for (const [key, value] of Object.entries(extra)) {
    params.set(key, String(value));
  }
  return `${path}?${params.toString()}`;
}

export function fetchFinOpsSummary(
  window: WindowParams,
  groupBy: FinOpsGroupBy,
  includeJudge: boolean,
): Promise<FinOpsSummaryResponse> {
  return apiGet<FinOpsSummaryResponse>(
    withWindow("/api/v1/finops/summary", window, {
      group_by: groupBy,
      include_judge: includeJudge,
    }),
  );
}

export function fetchLatency(
  window: WindowParams,
  groupBy: LatencyGroupBy,
): Promise<LatencyResponse> {
  return apiGet<LatencyResponse>(
    withWindow("/api/v1/latency", window, { group_by: groupBy }),
  );
}

export function fetchTrace(traceId: string): Promise<TraceResponse> {
  const encoded = encodeURIComponent(traceId);
  return apiGet<TraceResponse>(`/api/v1/traces/${encoded}`);
}

export function fetchTraceList(
  window: WindowParams,
  limit = 50,
): Promise<TraceListResponse> {
  return apiGet<TraceListResponse>(
    withWindow("/api/v1/traces", window, { limit: String(limit) }),
  );
}

export function fetchCompare(
  window: WindowParams,
  dimension: CompareDimension,
  left: string,
  right: string,
): Promise<CompareResponse> {
  return apiGet<CompareResponse>(
    withWindow("/api/v1/compare", window, {
      dimension,
      left,
      right,
    }),
  );
}

export function postPlaygroundDual(
  body: DualPlaygroundRequest,
): Promise<DualPlaygroundResponse> {
  return apiPost<DualPlaygroundResponse>("/api/v1/playground/dual", body);
}
