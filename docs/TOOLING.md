# Tooling — AI dev helpers wired into this repo (2026-09-13)

Three helpers, none required to build or run the product.

| Tool | What | Where it lives | How to activate |
|---|---|---|---|
| **UI/UX Pro Max** | Design intelligence (styles, palettes, font pairs, design-system reasoning) | `.claude/skills/` (vendored by `npx ui-ux-pro-max-cli init --ai claude`) | Automatic in Claude Code / Cowork when working in this repo. Refresh: rerun the `npx` command. |
| **Ponytail** | "Lazy senior dev" rules + `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt` | Declared in `.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) | Claude Code offers to install it when it opens this repo. Global install on the Mac: `/plugin marketplace add DietrichGebert/ponytail` → `/plugin install ponytail@ponytail`. |
| **OmniRoute** | OpenAI-compatible LLM gateway (352+ providers, auto-fallback, token compression) | `docker-compose.yml` service `omniroute`, profile `gateway` (opt-in, never started by default) | `docker compose --profile gateway up -d omniroute` → dashboard http://localhost:20128, API `http://localhost:20128/v1`. Or on the Mac: `npm i -g omniroute && omniroute`. |

Global (user-level) install of UI/UX Pro Max in Claude Code on the Mac, if wanted outside this repo:
`/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill` → `/plugin install ui-ux-pro-max@ui-ux-pro-max-skill`.

OmniRoute is **not** wired into the backend yet. When it is, the only change is `OLLAMA_BASE_URL`-style config in
`backend/app/core/config.py` (an `LLM_BASE_URL` pointing at the gateway) — see `docs/BRAINSTORM-2026-09-13.md`.
