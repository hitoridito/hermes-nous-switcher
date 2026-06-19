# Changelog

## 0.1.11 — Nous credits card

- Adds `GET /api/credits`, a read-only endpoint that reuses Hermes Agent's own Nous Portal auth/account helpers.
- Adds a small UI credits card showing sanitized balance lines and a Portal/top-up link.
- Keeps OAuth tokens and raw account payloads server-side only; the browser receives no secrets.
- Fails soft when Hermes Agent source/auth is unavailable.

## 0.1.10 — official links

- Adds tasteful official links to Hermes Agent, Hermes Agent docs, and Nous Research.
- Adds a non-affiliation note so the project does not overclaim endorsement.

## 0.1.9 — first-contact model provenance

- Adds a README first-contact install note naming the installing model: Hermes Desktop Windows with Minimax M3 (Medium).
- Clarifies that first-contact install notes are provenance for the agent-native install path, not benchmark claims.

## 0.1.8 — Windows first-contact notes

- Documents the successful Windows/MINGW64 first-contact install path.
- Notes that Hermes Desktop on Windows may use `%LOCALAPPDATA%\hermes` as active home while `~/.hermes` is stale.
- Documents that new sessions use the selected default after Settings → Apply on Windows, while an existing chat's model pill can visually mislead.

## 0.1.7 — read-only first-contact install

- Tightens the Hermes-native onboarding prompt: initial install verification must not call `POST /api/set` or modify the user's Hermes config.
- Updates the public skill verification checklist to use read-only endpoints first (`/api/health`, `/api/current`, `/api/catalog`).
- Requires explicit user model choice/permission before writing config during setup.

## 0.1.6 — platform-aware onboarding

- Updates the Hermes-native install prompt to require OS/shell/Python/Hermes-path detection before acting.
- Documents Linux as the primary tested path and macOS/Windows as alpha/best-effort for the local app.
- Adds a Windows PowerShell launcher (`start.ps1`).
- Makes Linux Desktop Apply discovery fail soft on systems without `/proc` instead of crashing.

## 0.1.5 — public-alpha cleanup

- Removes the experimental `hermes://model/current` deep-link launch path from Nous Switcher. On KDE/Electron it could trigger a scary crash reporter dialog from the short-lived helper process even when the main Hermes app was fine.
- Keeps the reliable layers: config write, catalog overlay, and live Hermes Desktop backend Apply endpoint.
- Adds UI sorting: catalog order, cheapest input, cheapest output, largest context, and name.
- Updates copy/README for public-alpha sharing.

## 0.1.4 — deep-link transport attempt

- Switched from `xdg-open hermes://...` to launching the Hermes Desktop binary directly to avoid KDE/KIO protocol errors.
- Later removed from the switcher after discovering the helper process could exit via SIGTRAP on this stack.

## 0.1.3 — renderer state investigation

- Added an experimental Hermes Desktop deep-link handler for syncing sticky composer model state.
- Identified that new chat creation could use sticky renderer composer state instead of global default.

## 0.1.2 — backend Apply

- Added live Hermes Desktop backend Apply via `POST /api/model/set` with the local per-session dashboard token.
- This mirrors Settings → Apply for backend default state.

## 0.1.1 — catalog overlay

- Added local Nous catalog overlay so selected full-catalog models appear in Hermes Settings/model picker.

## 0.1.0 — initial local switcher

- Localhost FastAPI app.
- Fetch/search/filter Nous `/v1/models` catalog.
- Write selected model to Hermes `config.yaml`.
