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

Three layers; the realtime audio path does **not** go through the Python server.

1. **FastAPI server (`web/server.py`)** — minimal control plane. Endpoints:
   - `POST /token` — calls xAI `/v1/realtime/client_secrets` with the server-side `XAI_API_KEY` and returns a 5-minute ephemeral secret. The real API key never reaches the browser.
   - `GET /config` — reads `web/config/system_prompt.txt` and `web/config/tools.json` **fresh from disk on every request**, so editing those files takes effect on the next conversation with no restart. `tools.json` may contain `${ENV_VAR}` placeholders (e.g. `${COMPOSIO_API_KEY}`, `${COMPOSIO_MCP_URL}`) — they're expanded with `string.Template.safe_substitute(os.environ)` so secrets stay out of the file but still reach xAI via `session.update`. Don't switch to `os.path.expandvars` on Windows — shell-quote semantics silently kill expansion after a stray apostrophe.
   - `POST /api/calendar/book` — builds the Google Calendar event payload server-side and POSTs to Composio's REST API (`backend.composio.dev/.../GOOGLECALENDAR_CREATE_EVENT`). The model never sees raw calendar fields — Grok hallucinated `workingLocationProperties` when given the full schema. Errors are returned as `{"status":"error", ...}` with HTTP 200 on purpose, so the voice agent can react verbally instead of seeing a fetch failure.
   - `GET /` — injects a `?v=<mtime>` cache-buster on the `voice.js` script tag so browsers can't serve a stale module during dev.
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
   - For each `function` tool you add to `tools.json`, you **must** add a matching handler in the `FUNCTIONS` object in `web/static/voice.js`. The handler receives the parsed args and returns a JSON-serializable result. Server-side work (DB, external APIs) belongs behind a FastAPI endpoint that the handler fetches — see `book_reservation` → `/api/calendar/book` for the pattern.

## Sample rate

24 kHz everywhere: `SAMPLE_RATE = 24000` in `voice.js`, declared on `getUserMedia`, `AudioContext`, and the `session.update.audio.{input,output}.format.rate`. Mismatched rates produce choppy/sped-up audio — keep all three in lockstep when changing it.

## Calendar config

The active booking path is Composio, not direct Google OAuth. Defaults in `server.py`: `calendar_id="primary"`, `timezone="Europe/Paris"`, duration 1h30. `web/google_calendar.py` and `setup_google.py` are legacy direct-OAuth code paths kept for reference; they are **not** wired into the running app.

## Secrets / files not in git

`.env` holds `XAI_API_KEY`, `COMPOSIO_API_KEY`, and `COMPOSIO_MCP_URL`. `web/config/google_oauth_client.json` and `web/config/google_token.json` are gitignored (only relevant if you reactivate the legacy `google_calendar.py` path).
