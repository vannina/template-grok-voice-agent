# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Demo of a realtime voice agent ("Margot", hôtesse of *Le Petit Bistro*, a French restaurant in Paris) built on xAI's **`grok-voice-think-fast-1.0`** model. A FastAPI server mints ephemeral xAI tokens and serves a static frontend; the browser opens a WebSocket directly to `wss://api.x.ai/v1/realtime` and streams PCM16 audio at 24 kHz both ways. The agent can call tools — a Composio-backed Google Calendar booking flow, a calendar availability MCP, an hours lookup, and an `end_call` hang-up.

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
   - `POST /api/calendar/book` — builds the Google Calendar event payload server-side and POSTs to Composio's REST API (`backend.composio.dev/.../GOOGLECALENDAR_CREATE_EVENT`). The model never sees raw calendar fields — Grok hallucinated `workingLocationProperties` when given the full schema. Errors are returned as `{"status":"error", ...}` with HTTP 200 on purpose, so the voice agent can react verbally instead of seeing a fetch failure.
   - `GET /` — injects a `?v=<mtime>` cache-buster on the `voice.js` script tag so browsers can't serve a stale module during dev.
   - `POST /twilio/voice` — TwiML webhook. Returns `<Connect><Stream url="wss://<host>/twilio/stream"/></Connect>`. The `<host>` is read from the `Host` request header, so the Nginx vhost must `proxy_set_header Host $host;` for the wss URL to be correct behind the reverse proxy.
   - `WS /twilio/stream` — bridges a Twilio Media Stream to an xAI realtime WS. Both sides exchange µ-law 8 kHz base64 audio, so we just unwrap/rewrap the JSON envelope (no transcoding). The session is configured with `audio.input.format = audio.output.format = "audio/pcmu"` and an explicit greeting `response.create` so the caller doesn't pick up to silence. Tool calls (`book_reservation`, `get_restaurant_hours`, `end_call`) are dispatched server-side through `_server_tool_call`. `end_call` defers the actual hang-up until `response.done`, then calls Twilio's REST API (`Status=completed`) to drop the PSTN leg — just closing the WS isn't enough, the call would stay open with silence.
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
   - `web/config/system_prompt.txt` — persona and rules.
   - `web/config/tools.json` — tool definitions sent to xAI. Mix of xAI built-ins (`web_search`, `mcp`) and `function` tools.
   - For each `function` tool you add to `tools.json`, you **must** add a handler in **two places** — keep them in sync: (a) the `FUNCTIONS` object in `web/static/voice.js` for the browser path, and (b) `_server_tool_call` in `web/server.py` for the Twilio path. The browser handler can fetch a server endpoint; the server handler must do the work inline.

## Sample rate

24 kHz everywhere: `SAMPLE_RATE = 24000` in `voice.js`, declared on `getUserMedia`, `AudioContext`, and the `session.update.audio.{input,output}.format.rate`. Mismatched rates produce choppy/sped-up audio — keep all three in lockstep when changing it.

## Calendar config

The active booking path is Composio, not direct Google OAuth. Defaults in `server.py`: `calendar_id="primary"`, `timezone="Europe/Paris"`, duration 1h30. `web/google_calendar.py` and `setup_google.py` are legacy direct-OAuth code paths kept for reference; they are **not** wired into the running app.

## Deployment (Docker + Nginx)

`Dockerfile` builds a python:3.12-slim image with the app. `docker-compose.yml` runs the container bound only to `127.0.0.1:8001` — Nginx (on the host) reverse-proxies the public domain to it. `deploy/nginx.conf.example` is a ready-to-edit vhost with the WebSocket `Upgrade` headers and `proxy_set_header Host $host;` (the latter is *required* — `/twilio/voice` reads the Host header to build the `wss://` URL it returns to Twilio). TLS is via `certbot --nginx`. The `web/config` dir is bind-mounted read-only into the container so prompt/tools edits don't need a rebuild.

## Secrets / files not in git

`.env` holds `XAI_API_KEY`, `COMPOSIO_API_KEY`, `COMPOSIO_MCP_URL`, and (for the phone path) `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`. `web/config/google_oauth_client.json` and `web/config/google_token.json` are gitignored (only relevant if you reactivate the legacy `google_calendar.py` path).
