import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import UserPanel from "./pages/UserPanel";
import AdminPanel from "./pages/AdminPanel";

export default function App() {
  const [marketRefreshKey, setMarketRefreshKey] = useState(0);

  function handleSyncDone() {
    setMarketRefreshKey((k) => k + 1);
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/user" element={<UserPanel refreshKey={marketRefreshKey} />} />
        <Route path="/admin" element={<AdminPanel onSyncDone={handleSyncDone} />} />
        <Route path="*" element={<Navigate to="/user" replace />} />
      </Routes>
    </AppShell>
  );
}
