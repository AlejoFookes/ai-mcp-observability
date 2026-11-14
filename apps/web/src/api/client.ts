import type { ApiErrorBody, HealthResponse } from "./types";
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

export async function apiGet<T>(path: string): Promise<T> {
  const headers = new Headers({ Accept: "application/json" });
  const token = getIngestToken();
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBase()}${path}`, {
    method: "GET",
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

export function fetchHealth(ready = false): Promise<HealthResponse> {
  const query = ready ? "?ready=true" : "";
  return apiGet<HealthResponse>(`/api/v1/health${query}`);
}
