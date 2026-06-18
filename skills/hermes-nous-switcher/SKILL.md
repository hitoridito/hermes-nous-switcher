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

6. If Hermes Desktop is running, call its live Apply endpoint, matching Settings → Apply:

   ```http
   POST http://127.0.0.1:<dashboard-port>/api/model/set
   X-Hermes-Session-Token: <ephemeral local token>
   Content-Type: application/json

   {"scope":"main","provider":"nous","model":"<model-id>"}
   ```

   Discover the dashboard port from the local dashboard process and read `HERMES_DASHBOARD_SESSION_TOKEN` from that same-user process environment. Do not print, store, or return the token.

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

- Bind server to `127.0.0.1` only.
- Restrict CORS to localhost.
- Do not require API keys for public catalog fetches.
- Write config atomically and create backups.
- Never log dashboard session tokens.
- Keep active-session hot-swap out of scope unless Hermes exposes a stable session model-switch API.

## Verification

- `python3 -m py_compile *.py`
- `GET /api/health` returns current version.
- `GET /api/catalog` returns models.
- `POST /api/set` returns `success: true`.
- Hermes `config.yaml` contains the selected model.
- Hermes Desktop `/api/model/info` reports the selected provider/model after Apply.
- Creating a fresh Hermes chat uses the selected default, if the Desktop fresh-draft reseed patch is present.
