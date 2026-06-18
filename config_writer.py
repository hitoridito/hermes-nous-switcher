"""
config_writer.py — Atomic write to ``$HERMES_HOME/config.yaml``.

Uses ``ruamel.yaml`` in round-trip mode so the existing config keeps its
comments, key order, and overall structure. We only touch the ``model:`` block.

Backups are written next to config.yaml with a timestamp suffix, matching
Hermes's own backup convention (``config.yaml.bak.<label>_<timestamp>``).
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def _hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME", "").strip()
    if home:
        return Path(home).expanduser()
    return Path.home() / ".hermes"


def _config_path() -> Path:
    return _hermes_home() / "config.yaml"


def read_current_model() -> dict[str, str]:
    """Return the current ``model:`` block as a plain dict.

    Returns ``{"provider": "", "default": "", "base_url": ""}`` if the
    file or block is missing/empty — never raises.
    """
    path = _config_path()
    out = {"provider": "", "default": "", "base_url": ""}
    if not path.exists():
        return out
    try:
        yaml = YAML(typ="rt")
        with open(path, encoding="utf-8") as fh:
            cfg = yaml.load(fh)
    except Exception:
        return out
    if not isinstance(cfg, dict):
        return out
    m = cfg.get("model")
    if not isinstance(m, dict):
        return out
    out["provider"] = str(m.get("provider", "") or "")
    out["default"] = str(m.get("default", "") or "")
    out["base_url"] = str(m.get("base_url", "") or "")
    return out


def _backup_config(label: str = "nous_switcher") -> Path | None:
    """Snapshot config.yaml next to itself, mirroring Hermes's backup pattern.

    Best-effort: never raises. Returns the backup path on success, ``None`` on
    failure. The backup is only created if config.yaml actually exists.
    """
    path = _config_path()
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak.{label}_{ts}")
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError:
        return None


def set_default_model(
    model_id: str,
    *,
    provider: str = "nous",
    base_url: str = "",
    create_backup: bool = True,
) -> dict[str, Any]:
    """Set ``model.default`` (and optionally ``provider`` / ``base_url``) in config.yaml.

    Round-trip safe: preserves comments and order in the rest of the file.
    Atomic: writes to ``.tmp`` then ``os.replace`` so a crash mid-write
    never leaves a half-written config.

    Returns::

        {
            "success": bool,
            "previous": {"provider": str, "default": str, "base_url": str},
            "current":  {"provider": str, "default": str, "base_url": str},
            "backup":   str | None,   # backup path
        }
    """
    if not model_id or not model_id.strip():
        return {
            "success": False,
            "error": "model_id is required",
            "previous": read_current_model(),
            "current": read_current_model(),
            "backup": None,
        }

    path = _config_path()
    if not path.exists():
        return {
            "success": False,
            "error": f"config.yaml not found at {path}",
            "previous": read_current_model(),
            "current": read_current_model(),
            "backup": None,
        }

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        with open(path, encoding="utf-8") as fh:
            cfg = yaml.load(fh)
    except Exception as exc:
        return {
            "success": False,
            "error": f"failed to read config.yaml: {exc}",
            "previous": read_current_model(),
            "current": read_current_model(),
            "backup": None,
        }

    if not isinstance(cfg, dict):
        return {
            "success": False,
            "error": "config.yaml top-level is not a mapping",
            "previous": read_current_model(),
            "current": read_current_model(),
            "backup": None,
        }

    previous = {
        "provider": str((cfg.get("model") or {}).get("provider", "") or ""),
        "default": str((cfg.get("model") or {}).get("default", "") or ""),
        "base_url": str((cfg.get("model") or {}).get("base_url", "") or ""),
    }

    # Ensure the model block exists and is a CommentedMap (ruamel round-trip).
    from ruamel.yaml.comments import CommentedMap

    model_block = cfg.get("model")
    if not isinstance(model_block, CommentedMap):
        new_block = CommentedMap()
        # Preserve the existing dict's contents if any.
        if isinstance(model_block, dict):
            for k, v in model_block.items():
                new_block[k] = v
        cfg["model"] = new_block
        model_block = new_block

    model_block["provider"] = provider
    model_block["default"] = model_id.strip()
    if base_url:
        model_block["base_url"] = base_url
    elif "base_url" in model_block and not model_block["base_url"]:
        # Keep an empty base_url explicit so the field stays present in YAML.
        model_block["base_url"] = ""

    backup = _backup_config() if create_backup else None

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh)
        os.replace(tmp, path)
    except OSError as exc:
        return {
            "success": False,
            "error": f"failed to write config.yaml: {exc}",
            "previous": previous,
            "current": read_current_model(),
            "backup": str(backup) if backup else None,
        }

    current = {
        "provider": provider,
        "default": model_id.strip(),
        "base_url": base_url,
    }
    return {
        "success": True,
        "previous": previous,
        "current": current,
        "backup": str(backup) if backup else None,
    }


if __name__ == "__main__":
    # Quick CLI sanity-check: ``python3 config_writer.py`` reads current model.
    import json as _json
    print("Current model block:")
    print(_json.dumps(read_current_model(), indent=2))
