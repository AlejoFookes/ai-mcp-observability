import type { ReactNode } from "react";
import { ApiClientError } from "../api/client";

interface QueryStatusProps {
  isPending: boolean;
  error: unknown;
  isEmpty: boolean;
  emptyMessage: string;
  children: ReactNode;
}

function errorMessage(error: unknown): { title: string; detail: string } {
  if (error instanceof ApiClientError) {
    if (error.status === 401) {
      return {
        title: "Unauthorized",
        detail:
          "Save a valid ingest token above, then reload this view. The API rejected the Bearer credential.",
      };
    }
    return {
      title: `Request failed (${error.status})`,
      detail: error.message,
    };
  }
  if (error instanceof Error) {
    return { title: "Network error", detail: error.message };
  }
  return { title: "Network error", detail: "Unexpected failure contacting the API." };
}

export function QueryStatus({
  isPending,
  error,
  isEmpty,
  emptyMessage,
  children,
}: QueryStatusProps) {
  if (isPending) {
    return (
      <p className="rounded border border-[var(--line)] bg-[var(--panel)] px-4 py-6 text-sm text-[var(--muted)]">
        Loading…
      </p>
    );
  }

  if (error !== null && error !== undefined) {
    const { title, detail } = errorMessage(error);
    return (
      <div
        role="alert"
        className="rounded border border-red-300 bg-red-50 px-4 py-4 text-sm text-red-900"
      >
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-red-800/90">{detail}</p>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <p className="rounded border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 py-6 text-sm text-[var(--muted)]">
        {emptyMessage}
      </p>
    );
  }

  return <>{children}</>;
}
