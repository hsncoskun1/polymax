import MarketList from "../components/MarketList";

export default function UserPanel() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">User Panel</h1>
      <section>
        <h2 className="text-sm font-medium text-[var(--color-text-muted)] uppercase tracking-wide mb-3">
          Markets
        </h2>
        <MarketList />
      </section>
    </div>
  );
}
