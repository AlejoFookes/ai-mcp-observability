interface PlaceholderPageProps {
  title: string;
  summary: string;
}

export function PlaceholderPage({ title, summary }: PlaceholderPageProps) {
  return (
    <section className="rounded border border-[var(--line)] bg-[var(--panel)] p-6">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-[var(--muted)]">{summary}</p>
      <p className="mt-4 text-sm text-[var(--muted)]">
        Screen body arrives in M4.2 / M4.3. Scaffold only.
      </p>
    </section>
  );
}
