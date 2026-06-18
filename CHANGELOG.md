# Changelog

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
