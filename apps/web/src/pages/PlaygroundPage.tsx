import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ApiClientError, postPlaygroundDual } from "../api/client";
import type { DualPlaygroundResponse } from "../api/types";
import { formatMs } from "../lib/window";

interface Turn {
  prompt: string;
  result: DualPlaygroundResponse | null;
  error: string | null;
}

const DEFAULT_LEFT = "openai/gpt-oss-20b";
const DEFAULT_RIGHT = "openai/gpt-oss-120b";

export function PlaygroundPage() {
  const [leftModel, setLeftModel] = useState(DEFAULT_LEFT);
  const [rightModel, setRightModel] = useState(DEFAULT_RIGHT);
  const [promptVersion, setPromptVersion] = useState("playground");
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = draft.trim();
    if (prompt === "" || pending) {
      return;
    }
    setPending(true);
    setDraft("");
    const index = turns.length;
    setTurns((prev) => [...prev, { prompt, result: null, error: null }]);
    try {
      const result = await postPlaygroundDual({
        schema_version: "1.0",
        prompt,
        left_model: leftModel.trim() || DEFAULT_LEFT,
        right_model: rightModel.trim() || DEFAULT_RIGHT,
        prompt_version: promptVersion.trim() || "playground",
      });
      setTurns((prev) =>
        prev.map((turn, i) => (i === index ? { ...turn, result } : turn)),
      );
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Request failed";
      setTurns((prev) =>
        prev.map((turn, i) => (i === index ? { ...turn, error: message } : turn)),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Playground</h2>
        <p className="mt-1 max-w-2xl text-[var(--muted)]">
          Escribí un prompt y corré el mismo mensaje en dos modelos. Cada lado emite
          telemetría a FinOps / Latency / Traces (mismo <code>trace_id</code>).
        </p>
      </div>

      <div className="flex flex-wrap gap-3 border-b border-[var(--line)] pb-4">
        <label className="flex min-w-[10rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Left model</span>
          <input
            value={leftModel}
            onChange={(e) => setLeftModel(e.target.value)}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2 font-mono text-sm"
          />
        </label>
        <label className="flex min-w-[10rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Right model</span>
          <input
            value={rightModel}
            onChange={(e) => setRightModel(e.target.value)}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2 font-mono text-sm"
          />
        </label>
        <label className="flex min-w-[8rem] flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">prompt_version</span>
          <input
            value={promptVersion}
            onChange={(e) => setPromptVersion(e.target.value)}
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"
          />
        </label>
      </div>

      <div className="flex flex-col gap-6">
        {turns.length === 0 ? (
          <p className="rounded border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 py-6 text-sm text-[var(--muted)]">
            Probá: “Explicá FinOps en una frase” o “¿Cuántos días tengo para devolver un
            pedido?”. Después abrí FinOps / Compare / Traces.
          </p>
        ) : null}

        {turns.map((turn, index) => (
          <article
            key={`${index}-${turn.prompt.slice(0, 24)}`}
            className="flex flex-col gap-3 rounded border border-[var(--line)] bg-[var(--panel)] p-4"
          >
            <p className="text-sm font-medium">You</p>
            <p className="whitespace-pre-wrap text-sm">{turn.prompt}</p>

            {turn.error !== null ? (
              <p role="alert" className="text-sm text-red-800">
                {turn.error}
              </p>
            ) : null}

            {turn.result === null && turn.error === null ? (
              <p className="text-sm text-[var(--muted)]">Running both models…</p>
            ) : null}

            {turn.result !== null ? (
              <>
                <p className="text-xs text-[var(--muted)]">
                  <Link className="underline" to="/traces">
                    Traces
                  </Link>
                  {": "}
                  <code>{turn.result.trace_id}</code>
                  {" · "}
                  prompt_version=<code>{turn.result.prompt_version}</code>
                </p>
                <div className="grid gap-3 lg:grid-cols-2">
                  <SideCard side="Left" data={turn.result.left} />
                  <SideCard side="Right" data={turn.result.right} />
                </div>
              </>
            ) : null}
          </article>
        ))}
      </div>

      <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-[var(--muted)]">Mensaje</span>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            placeholder="Escribí el prompt a evaluar en ambos modelos…"
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={pending || draft.trim() === ""}
          className="w-fit rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {pending ? "Evaluando…" : "Evaluar en dos modelos"}
        </button>
      </form>
    </div>
  );
}

function SideCard({
  side,
  data,
}: {
  side: string;
  data: DualPlaygroundResponse["left"];
}) {
  return (
    <div className="rounded border border-[var(--line)] bg-[var(--bg)] p-3">
      <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{side}</p>
      <p className="mt-1 font-mono text-sm font-medium">{data.model}</p>
      <p className="mt-1 text-xs text-[var(--muted)]">
        {data.latency_ms === null ? "—" : formatMs(data.latency_ms)}
      </p>
      <p className="mt-3 whitespace-pre-wrap text-sm">{data.answer}</p>
    </div>
  );
}
