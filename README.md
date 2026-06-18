# Nous Switcher

A tiny local web app for browsing the Nous model catalog and setting the default model for new [Hermes Agent](https://github.com/NousResearch/hermes-agent) chats.

Built for our own Hermes setup first. Shared as an early alpha for other Hermes tinkerers who want a quick, local way to compare Nous models by price/context/capabilities and make one the default.

## Give this to your Hermes

Copy/paste this into a Hermes Agent session with terminal access:

```text
Please install and run the local Nous Switcher from https://github.com/hitoridito/hermes-nous-switcher.

Clone it into a sensible local tools directory, read README.md and skills/hermes-nous-switcher/SKILL.md first, then set it up safely for my Hermes profile. Keep it localhost-only. Do not print or store any tokens. Start the app and tell me the local URL. If my Hermes Desktop needs the fresh-new-chat default reseed patch for full no-Settings behavior, explain the caveat and ask before changing Desktop source.
```

If you prefer the Hermes CLI one-shot style:

```bash
hermes chat -q 'Please install and run the local Nous Switcher from https://github.com/hitoridito/hermes-nous-switcher. Clone it into a sensible local tools directory, read README.md and skills/hermes-nous-switcher/SKILL.md first, then set it up safely for my Hermes profile. Keep it localhost-only. Do not print or store any tokens. Start the app and tell me the local URL. If my Hermes Desktop needs the fresh-new-chat default reseed patch for full no-Settings behavior, explain the caveat and ask before changing Desktop source.'
```

![Nous Switcher screenshot](screenshots/nous-switcher.png)

## Status

**Alpha / local utility.** It works in our setup, but it is intentionally small and boring:

- localhost only
- no hosted service
- no auth proxy
- no active-chat hot swap
- no telemetry

It changes the default model for **new Hermes chats**. It does not switch the model inside an already-running conversation.

## What it does

- Fetches the live Nous/OpenRouter-compatible model catalog from `https://inference-api.nousresearch.com/v1/models`.
- Caches the catalog at `~/.hermes/cache/nous_full_catalog.json` for fast loads and offline fallback.
- Shows model name, id, context length, input/output pricing per million tokens, and capability badges.
- Supports search, filters (`Vision`, `Reasoning`, `Free`), and sorting (`cheapest input`, `cheapest output`, `largest context`, `name`).
- Writes the selected model to `~/.hermes/config.yaml` as:

  ```yaml
  model:
    provider: nous
    default: <model-id>
  ```

- Writes a local Hermes model-catalog overlay so full-catalog Nous models can appear correctly in Hermes Settings/model picker even when they are outside Hermes' curated list.
- Calls the live Hermes Desktop backend's `POST /api/model/set` endpoint when Desktop is running, matching what Settings → Apply does.

## Important Hermes Desktop note

Hermes Desktop has had a sticky composer/new-chat model state that can override `config.yaml`. In our setup, fully removing the manual Settings → Apply step required a tiny Hermes Desktop patch: fresh new-chat drafts force-reseed from the global default (`refreshCurrentModel(true)`).

Without that patch, this tool can still update `config.yaml`, the catalog overlay, and the live backend default, but your Desktop UI may continue to use its previous composer model until you open Settings and click Apply.

See `skills/hermes-nous-switcher/SKILL.md` for the agent-readable explanation and caveats.

## Run locally

From this directory:

```bash
./start.sh
```

Then open:

```text
http://127.0.0.1:9120
```

The launcher tries to reuse Hermes' own venv:

```text
~/.hermes/hermes-agent/venv/bin/python3
```

If that does not exist, create your own venv and install:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install fastapi uvicorn ruamel.yaml
python server.py
```

## Files

```text
nous_switcher/
├── server.py                   FastAPI app (localhost:9120)
├── catalog.py                  Nous /v1/models fetcher + disk cache
├── config_writer.py            Round-trip-safe config.yaml writer
├── hermes_catalog_overlay.py   Local catalog overlay writer
├── hermes_desktop_apply.py     Live Hermes Desktop Apply endpoint caller
├── static/index.html           Single-file vanilla JS UI
├── skills/hermes-nous-switcher/SKILL.md
├── start.sh
└── README.md
```

## API

| Method | Path                         | Purpose |
|---:|---|---|
| `GET` | `/api/health` | version, paths, sanity check |
| `GET` | `/api/catalog` | cached/full model catalog |
| `GET` | `/api/catalog?refresh=true` | force live re-fetch |
| `GET` | `/api/current` | current Hermes `model:` config block |
| `POST` | `/api/set` | set default model; body: `{ "model_id": "...", "provider": "nous" }` |

## Safety / privacy

- Server binds only to `127.0.0.1`.
- CORS only allows localhost origins.
- No API keys are needed to fetch the public catalog.
- Config writes are atomic (`config.yaml.tmp` then `os.replace`).
- Each successful config write creates a timestamped backup next to `config.yaml`.
- The live Desktop Apply helper reads the ephemeral dashboard session token from the same-user local Hermes Desktop process and sends it only to the loopback dashboard endpoint. It is not logged, persisted, or returned by the API.

## Known caveats

- This is Linux/Hermes Desktop focused because that is what we use.
- Full no-Settings behavior currently depends on the Hermes Desktop fresh-new-chat default reseed patch described above.
- Active-session hot swap is deliberately out of scope. Mid-conversation model switching has prompt-cache/cost implications and should use Hermes' own session/gateway model-switch path when exposed cleanly.
- The model catalog is whatever Nous' public `/v1/models` endpoint returns at runtime.

## Why share it?

Because it became useful in our own Hermes house, and maybe it helps another Hermes user tinker a little faster too.

Not a product launch. Just a small "hei, vi er også her" from our corner of the workshop.
