"""
server.py — Nous Switcher (V0)

A tiny local web app that lets you browse the full Nous Portal model catalog
and click one to set it as the default for new Hermes sessions.

Runs on http://127.0.0.1:9120 (localhost only — never binds to a public
interface). The companion UI lives in ``static/index.html``.

Endpoints
---------
  GET  /                  → static/index.html
  GET  /api/health        → {ok, version, source}
  GET  /api/catalog       → {models, fetched_at, source, count, warning?}
  GET  /api/catalog?refresh=true  → force live fetch
  GET  /api/current       → {provider, default, base_url, home}
  POST /api/set           → body {model_id, provider?, base_url?} → write config

This is V0 — set-as-default only. Hot-swap of the active session is a
deliberate V0.1 because it requires touching the running tui_gateway's
internal state (see spike report). V0.1 hooks can land here without
breaking V0.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import catalog
import config_writer
import hermes_catalog_overlay
import hermes_desktop_apply

VERSION = "0.1.5"
HOST = "127.0.0.1"
PORT = 9120
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "") or str(Path.home() / ".hermes")).expanduser()
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Nous Switcher",
    version=VERSION,
    description="Set the default Nous Portal model for new Hermes sessions.",
)

# CORS: localhost only. We bind to 127.0.0.1 so this is defense-in-depth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:9120",
        "http://127.0.0.1:9120",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models for request/response
# ---------------------------------------------------------------------------

class SetModelRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=512, description="Model id, e.g. 'google/gemini-3-pro-image'")
    provider: str = Field(default="nous", min_length=1, max_length=64)
    base_url: str = Field(default="", max_length=512)


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": VERSION,
        "host": HOST,
        "port": PORT,
        "hermes_home": str(HERMES_HOME),
        "config_path": str(HERMES_HOME / "config.yaml"),
        "cache_path": str(HERMES_HOME / "cache" / catalog.CACHE_FILENAME),
    }


@app.get("/api/catalog")
def get_catalog(refresh: bool = Query(default=False, description="Force a live re-fetch from Nous Portal")) -> dict[str, Any]:
    out = catalog.fetch_catalog(force_refresh=refresh)
    # Trim the per-model ``_raw`` payload before sending to the UI — it's big
    # and the UI doesn't need it. Keep ``count``/``source``/``fetched_at`` for
    # the header strip in the UI.
    models = []
    for m in out.get("models", []):
        models.append({k: v for k, v in m.items() if k != "_raw"})
    out["models"] = models
    return out


@app.get("/api/current")
def get_current() -> dict[str, Any]:
    cur = config_writer.read_current_model()
    return {
        **cur,
        "home": str(HERMES_HOME),
        "config_path": str(HERMES_HOME / "config.yaml"),
    }


@app.post("/api/set")
def post_set(body: SetModelRequest) -> JSONResponse:
    # Defense in depth — strip whitespace, refuse obvious junk.
    model_id = body.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")
    if any(c in model_id for c in ("\n", "\r", "\t")):
        raise HTTPException(status_code=400, detail="model_id contains invalid characters")

    provider = body.provider.strip() or "nous"
    result = config_writer.set_default_model(
        model_id=model_id,
        provider=provider,
        base_url=body.base_url.strip(),
    )
    if not result.get("success"):
        return JSONResponse(status_code=500, content=result)

    # If this is a Nous model, make it visible to Hermes' own Settings/model
    # picker too. Hermes intentionally uses a curated catalog for /api/model/options
    # rather than the full /v1/models list; without this overlay a valid full-
    # catalog selection can render as an empty dropdown in Settings.
    overlay_result: dict[str, Any] | None = None
    if provider.strip().lower() == "nous":
        overlay_result = hermes_catalog_overlay.ensure_nous_model_visible(model_id)
        if not overlay_result.get("ok"):
            result["warning"] = f"model default was written, but catalog overlay failed: {overlay_result.get('error', 'unknown error')}"
        result["catalog_overlay"] = overlay_result

    # Match Hermes Settings → Apply: call the live Desktop dashboard backend's
    # model assignment endpoint when it is running. This updates backend model
    # info/options. Do NOT launch a second Hermes binary with a hermes:// deep
    # link here: on KDE/Electron that helper process can exit via SIGTRAP and
    # trigger a scary crash reporter dialog even though the main app is fine.
    # The local Hermes Desktop patch now makes fresh new-chat drafts force-reseed
    # from this global default, so backend Apply is the only live sync needed.
    desktop_apply = hermes_desktop_apply.apply_main_model(provider=provider, model=model_id)
    result["desktop_apply"] = desktop_apply
    result["renderer_sync"] = {"ok": True, "method": "fresh-draft-default-reseed", "skipped_deeplink": True}
    if not desktop_apply.get("ok"):
        prior_warning = result.get("warning")
        apply_warning = f"Hermes Desktop apply was not completed automatically: {desktop_apply.get('error', 'unknown error')}"
        result["warning"] = f"{prior_warning}; {apply_warning}" if prior_warning else apply_warning

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Routes — static UI
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Mount /static for the assets dir.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    import uvicorn
    print(f"nous_switcher v{VERSION}  →  http://{HOST}:{PORT}")
    print(f"  HERMES_HOME : {HERMES_HOME}")
    print(f"  config.yaml : {HERMES_HOME / 'config.yaml'}")
    print(f"  catalog src : {catalog.NOUS_MODELS_URL}")
    print()
    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        # access_log=False keeps the terminal quiet; set True to debug.
        access_log=False,
    )


if __name__ == "__main__":
    main()
