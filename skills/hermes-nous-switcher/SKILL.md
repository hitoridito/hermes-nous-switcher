---
name: hermes-nous-switcher
description: Build or adapt a local Hermes companion app that browses Nous models and sets the default model for new Hermes chats, including catalog overlays and Desktop Apply caveats.
version: 0.1.0
author: Hitori Hermes
license: MIT
metadata:
  hermes:
    tags: [hermes, nous, models, desktop, catalog, local-tool]
    related_skills: [hermes-agent]
---

# Hermes Nous Switcher

Use this skill when you want a small local Hermes companion app that:

- fetches the Nous model catalog,
- lets a user search/filter/sort models,
- writes the selected model as Hermes' default for new chats,
- makes full-catalog Nous models visible in Hermes Settings,
- and avoids the common Desktop state pitfalls.

## First: Detect Platform

Before installing or modifying anything, detect and report:

- OS and shell (Linux/macOS/Windows, bash/zsh/PowerShell/etc.)
- Python command and version
- Git availability
- Hermes install path and active Hermes home/profile
- whether Hermes Desktop is running
- whether `/proc` exists (needed by the current Linux Desktop Apply discovery path)

Windows note: Hermes Desktop can use `%LOCALAPPDATA%\hermes` as its active home/config path when that directory exists. Do not assume `~/.hermes` is active; it may exist as a stale/legacy config. Prefer the path Hermes Desktop itself resolves.

If the platform is not Linux-like or the Hermes install layout is unknown, do not force Linux paths. Set up only the safe local web app pieces, explain what is unsupported, and ask before changing Hermes Desktop source.

## Core Pattern

1. Fetch the public Nous/OpenRouter-compatible model catalog:

   ```text
   https://inference-api.nousresearch.com/v1/models
   ```

2. Normalize useful display fields:

   - `id`
   - `name`
   - `context_length`
   - prompt/completion pricing converted to dollars per million tokens
   - input/output modalities
   - vision/reasoning/free flags

3. Cache the catalog under Hermes home:

   ```text
   ~/.hermes/cache/nous_full_catalog.json
   ```

4. On selection, write Hermes config using a round-trip YAML writer:

   ```yaml
   model:
     provider: nous
     default: <model-id>
   ```

5. Write a local model-catalog overlay and point Hermes at it:

   ```yaml
   model_catalog:
     providers:
       nous:
         url: file:///home/<user>/.hermes/cache/nous_switcher_model_catalog.json
   ```

   Put the selected model first in the overlay so picker payload caps do not hide it.

6. On Linux-like systems, if Hermes Desktop is running, call its live Apply endpoint, matching Settings → Apply:

   ```http
   POST http://127.0.0.1:<dashboard-port>/api/model/set
   X-Hermes-Session-Token: <ephemeral local token>
   Content-Type: application/json

   {"scope":"main","provider":"nous","model":"<model-id>"}
   ```

   The current helper discovers the dashboard port from the local dashboard process via `/proc` and reads `HERMES_DASHBOARD_SESSION_TOKEN` from that same-user process environment. Do not print, store, or return the token.

   On macOS/Windows, or any system without `/proc`, treat this step as unsupported/best-effort for now: skip live Apply, keep config/catalog writes, and explain that the user may need Hermes Settings → Apply until a native dashboard discovery path exists.

## Initial Install Verification Must Be Read-Only

When installing this for a user, do not probe `POST /api/set` just to prove writes work. That changes the user's real Hermes default, even if you restore it afterward.

Initial setup verification should use only:

- `GET /api/health`
- `GET /api/current`
- `GET /api/catalog` or `GET /api/catalog?refresh=true`
- OS-level bind checks such as `netstat`/`ss` showing `127.0.0.1:<port>` only

Only call `POST /api/set` after the user explicitly chooses a model or explicitly asks to test model-setting behavior.

## Windows First-Contact Result

A Windows/MINGW64 first-contact install confirmed:

- The repo can be cloned and run from a fresh Hermes session.
- A local `.venv` works well when Hermes' bundled venv layout varies.
- `HERMES_HOME` should be pointed at the active Desktop home, e.g. `%LOCALAPPDATA%\hermes`, not blindly at `~/.hermes`.
- Because live Desktop Apply is Linux-focused, the user may need to open Hermes Settings → Apply after selecting a model.
- New Hermes sessions then use the selected default.

Possible Windows UI quirk: after Settings → Apply, the model pill/current-chat display may appear to change for an already-running chat. Verify by switching away and back; the ongoing session can still retain its original model while new sessions use the new default.

## Desktop New-Chat Caveat

Hermes Desktop can have sticky renderer composer state (`$currentModel` / `$currentProvider`) that affects new chat creation. In that case, writing `config.yaml` and calling backend Apply may still not change the next chat until Settings → Apply updates the renderer state.

A robust local Hermes Desktop patch is to force fresh new-chat drafts to reseed from the global default. In `apps/desktop/src/app/desktop-controller.tsx`, find the effect for:

```ts
gatewayState === 'open' && !activeSessionId && freshDraftReady
```

and change:

```ts
refreshCurrentModel()
```

into:

```ts
refreshCurrentModel(true)
```

This makes “set default” mean “the next new chat starts with that default.”

## Avoid This Trap

Do not rely on launching a second Hermes Desktop binary with a `hermes://model/current?...` URL as your main sync path on Linux/KDE/Electron. It can avoid KIO in one configuration but still create a short-lived helper process that exits via `SIGTRAP`, causing a desktop crash reporter dialog even though the main Hermes app is fine.

Prefer:

- config write,
- catalog overlay,
- backend `/api/model/set`,
- and the fresh-new-chat default reseed behavior in Hermes Desktop.

## Public Alpha UI Shape

A good minimal UI has:

- current default strip,
- search by name/id,
- filters for vision/reasoning/free,
- sorting by price/context/name,
- model rows with id/context/pricing/capability badges,
- clear copy that says “default for new chats,” not “active chat switched.”

## Safety Checklist

- Detect OS/shell/Python/Hermes home before assuming paths.
- Bind server to `127.0.0.1` only.
- Restrict CORS to localhost.
- Do not require API keys for public catalog fetches.
- Write config atomically and create backups.
- Never log dashboard session tokens.
- Do not call `POST /api/set` during initial installation; wait for explicit model choice/permission.
- On non-Linux systems, skip `/proc`-based Desktop Apply and report the limitation clearly.
- Keep active-session hot-swap out of scope unless Hermes exposes a stable session model-switch API.

## Verification

- `python3 -m py_compile *.py`
- `GET /api/health` returns current version.
- `GET /api/catalog` returns models.
- `GET /api/current` reports the existing Hermes default without modifying it.
- The server is bound to loopback only.
- Do not call `POST /api/set` unless the user explicitly chooses a model or asks to test writes.
- After an explicit model choice, Hermes `config.yaml` contains the selected model.
- Hermes Desktop `/api/model/info` reports the selected provider/model after Apply where supported.
- Creating a fresh Hermes chat uses the selected default, if the Desktop fresh-draft reseed patch is present.
