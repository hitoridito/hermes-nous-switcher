"""
hermes_catalog_overlay.py — make Switcher selections visible to Hermes UI.

Hermes Desktop Settings does not read the full Nous `/v1/models` catalog. It
reads the curated Hermes model catalog through `hermes_cli.model_catalog`, and
`/api/model/options` returns only the first N curated models. A full-catalog
selection like `openrouter/owl-alpha` can be valid for the Nous inference API
while still rendering as an empty Select in Settings because the Select has no
matching item.

This module fixes that without touching Hermes source:

1. Create a local model-catalog manifest at
   `~/.hermes/cache/nous_switcher_model_catalog.json`.
2. Put the selected model first under `providers.nous.models`.
3. Append the existing curated Nous list after it.
4. Set `model_catalog.providers.nous.url` in `config.yaml` to a `file://` URL
   pointing at the overlay.

Hermes already supports per-provider catalog override URLs via
`model_catalog.providers.<provider>.url`; using that hook keeps this fully
user-space/update-safe.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


def _hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME", "").strip()
    if home:
        return Path(home).expanduser()
    return Path.home() / ".hermes"


def _config_path() -> Path:
    return _hermes_home() / "config.yaml"


def _curated_catalog_path() -> Path:
    return _hermes_home() / "cache" / "model_catalog.json"


def _overlay_path() -> Path:
    p = _hermes_home() / "cache" / "nous_switcher_model_catalog.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _file_url(path: Path) -> str:
    # pathlib.as_uri() requires absolute paths and percent-encodes safely.
    return path.resolve().as_uri()


def _read_curated_nous_ids() -> list[str]:
    """Read Hermes' existing curated Nous list from its cache, best-effort."""
    path = _curated_catalog_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        data = {}

    models = (
        data.get("providers", {})
        .get("nous", {})
        .get("models", [])
        if isinstance(data, dict)
        else []
    )
    out: list[str] = []
    for item in models if isinstance(models, list) else []:
        mid = ""
        if isinstance(item, dict):
            mid = str(item.get("id") or "").strip()
        elif isinstance(item, str):
            mid = item.strip()
        if mid and mid not in out:
            out.append(mid)
    return out


def _read_existing_overlay_ids() -> list[str]:
    """Keep previously selected Switcher models near the top if present."""
    path = _overlay_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    models = (
        data.get("providers", {})
        .get("nous", {})
        .get("models", [])
        if isinstance(data, dict)
        else []
    )
    out: list[str] = []
    for item in models if isinstance(models, list) else []:
        mid = str(item.get("id") or "").strip() if isinstance(item, dict) else str(item or "").strip()
        if mid and mid not in out:
            out.append(mid)
    return out


def _write_overlay_manifest(selected_model: str) -> Path:
    selected = selected_model.strip()
    curated = _read_curated_nous_ids()
    existing = _read_existing_overlay_ids()

    # Order matters because Hermes Settings caps `/api/model/options` to the
    # first 50 models. Selected first guarantees the Select can render it.
    ordered: list[str] = []
    for mid in [selected, *existing, *curated]:
        if mid and mid not in ordered:
            ordered.append(mid)

    manifest = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "generated_by": "nous_switcher",
            "purpose": "Local overlay so full Nous Portal selections appear in Hermes Settings/model picker.",
        },
        "providers": {
            "nous": {
                "metadata": {
                    "overlay_selected_model": selected,
                    "base_catalog": str(_curated_catalog_path()),
                },
                "models": [{"id": mid, "description": "selected via Nous Switcher" if mid == selected else ""} for mid in ordered],
            }
        },
    }

    path = _overlay_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def _ensure_config_override(overlay: Path) -> str:
    """Set config.yaml model_catalog.providers.nous.url to the overlay file URL."""
    cfg_path = _config_path()
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(cfg_path, encoding="utf-8") as fh:
        cfg = yaml.load(fh)
    if not isinstance(cfg, dict):
        cfg = CommentedMap()

    def cmap(value: Any = None) -> CommentedMap:
        if isinstance(value, CommentedMap):
            return value
        cm = CommentedMap()
        if isinstance(value, dict):
            for k, v in value.items():
                cm[k] = v
        return cm

    model_catalog = cmap(cfg.get("model_catalog"))
    providers = cmap(model_catalog.get("providers"))
    nous = cmap(providers.get("nous"))

    url = _file_url(overlay)
    nous["url"] = url
    providers["nous"] = nous
    model_catalog["providers"] = providers
    # Leave any existing enabled/ttl/url values alone. If absent, Hermes defaults
    # model_catalog.enabled to true, so no explicit write is needed.
    cfg["model_catalog"] = model_catalog

    tmp = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh)
    os.replace(tmp, cfg_path)
    return url


def ensure_nous_model_visible(selected_model: str) -> dict[str, Any]:
    """Create/update the Nous overlay and wire config.yaml to it.

    Returns a small status dict used by the API response.
    """
    selected = selected_model.strip()
    if not selected:
        return {"ok": False, "error": "selected_model is required"}
    overlay = _write_overlay_manifest(selected)
    url = _ensure_config_override(overlay)
    return {
        "ok": True,
        "overlay_path": str(overlay),
        "overlay_url": url,
        "selected_model": selected,
    }


if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(ensure_nous_model_visible(model), indent=2))
