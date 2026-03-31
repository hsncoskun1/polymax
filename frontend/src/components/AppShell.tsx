import { type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import HealthBadge from "./HealthBadge";

function NavTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-4 py-2 text-sm font-medium rounded-md transition-colors ${
          isActive
            ? "bg-[var(--color-surface)] text-[var(--color-accent)]"
            : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--color-border)] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className="text-lg font-bold tracking-tight text-[var(--color-text)]">
            POLYMAX
          </span>
          <nav className="flex gap-1">
            <NavTab to="/user" label="User" />
            <NavTab to="/admin" label="Admin" />
          </nav>
        </div>
        <HealthBadge />
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
