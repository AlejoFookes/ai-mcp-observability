import { useState, type FormEvent } from "react";
import { clearIngestToken, getIngestToken, setIngestToken } from "../api/token";

interface TokenFormProps {
  onChange?: () => void;
}

export function TokenForm({ onChange }: TokenFormProps) {
  const [draft, setDraft] = useState(() => getIngestToken() ?? "");
  const [saved, setSaved] = useState(() => getIngestToken());

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = draft.trim();
    if (next === "") {
      clearIngestToken();
      setSaved(null);
    } else {
      setIngestToken(next);
      setSaved(next);
    }
    onChange?.();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 border-b border-[var(--line)] pb-4"
    >
      <label className="flex min-w-[16rem] flex-1 flex-col gap-1 text-sm">
        <span className="text-[var(--muted)]">Ingest token (sessionStorage)</span>
        <input
          type="password"
          autoComplete="off"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Bearer value for /api/v1"
          className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
        />
      </label>
      <button
        type="submit"
        className="rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
      >
        Save
      </button>
      <p className="w-full text-xs text-[var(--muted)]">
        {saved === null ? "No token saved." : "Token saved for this browser tab."}
      </p>
    </form>
  );
}
