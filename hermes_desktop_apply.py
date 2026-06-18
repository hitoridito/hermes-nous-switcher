"""
hermes_desktop_apply.py — call the live Hermes Desktop Apply endpoint.

Writing ~/.hermes/config.yaml directly can make Settings *display* a selected
model, but Hermes Desktop may keep a live backend/renderer state that only
updates after Settings -> Apply calls POST /api/model/set.

This module discovers the running local dashboard backend, reads its ephemeral
session token from that same-user process environment, and calls the same
endpoint Hermes Settings uses:

    POST /api/model/set
    X-Hermes-Session-Token: <ephemeral per-process token>
    {"scope":"main", "provider":"nous", "model":"..."}

The token is never logged or returned. This is localhost/same-user only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DashboardBackend:
    pid: int
    port: int
    token: str

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def _read_cmdline(pid: str) -> str:
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "ignore").replace("\x00", " ")
    except OSError:
        return ""


def _read_environ(pid: int) -> dict[str, str]:
    try:
        raw = open(f"/proc/{pid}/environ", "rb").read().split(b"\x00")
    except OSError:
        return {}
    env: dict[str, str] = {}
    for item in raw:
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode()] = value.decode(errors="ignore")
        except Exception:
            continue
    return env


def _dashboard_pids() -> list[int]:
    out: list[int] = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        cmd = _read_cmdline(pid)
        if "hermes_cli.main dashboard" in cmd:
            out.append(int(pid))
    return sorted(out)


def _listening_ports_by_pid() -> dict[int, list[int]]:
    """Return {pid: [127.0.0.1 listening ports]} using ss.

    We intentionally avoid returning command output to callers because ss lines
    can include process command names. No secrets are present, but keep it small.
    """
    ports: dict[int, list[int]] = {}
    try:
        output = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL, timeout=3)
    except Exception:
        return ports
    for line in output.splitlines():
        if "127.0.0.1:" not in line or "pid=" not in line:
            continue
        pid_match = re.search(r"pid=(\d+),", line)
        port_match = re.search(r"127\.0\.0\.1:(\d+)", line)
        if not pid_match or not port_match:
            continue
        try:
            pid = int(pid_match.group(1))
            port = int(port_match.group(1))
        except ValueError:
            continue
        ports.setdefault(pid, []).append(port)
    return ports


def discover_dashboard_backend() -> DashboardBackend | None:
    ports_by_pid = _listening_ports_by_pid()
    for pid in _dashboard_pids():
        env = _read_environ(pid)
        token = env.get("HERMES_DASHBOARD_SESSION_TOKEN", "").strip()
        if not token:
            continue
        ports = ports_by_pid.get(pid) or []
        # Dashboard process should have one loopback listener. If several appear,
        # prefer non-9120 so we never mistake ourselves for Nous Switcher.
        ports = [p for p in ports if p != 9120]
        if not ports:
            continue
        return DashboardBackend(pid=pid, port=ports[0], token=token)
    return None


def apply_main_model(provider: str, model: str) -> dict[str, Any]:
    """Apply the main model through the live Hermes Desktop backend if present."""
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        return {"ok": False, "error": "provider and model are required"}

    backend = discover_dashboard_backend()
    if backend is None:
        return {
            "ok": False,
            "error": "No running Hermes Desktop dashboard backend with session token found",
        }

    body = json.dumps({"scope": "main", "provider": provider, "model": model}).encode()
    req = urllib.request.Request(
        backend.base_url + "/api/model/set",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hermes-Session-Token": backend.token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode(errors="replace")[:500]
        except Exception:
            detail = ""
        return {"ok": False, "error": f"Hermes Desktop apply failed: HTTP {exc.code}", "detail": detail}
    except Exception as exc:
        return {"ok": False, "error": f"Hermes Desktop apply failed: {exc}"}

    return {
        "ok": bool(data.get("ok")),
        "provider": data.get("provider", provider),
        "model": data.get("model", model),
        "base_url": data.get("base_url", ""),
        "stale_aux": data.get("stale_aux", []),
        "gateway_tools": data.get("gateway_tools", []),
        "dashboard": {"pid": backend.pid, "port": backend.port},
    }


if __name__ == "__main__":
    import sys
    m = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(apply_main_model("nous", m), indent=2))
