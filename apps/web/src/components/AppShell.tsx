import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router";
import { TokenForm } from "./TokenForm";

const nav: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: "/", label: "FinOps", end: true },
  { to: "/latency", label: "Latency" },
  { to: "/traces", label: "Traces" },
  { to: "/compare", label: "Compare" },
];

export function AppShell() {
  const queryClient = useQueryClient();

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-6 py-8">
      <header className="flex flex-col gap-6">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--muted)]">
            multiMCP
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">
            FinOps, latency, traces and prompt/model compare against the local API.
          </p>
        </div>
        <TokenForm
          onChange={() => {
            void queryClient.invalidateQueries();
          }}
        />
        <nav className="flex flex-wrap gap-2">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                [
                  "rounded px-3 py-2 text-sm",
                  isActive
                    ? "bg-[var(--accent)] text-white"
                    : "border border-[var(--line)] bg-[var(--panel)]",
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
