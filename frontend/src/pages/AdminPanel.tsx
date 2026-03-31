export default function AdminPanel() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Admin Panel</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusChip label="Backend" value="v0.1.0" />
        <StatusChip label="Frontend" value="v0.1.0" />
        <StatusChip label="Uptime" value="—" />
      </div>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h3 className="font-semibold text-[var(--color-text)] mb-3">
          System Overview
        </h3>
        <p className="text-sm text-[var(--color-text-muted)]">
          Service monitoring and configuration will appear here.
        </p>
      </div>
    </div>
  );
}

function StatusChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 flex items-center justify-between">
      <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--color-accent)]">
        {value}
      </span>
    </div>
  );
}
