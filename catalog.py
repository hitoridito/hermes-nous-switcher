"""
catalog.py — Nous Portal model catalog fetcher with disk cache.

Fetches the full live model list from inference-api.nousresearch.com/v1/models
(OpenRouter-compatible, public, no auth required) and caches it locally so
subsequent reads are instant. Mirrors the pattern Hermes itself uses for
``nous_recommended_cache.json``.

Cache location: ``$HERMES_HOME/cache/nous_full_catalog.json`` (default
``~/.hermes/cache/nous_full_catalog.json``).

Cache TTL: 1 hour. On network failure, returns the last-known-good disk cache
rather than empty — so a transient Portal hiccup doesn't blank the picker.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Source endpoint — the same one Hermes's own models.py uses for live pricing
# (see hermes_cli/models.py: get_pricing_for_provider('nous')).
NOUS_MODELS_URL = "https://inference-api.nousresearch.com/v1/models"
CACHE_FILENAME = "nous_full_catalog.json"
CACHE_TTL_SECONDS = 60 * 60  # 1 hour
FETCH_TIMEOUT_SECONDS = 10.0
USER_AGENT = "hermes-nous-switcher/0.1 (+https://hermes-agent.nousresearch.com)"


def _hermes_home() -> Path:
    """Resolve ``$HERMES_HOME`` or fall back to ``~/.hermes``."""
    home = os.environ.get("HERMES_HOME", "").strip()
    if home:
        return Path(home).expanduser()
    return Path.home() / ".hermes"


def _cache_path() -> Path:
    p = _hermes_home() / "cache" / CACHE_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_disk_cache() -> dict[str, Any] | None:
    """Return the last-known-good disk cache, or ``None`` if missing/invalid."""
    path = _cache_path()
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _write_disk_cache(payload: dict[str, Any]) -> None:
    """Persist the catalog payload atomically. Failures are non-fatal."""
    path = _cache_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError:
        # Disk full or permission denied — live in-memory data still works.
        pass


def _parse_models(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the OpenRouter-compatible ``/v1/models`` payload into a clean list.

    Returns a list of dicts with the fields our UI actually needs. We keep
    ``raw`` (the full upstream item) under ``_raw`` for future fields the UI
    may want to surface (knowledge cutoff, links, etc.) without re-fetching.
    """
    out: list[dict[str, Any]] = []
    for item in raw.get("data", []):
        if not isinstance(item, dict):
            continue
        mid = item.get("id")
        if not isinstance(mid, str) or not mid.strip():
            continue

        pricing = item.get("pricing") or {}
        arch = item.get("architecture") or {}

        # Pricing is per-token in the upstream payload. Convert to $/Mtok for
        # the UI — matches the format Hermes's own models.py emits.
        def _per_mtok(val: Any) -> str | None:
            if val in (None, ""):
                return None
            try:
                v = float(val)
            except (TypeError, ValueError):
                return None
            if v == 0:
                return "free"
            return f"${v * 1_000_000:.2f}"

        out.append({
            "id": mid,
            "name": str(item.get("name") or mid),
            "description": str(item.get("description") or ""),
            "context_length": int(item.get("context_length") or 0),
            "prompt_price_per_mtok": _per_mtok(pricing.get("prompt")),
            "completion_price_per_mtok": _per_mtok(pricing.get("completion")),
            "input_modalities": list(arch.get("input_modalities") or []),
            "output_modalities": list(arch.get("output_modalities") or []),
            "supports_vision": "image" in (arch.get("input_modalities") or []),
            "supports_reasoning": bool((item.get("reasoning") or {}).get("mandatory"))
                                   or "include_reasoning" in (item.get("supported_parameters") or []),
            "is_free": pricing.get("prompt") in (None, "0", "0.0", "0.00", 0, 0.0)
                       and pricing.get("completion") in (None, "0", "0.0", "0.00", 0, 0.0),
            "knowledge_cutoff": item.get("knowledge_cutoff"),
            "_raw": item,  # full upstream payload, for future fields
        })
    return out


def fetch_catalog(*, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch the Nous Portal model catalog, with disk + TTL caching.

    Returns a dict shaped as::

        {
            "models": [...],          # list of normalized model dicts
            "fetched_at": <epoch>,     # when the live fetch succeeded
            "source": "live" | "cache" | "cache_stale",
            "count": <int>,
        }

    Strategy:
      1. If ``force_refresh`` is False and disk cache is fresh (< TTL), return it.
      2. Otherwise, hit the live endpoint.
      3. On live success: persist + return.
      4. On live failure: fall back to stale disk cache (if any) so the UI
         keeps working during Portal hiccups.
      5. On total failure (no cache, no network): return empty list with
         ``source="error"`` so the UI can show a clear "couldn't reach Portal".
    """
    now = time.time()
    disk = _read_disk_cache()

    # 1. Fresh disk cache → return it.
    if not force_refresh and disk:
        fetched_at = float(disk.get("fetched_at") or 0)
        if fetched_at > 0 and (now - fetched_at) < CACHE_TTL_SECONDS:
            return {
                "models": disk.get("models") or [],
                "fetched_at": fetched_at,
                "source": "cache",
                "count": len(disk.get("models") or []),
            }

    # 2. Try the live endpoint.
    req = urllib.request.Request(
        NOUS_MODELS_URL,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    live: dict[str, Any] | None = None
    error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            live = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        error = f"{type(exc).__name__}: {exc}"

    # 3. Live success → persist + return.
    if isinstance(live, dict):
        models = _parse_models(live)
        payload = {
            "models": models,
            "fetched_at": now,
            "source_url": NOUS_MODELS_URL,
        }
        _write_disk_cache(payload)
        return {
            "models": models,
            "fetched_at": now,
            "source": "live",
            "count": len(models),
        }

    # 4. Live failed but disk cache exists → return stale with a flag.
    if disk and disk.get("models"):
        return {
            "models": disk.get("models") or [],
            "fetched_at": float(disk.get("fetched_at") or 0),
            "source": "cache_stale",
            "count": len(disk.get("models") or []),
            "warning": f"Live fetch failed ({error}); using last-known-good cache.",
        }

    # 5. Total failure.
    return {
        "models": [],
        "fetched_at": 0.0,
        "source": "error",
        "count": 0,
        "warning": f"Could not reach Nous Portal ({error}) and no cache available.",
    }


if __name__ == "__main__":
    # Quick CLI sanity-check: ``python3 catalog.py`` prints a summary.
    import sys
    force = "--refresh" in sys.argv
    out = fetch_catalog(force_refresh=force)
    print(f"source: {out['source']}  count: {out['count']}  fetched_at: {out['fetched_at']}")
    if out["models"]:
        print("\nFirst 3 models:")
        for m in out["models"][:3]:
            print(f"  - {m['id']}  ctx={m['context_length']}  prompt={m['prompt_price_per_mtok']}  vision={m['supports_vision']}")
