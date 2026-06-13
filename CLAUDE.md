# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Demo of a realtime voice agent ("Margot", hôtesse of *Le Petit Bistro*, a French restaurant in Paris) built on xAI's **`grok-voice-think-fast-1.0`** model. A FastAPI server mints ephemeral xAI tokens and serves a static frontend; the browser opens a WebSocket directly to `wss://api.x.ai/v1/realtime` and streams PCM16 audio at 24 kHz both ways. The same server also relays Twilio Media Streams to xAI for the phone path. The agent can call tools — a Composio-backed Google Calendar booking flow, a calendar availability MCP, an hours lookup, and an `end_call` hang-up.

The README is in French; user-facing copy (system prompt, UI) is French by default.

## Common commands

Activate the venv first (`.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate` on Mac/Linux), then:

```
pip install -r requirements.txt                # install deps
uvicorn web.server:app --port 8000 --reload    # run dev server
```

App: `http://localhost:8000` · Embedded guide: `http://localhost:8000/guide.html`.

There is no test suite, no linter config, and no build step.

## Architecture

The app has **two entry points** sharing the same agent config:

- **Browser path** — the realtime audio goes browser ↔ xAI directly; the Python server only mints tokens and serves the SPA.
- **Phone path (Twilio Media Streams)** — Twilio opens a WebSocket to *our* server; the server proxies audio to xAI and runs the tool calls itself, because the browser is out of the loop.

1. **FastAPI server (`web/server.py`)** — control plane + Twilio relay. Endpoints:
   - `POST /token` — calls xAI `/v1/realtime/client_secrets` with the server-side `XAI_API_KEY` and returns a 5-minute ephemeral secret. The real API key never reaches the browser.
   - `GET /config` — reads `web/config/system_prompt.txt` and `web/config/tools.json` **fresh from disk on every request**, so editing those files takes effect on the next conversation with no restart. `tools.json` may contain `${ENV_VAR}` placeholders (e.g. `${COMPOSIO_API_KEY}`, `${COMPOSIO_MCP_URL}`) — they're expanded with `string.Template.safe_substitute(os.environ)` so secrets stay out of the file but still reach xAI via `session.update`. Don't switch to `os.path.expandvars` on Windows — shell-quote semantics silently kill expansion after a stray apostrophe.
   - `POST /api/calendar/book` — builds the Google Calendar event payload server-side and POSTs to Composio's REST API (`backend.composio.dev/.../GOOGLECALENDAR_CREATE_EVENT`). The model never sees raw calendar fields — Grok hallucinated `workingLocationProperties` when given the full schema. Errors are returned as `{"status":"error", ...}` with HTTP 200 on purpose, so the voice agent can react verbally instead of seeing a fetch failure. Also rejects placeholder phones (`anonymous`/`restricted`/`unavailable`/`unknown`/`private`/`none`/`n/a`) with an `INVALID_PHONE` status — required because Twilio sends the literal string `"anonymous"` as `From=` when the caller's CallerID is masked, and Grok will obediently store that as the phone field unless we push back.
   - `GET /` — injects a `?v=<mtime>` cache-buster on the `voice.js` script tag so browsers can't serve a stale module during dev.
   - `POST /twilio/voice` — TwiML webhook. Returns `<Connect><Stream url="wss://<host>/twilio/stream"><Parameter name="from" value="<From>"/></Stream></Connect>`. Reads the caller's number from the form body (`From=...`) and forwards it as a Stream custom Parameter so the WS handler can inject it into the system prompt. Reads the host from the `Host` header, so the reverse proxy must preserve it. Parsing the form body requires `python-multipart` — Starlette asserts the dependency before `request.form()` will run.
   - `WS /twilio/stream` — bridges a Twilio Media Stream to an xAI realtime WS. Both sides exchange µ-law 8 kHz base64 audio, so we just unwrap/rewrap the JSON envelope (no transcoding). Behavior:
     - The `session.update` is **deferred until the Twilio `start` event arrives**, because that's when we learn the caller phone from `customParameters.from`. If the caller phone is one of the masked sentinels (`anonymous`/`restricted`/`unavailable`/...), the instructions are augmented with a "numéro MASQUÉ, demande-le explicitement" block instead of "use this CallerID". If it's a real number, the model is told it can default to it.
     - Audio formats are pinned to `audio/pcmu` (Twilio's native µ-law 8 kHz), Whisper input transcription is pinned to `language: "fr"` so it doesn't fall back to Hindi/Portuguese on ambiguous speech.
     - After `session.update`, an explicit `response.create` triggers an opening greeting so the caller doesn't pick up to silence.
     - Tool calls (`book_reservation`, `get_restaurant_hours`, `end_call`) are dispatched server-side through `_server_tool_call`.
     - **Auto-hangup safety net**: Grok-voice often speaks the goodbye ("Au revoir, bonne soirée !") but skips emitting `end_call`. The transcript-done handler scans for goodbye phrases (`au revoir`, `bonne soirée`, `à très vite`, etc.) and sets `pending_end_call = True` itself, so the existing `response.done` handler hangs up via Twilio's REST API (`Status=completed`) — just closing the WS isn't enough, the PSTN leg would stay open with silence.
   - A `no_cache` middleware sets `Cache-Control: no-store` on every response.
   - Everything else is mounted from `web/static/` (static SPA).

2. **Browser client (`web/static/voice.js`)** — runs the realtime session. On Start:
   - Concurrently requests mic, fetches `/token`, fetches `/config`.
   - Opens `wss://api.x.ai/v1/realtime?model=...` using the WebSocket subprotocol `xai-client-secret.<secret>` for auth.
   - Sends a `session.update` with `voice="69smp8rm"` (Composio voice library id, French speaker), the loaded instructions/tools, `server_vad` turn detection, and `whisper-1` input transcription.
   - Captures mic via `ScriptProcessorNode` (4096 samples), encodes Float32→PCM16→base64, sends as `input_audio_buffer.append`. Frames captured before the WS opens are buffered in `earlyBuffer` and flushed on `onopen`.
   - Plays assistant audio with a manual `playhead` cursor that schedules `AudioBufferSourceNode`s back-to-back to avoid gaps.
   - Handles function tool calls: on `response.function_call_arguments.done` it looks up the tool name in the `FUNCTIONS` map, runs it, then sends `conversation.item.create` (function_call_output) + `response.create` to let the agent continue.
   - `end_call` is deferred: it sets a `pendingEndCall` flag and only actually disconnects on `response.done`, after draining the queued audio (`playhead - audioCtx.currentTime + 400 ms` margin), so Margot's "au revoir" isn't cut off mid-word.

3. **Agent configuration (hot-reloaded)**:
   - `web/config/system_prompt.txt` — persona and rules. Structured along the [OpenAI Realtime Prompting Guide](https://developers.openai.com/cookbook/examples/realtime_prompting_guide) 8-section pattern: `Role`, `Personality & Tone`, `Unclear audio`, `Tools`, `Rules`, `Conversation Flow` (Greeting / Collect / Check / Book / Goodbye states with sample phrases + "Exit when"), `Safety & Escalation`, `Context`. Two rules are flagged ABSOLUTES and load-bearing: R1 "never lie about a reservation" (forces tool use before any confirmation phrase), R2 "tirer sur la gâchette" (force `book_reservation` once the 5 fields are collected). Don't drop these in a "cleanup" pass.
   - `web/config/tools.json` — tool definitions sent to xAI. Mix of xAI built-ins (`web_search`, `mcp`) and `function` tools.
   - For each `function` tool you add to `tools.json`, you **must** add a handler in **two places** — keep them in sync: (a) the `FUNCTIONS` object in `web/static/voice.js` for the browser path, and (b) `_server_tool_call` in `web/server.py` for the Twilio path. The browser handler can fetch a server endpoint; the server handler must do the work inline.

## Multi-métier (socle « un agent par métier ») — depuis 2026-06-13

Une **seule** app sert plusieurs métiers (restaurant, hôtel, médical, immobilier,
artisan, coach, beauté). Le métier est résolu **par requête** depuis le Host :

- `demo-<metier>.corsica-studio.com` → `<metier>` ; `demo.corsica-studio.com`,
  `localhost`, IP → `DEFAULT_METIER` (env `METIER`, défaut `restaurant`).
  Override de test local : `?metier=<slug>`. Voir `_resolve_metier()` dans `server.py`.
- Tout ce qui varie vit dans **`web/config/metiers/<metier>/`** :
  `system_prompt.txt` + `tools.json` + `business.json` + `profile.json`.
  Si le dossier n'existe pas, fallback sur `web/config/*` (rétro-compat ; c'est
  pourquoi la prod restaurant n'a pas bougé). `web/config/metiers/restaurant/` est
  le **gabarit de référence** à dupliquer.
- `profile.json` = libellés UI + SEO + paramètres d'agenda. **Aucun secret.** Champs :
  `agent`, `agent_initial`, `agent_role`, `secteur`, `objet`, `cta_label`, `hero_*`,
  `home_*`, `call_header`, `chip_1..3`, `showcase_title/sub`, `showcase_kind`
  (`menu` = rendu carte resto ; `fiche` = rendu générique depuis `business.json.showcase`),
  `card1_title/bullets`, `conversion_*`, `mailto_subject`, `bubbles{}` (gabarits avec
  `{agent}{date}{time}{name}{party}{free}`), `recap_*`, `event_summary_label`,
  `calendar_note`, `calendar_id` (vide → `RESTAURANT_CALENDAR_ID`), `capacity_per_slot`,
  `slot_duration_min`, `greeting_instruction`. Valeurs par défaut = restaurant dans
  `_PROFILE_DEFAULTS` (server.py) → la page s'affiche correctement même sans profil.
- Le serveur injecte le profil dans `index.html` de deux façons : remplacement des
  placeholders texte `{{CLE_MAJ}}` (clés du profil en MAJUSCULES) **et**
  `window.__PROFILE__` (objet complet lu par `voice.js`). Endpoints : `GET /config`,
  `GET /api/profile`, `GET /api/business` (+ alias `/api/restaurant`) — tous résolus
  par Host. Le chemin Twilio résout le métier via `ws.headers["host"]`.
- L'agenda est paramétré par métier (`_metier_ctx`) : `calendar_id`, `capacity`,
  `duration`, `summary_label`, `event_note`. Un calendrier Google partagé
  « Démo Agent Vocal » pour les 6 nouveaux métiers ; le restaurant garde « Resto ».
- Smoke test : `./.venv/bin/python _s1_test.py` (22 checks : rendu, fallback, merge profil).

## Sample rates (don't mix them)

- **Browser path** — 24 kHz everywhere: `SAMPLE_RATE = 24000` in `voice.js`, declared on `getUserMedia`, `AudioContext`, and `session.audio.{input,output}.format.rate`. Mismatched rates produce choppy/sped-up audio.
- **Twilio path** — 8 kHz µ-law, set via `audio.input.format = audio.output.format = "audio/pcmu"`. xAI accepts this natively, so no transcoding library (audioop / numpy resample) is needed.

## Calendar config

The active booking path is Composio, not direct Google OAuth. Defaults in `server.py`: `calendar_id="primary"`, `timezone="Europe/Paris"`, duration 1h30. `web/google_calendar.py` and `setup_google.py` are legacy direct-OAuth code paths kept for reference; they are **not** wired into the running app.

## Deployment

`Dockerfile` builds a python:3.12-slim image with the app. `docker-compose.yml` runs the container bound only to `127.0.0.1:8001` — a reverse proxy on the host fronts the public domain and terminates TLS. The `web/config` dir is bind-mounted read-only into the container so prompt/tools edits don't need a rebuild (Python source changes do).

The repo carries two reverse-proxy templates:

- **`deploy/nginx.conf.example`** — Nginx vhost with `proxy_set_header Host $host;` (required — `/twilio/voice` reads the Host header to build the `wss://` URL), the WebSocket `Upgrade` headers, and `proxy_request_buffering off`. TLS via `certbot --nginx`.
- **The current production VPS (`voiceagents.thomas-berton.com`)** actually runs **Caddy**, not Nginx. The block in `/etc/caddy/Caddyfile` is just:
  ```
  voiceagents.thomas-berton.com {
      reverse_proxy 127.0.0.1:8001 {
          header_up Host {host}
      }
  }
  ```
  Caddy auto-provisions Let's Encrypt and proxies WebSockets natively, no extra directives. `header_up Host {host}` is the Caddy equivalent of nginx's `proxy_set_header Host $host;` — needed so the TwiML URL builder sees the public hostname, not `127.0.0.1:8001`.

The repo is cloned at `/opt/margot-voice/`. Standard ops:

```
ssh root@<vps>
cd /opt/margot-voice
git pull
docker compose up -d --build       # rebuild only needed if Python source or requirements changed
docker logs -f margot-voice        # follow live logs
```

If the change is only in `web/config/*` (prompt, tools.json), the bind mount picks it up on the next conversation — no `docker compose` invocation needed.

## Logging conventions

Server prints tagged lines so `docker logs -f margot-voice` is the primary debug tool:

- `[twilio] ...` — Twilio WS lifecycle (connected, start with `from='...'`, stop, closed)
- `[caller] ...` — completed Whisper transcript of the caller
- `[margot] ...` — completed transcript of the assistant
- `[tool] → name(args)` / `[tool] ← name → result` — server-handled function tool calls
- `[xai] session.updated tools=[...]` — which tools xAI accepted in the session
- `[xai] response.mcp_call.in_progress / .completed ...` — MCP calls handled by xAI itself (not by us); useful to debug Composio failures
- `[xai] ERROR (...)` / anything with "error"/"fail" — surfaces any other anomaly

If you see no `[tool] → book_reservation` despite the caller having given all 5 fields, R2 of the prompt isn't being honoured — that's the symptom to look for. If you see Hindi/Devanagari in `[caller]` lines, the Whisper `language: "fr"` pin has been dropped from `session.update`.

## Twilio specifics

- Twilio webhook configuration: phone number → Voice → "A call comes in" → Webhook `https://<host>/twilio/voice` (POST). No TwiML Bin required — the server generates the TwiML dynamically and embeds the public host in the `wss://` URL.
- Twilio sends the caller phone as form-encoded `From=` in the webhook body. When the caller's number is hidden (e.g. iPhone "Hide my Caller ID", or a `#31#` prefix), Twilio sends the literal string `"anonymous"` (lowercase). The server treats this sentinel + a few related ones as "no CallerID" and adapts the prompt. Caller can override their hiding for one call by prefixing the dialled number with `3651` in France.
- `python-multipart` is required (in `requirements.txt`) for `request.form()` on the webhook. Don't drop it — Starlette asserts before parsing.
- Hangup needs the Twilio REST API (`TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`). Closing the WS alone leaves the PSTN leg open and the caller hears silence.

## Secrets / files not in git

`.env` holds `XAI_API_KEY`, `COMPOSIO_API_KEY`, `COMPOSIO_MCP_URL`, and (for the phone path) `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`. `web/config/google_oauth_client.json` and `web/config/google_token.json` are gitignored (only relevant if you reactivate the legacy `google_calendar.py` path). `.deploy_tmp/` is also gitignored — it holds throwaway SSH/SFTP helper scripts that embed the VPS password for the duration of a deployment session.
