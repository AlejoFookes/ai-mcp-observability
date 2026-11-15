import type { WindowParams } from "../api/types";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Format a Date as datetime-local value (local wall clock, no Z). */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number): string => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Parse datetime-local into timezone-aware ISO-8601 for the API. */
export function fromLocalInputValue(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`Invalid datetime: ${value}`);
  }
  return parsed.toISOString();
}

export function defaultWindowInputs(): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to.getTime() - 7 * DAY_MS);
  return {
    from: toLocalInputValue(from),
    to: toLocalInputValue(to),
  };
}

export function windowParamsFromInputs(
  fromInput: string,
  toInput: string,
): WindowParams {
  const from = fromLocalInputValue(fromInput);
  // `<input type="datetime-local">` is minute-precision and the API treats `to`
  // as exclusive. Pad one minute so events in the selected minute are included.
  const toDate = new Date(fromLocalInputValue(toInput));
  toDate.setUTCMinutes(toDate.getUTCMinutes() + 1);
  const liveFloor = new Date(Date.now() + 60_000);
  const to = toDate.getTime() >= liveFloor.getTime() ? toDate : liveFloor;
  return {
    from,
    to: to.toISOString(),
  };
}

export function formatUsd(value: string): string {
  const n = Number(value);
  if (Number.isNaN(n)) {
    return value;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(n);
}

export function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

export function formatMs(ms: number): string {
  return `${ms.toFixed(0)} ms`;
}

export function formatOccurredAt(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso;
  }
  return parsed.toLocaleString();
}
