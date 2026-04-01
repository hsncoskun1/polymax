import DiscoverAction from "../components/DiscoverAction";
import SyncAction from "../components/SyncAction";

interface AdminPanelProps {
  onSyncDone?: () => void;
}

export default function AdminPanel({ onSyncDone }: AdminPanelProps) {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Admin Panel</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusChip label="Backend" value="—" />
        <StatusChip label="Frontend" value="—" />
        <StatusChip label="Uptime" value="—" />
      </div>
      <DiscoverAction />
      <SyncAction onSuccess={onSyncDone} />
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
