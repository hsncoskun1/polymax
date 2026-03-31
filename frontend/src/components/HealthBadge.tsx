import { useEffect, useState } from "react";

type Status = "checking" | "ok" | "error";

export default function HealthBadge() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const check = () => {
      fetch("http://127.0.0.1:8000/health")
        .then((r) => {
          setStatus(r.ok ? "ok" : "error");
        })
        .catch(() => setStatus("error"));
    };
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  const colors: Record<Status, string> = {
    checking: "bg-yellow-500/20 text-yellow-400",
    ok: "bg-green-500/20 text-green-400",
    error: "bg-red-500/20 text-red-400",
  };

  const labels: Record<Status, string> = {
    checking: "Checking...",
    ok: "Backend OK",
    error: "Backend Offline",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colors[status]}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          status === "ok"
            ? "bg-green-400"
            : status === "error"
              ? "bg-red-400"
              : "bg-yellow-400"
        }`}
      />
      {labels[status]}
    </span>
  );
}
