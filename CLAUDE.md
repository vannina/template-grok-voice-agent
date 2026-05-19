# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Demo of a realtime voice agent ("Margot", an hôtesse for a French Montréal restaurant) built on xAI's **`grok-voice-think-fast-1.0`** model. A FastAPI server mints ephemeral xAI tokens and serves a static frontend; the browser opens a WebSocket directly to `wss://api.x.ai/v1/realtime` and streams PCM16 audio at 24 kHz both ways. The agent can call tools — currently a Google Calendar reservation hook and a hours lookup.

The README is in French; user-facing copy (system prompt, UI) is French by default.

## Common commands

Activate the venv first (`.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate` on Mac/Linux), then:

```
pip install -r requirements.txt        # install deps
uvicorn web.server:app --port 8000 --reload   # run dev server
python setup_google.py                 # one-time OAuth flow for Google Calendar
```

App: `http://localhost:8000` · Embedded guide: `http://localhost:8000/guide.html`.

There is no test suite, no linter config, and no build step.

## Architecture

Three layers; the realtime audio path does **not** go through the Python server.

1. **FastAPI server (`web/server.py`)** — minimal control plane. Three endpoints:
   - `POST /token` — calls xAI `/v1/realtime/client_secrets` with the server-side `XAI_API_KEY` and returns a 5-minute ephemeral secret. The real API key never reaches the browser.
   - `GET /config` — reads `web/config/system_prompt.txt` and `web/config/tools.json` **fresh from disk on every request**, so editing those files takes effect on the next conversation with no restart.
   - `POST /api/calendar/book` — proxies to `web/google_calendar.py:create_event`. Errors are returned as `{"status":"error", ...}` with HTTP 200 on purpose, so the voice agent can react verbally instead of seeing a fetch failure.
   - Everything else is mounted from `web/static/` (static SPA).

2. **Browser client (`web/static/voice.js`)** — runs the realtime session. On Start:
   - Concurrently requests mic, fetches `/token`, fetches `/config`.
   - Opens `wss://api.x.ai/v1/realtime?model=...` using the WebSocket subprotocol `xai-client-secret.<secret>` for auth.
   - Sends a `session.update` with voice="eve", the loaded instructions/tools, `server_vad` turn detection, and `whisper-1` input transcription.
   - Captures mic via `ScriptProcessorNode` (4096 samples), encodes Float32→PCM16→base64, sends as `input_audio_buffer.append`. Frames captured before the WS opens are buffered in `earlyBuffer` and flushed on `onopen`.
   - Plays assistant audio with a manual `playhead` cursor that schedules `AudioBufferSourceNode`s back-to-back to avoid gaps.
   - Handles function tool calls: on `response.function_call_arguments.done` it looks up the tool name in the `FUNCTIONS` map, runs it, then sends `conversation.item.create` (function_call_output) + `response.create` to let the agent continue.

3. **Agent configuration (hot-reloaded)**:
   - `web/config/system_prompt.txt` — persona and rules.
   - `web/config/tools.json` — tool definitions sent to xAI. Mix of xAI built-ins (`web_search`, `x_search`, `file_search`, `mcp`) and `function` tools.
   - For each `function` tool you add to `tools.json`, you **must** add a matching handler in the `FUNCTIONS` object in `web/static/voice.js`. The handler receives the parsed args and returns a JSON-serializable result. Server-side work (DB, external APIs) belongs behind a FastAPI endpoint that the handler fetches — see `book_reservation` → `/api/calendar/book` for the pattern.

## Sample rate

24 kHz everywhere: `SAMPLE_RATE = 24000` in `voice.js`, declared on both `getUserMedia`, `AudioContext`, and the `session.update.audio.{input,output}.format.rate`. Mismatched rates produce choppy/sped-up audio — keep all three in lockstep when changing it.

## Secrets / files not in git

`.env` holds `XAI_API_KEY`. `web/config/google_oauth_client.json` (OAuth client downloaded from Google Cloud Console) and `web/config/google_token.json` (created by `setup_google.py`) are both gitignored. Calendar code defaults to `primary` calendar, `America/Montreal` timezone, 90 min default duration — change in `web/google_calendar.py` if needed.
