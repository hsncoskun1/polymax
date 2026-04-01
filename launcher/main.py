"""POLYMAX Launcher — starts backend, frontend, opens browser."""

import subprocess
import sys
import time
import signal
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent.parent

# Read host/port from config/default.toml so there is a single source of truth.
# Fall back to defaults only if config is unavailable.
def _load_launcher_config() -> dict:
    try:
        import tomli
        config_path = ROOT / "config" / "default.toml"
        with open(config_path, "rb") as f:
            return tomli.load(f)
    except Exception:
        return {}

_cfg = _load_launcher_config()
BACKEND_HOST  = _cfg.get("backend",  {}).get("host", "127.0.0.1")
BACKEND_PORT  = _cfg.get("backend",  {}).get("port", 8000)
FRONTEND_HOST = _cfg.get("frontend", {}).get("host", "127.0.0.1")
FRONTEND_PORT = _cfg.get("frontend", {}).get("port", 5173)
READY_TIMEOUT = 30  # seconds
POLL_INTERVAL = 0.5

# Resolve npm path for Windows (Git Bash may not have it in PATH)
NPM_CMD = "npm.cmd" if sys.platform == "win32" else "npm"

processes: list[subprocess.Popen] = []


def log(msg: str) -> None:
    print(f"[POLYMAX] {msg}", flush=True)


def start_backend() -> subprocess.Popen:
    log(f"Starting backend on {BACKEND_HOST}:{BACKEND_PORT}...")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.app.main:app",
            "--host", BACKEND_HOST,
            "--port", str(BACKEND_PORT),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(proc)
    return proc


def start_frontend() -> subprocess.Popen:
    log(f"Starting frontend on {FRONTEND_HOST}:{FRONTEND_PORT}...")
    proc = subprocess.Popen(
        [NPM_CMD, "run", "dev"],
        cwd=str(ROOT / "frontend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(proc)
    return proc


def wait_for_url(url: str, label: str, proc: subprocess.Popen) -> bool:
    """Poll url until it responds 200 or timeout."""
    deadline = time.time() + READY_TIMEOUT
    while time.time() < deadline:
        # Check if process died
        if proc.poll() is not None:
            log(f"ERROR: {label} process exited with code {proc.returncode}")
            stdout = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            if stdout:
                for line in stdout.strip().splitlines()[-10:]:
                    log(f"  {label}: {line}")
            return False
        try:
            with urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    log(f"{label} is ready.")
                    return True
        except (URLError, OSError):
            pass
        time.sleep(POLL_INTERVAL)
    log(f"ERROR: {label} did not become ready within {READY_TIMEOUT}s")
    return False


def cleanup() -> None:
    log("Shutting down...")
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    # Give processes time to exit gracefully
    deadline = time.time() + 5
    for proc in processes:
        remaining = max(0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()
    log("All processes stopped.")


def main() -> int:
    log("POLYMAX Launcher v0.1.0")
    log(f"Project root: {ROOT}")

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, lambda *_: None)  # let finally block handle it

    backend_proc = start_backend()
    frontend_proc = start_frontend()

    try:
        # Wait for backend first (frontend depends on it for health badge)
        backend_ok = wait_for_url(
            f"http://{BACKEND_HOST}:{BACKEND_PORT}/health",
            "Backend",
            backend_proc,
        )
        if not backend_ok:
            log("Backend failed to start. Aborting.")
            return 1

        frontend_ok = wait_for_url(
            f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/",
            "Frontend",
            frontend_proc,
        )
        if not frontend_ok:
            log("Frontend failed to start. Aborting.")
            return 1

        panel_url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/user"
        log(f"Opening browser: {panel_url}")
        webbrowser.open(panel_url)

        log("POLYMAX is running. Press Ctrl+C to stop.")

        # Keep alive until interrupted or a process dies
        while True:
            if backend_proc.poll() is not None:
                log(f"Backend exited unexpectedly (code {backend_proc.returncode})")
                return 1
            if frontend_proc.poll() is not None:
                log(f"Frontend exited unexpectedly (code {frontend_proc.returncode})")
                return 1
            time.sleep(1)

    except KeyboardInterrupt:
        log("Ctrl+C received.")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
