export default function UserPanel() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">User Panel</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Portfolio" description="Asset overview and positions" />
        <Card title="Markets" description="Available markets and events" />
        <Card title="Activity" description="Recent transactions and orders" />
        <Card title="Settings" description="Account preferences" />
      </div>
    </div>
  );
}

function Card({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5 hover:border-[var(--color-accent)]/30 transition-colors">
      <h3 className="font-semibold text-[var(--color-text)]">{title}</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {description}
      </p>
    </div>
  );
}
