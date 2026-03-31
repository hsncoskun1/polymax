import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import UserPanel from "./pages/UserPanel";
import AdminPanel from "./pages/AdminPanel";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/user" element={<UserPanel />} />
        <Route path="/admin" element={<AdminPanel />} />
        <Route path="*" element={<Navigate to="/user" replace />} />
      </Routes>
    </AppShell>
  );
}
