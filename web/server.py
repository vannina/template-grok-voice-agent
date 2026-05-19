"""FastAPI server for the Grok Voice Agent.

Two entry points for the same agent:

  • Browser path (existing):
      GET  /              → serves the static SPA
      POST /token         → mints an xAI ephemeral token for the browser
      GET  /config        → returns the system prompt + tools.json (hot-reloaded)
      POST /api/calendar/book → server-side Composio call invoked by the SPA

  • Phone path (Twilio Media Streams):
      POST /twilio/voice  → TwiML telling Twilio to open a media stream to us
      WS   /twilio/stream → relays Twilio audio ↔ xAI realtime WS, runs tool calls server-side

Run:
  uvicorn web.server:app --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from string import Template

import httpx
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

XAI_API_KEY = os.environ.get("XAI_API_KEY")
XAI_TOKEN_URL = "https://api.x.ai/v1/realtime/client_secrets"
XAI_REALTIME_WS = "wss://api.x.ai/v1/realtime"
MODEL = "grok-voice-think-fast-1.0"
VOICE = "69smp8rm"  # Composio voice library id — French speaker

COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
COMPOSIO_EXEC_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_CREATE_EVENT"
COMPOSIO_USER_ID = "margot-bistro-demo"
RESTAURANT_TIMEZONE = "Europe/Paris"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
CONFIG_DIR = ROOT / "config"

RESTAURANT_HOURS = {
    "monday":    "closed",
    "tuesday":   "17:00-22:00",
    "wednesday": "17:00-22:00",
    "thursday":  "17:00-22:00",
    "friday":    "17:00-23:00",
    "saturday":  "11:00-23:00",
    "sunday":    "11:00-21:00",
}

app = FastAPI(title="Grok Voice Agent")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Read system prompt + tools fresh from disk on every call.
    Expands ${ENV_VAR} placeholders in tools.json via Template.safe_substitute
    (NB: os.path.expandvars on Windows breaks on apostrophes — don't use it)."""
    prompt_path = CONFIG_DIR / "system_prompt.txt"
    tools_path = CONFIG_DIR / "tools.json"
    instructions = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    tools_raw = tools_path.read_text(encoding="utf-8") if tools_path.exists() else "[]"
    tools = json.loads(Template(tools_raw).safe_substitute(os.environ))
    return {"instructions": instructions, "tools": tools}


async def _create_calendar_event(args: dict) -> dict:
    """Build the Google Calendar payload server-side (the model kept hallucinating
    fields like workingLocationProperties when given the raw schema) and POST to
    Composio. Returns a dict the voice agent can read back to the caller."""
    if not COMPOSIO_API_KEY:
        return {"status": "error", "message": "COMPOSIO_API_KEY not set"}
    payload = {
        "user_id": COMPOSIO_USER_ID,
        "arguments": {
            "calendar_id": "primary",
            "summary": f"Réservation : {args.get('name','?')} ({args.get('party_size','?')})",
            "description": f"Téléphone : {args.get('phone','?')}\nNotes : {args.get('notes') or '—'}",
            "start_datetime": f"{args.get('date','')}T{args.get('time','')}:00",
            "event_duration_hour": 1,
            "event_duration_minutes": 30,
            "timezone": RESTAURANT_TIMEZONE,
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            COMPOSIO_EXEC_URL,
            headers={"x-api-key": COMPOSIO_API_KEY, "Content-Type": "application/json"},
            json=payload,
        )
    body = r.json()
    if not body.get("successful"):
        return {"status": "error", "message": body.get("error") or "unknown error"}
    rd = body.get("data", {}).get("response_data", {})
    return {
        "status": "confirmed",
        "event_id": rd.get("id"),
        "html_link": rd.get("htmlLink"),
        "start": rd.get("start"),
        "end": rd.get("end"),
    }


async def _server_tool_call(name: str, args: dict) -> dict:
    """Function-tool dispatcher for the Twilio path (no browser to handle them).
    Mirrors the FUNCTIONS map in voice.js — keep them in sync when adding tools."""
    if name == "book_reservation":
        return await _create_calendar_event(args)
    if name == "get_restaurant_hours":
        return RESTAURANT_HOURS
    if name == "end_call":
        # Actual hang-up is deferred to the relay loop so we don't cut off the
        # goodbye mid-word; this just acknowledges so the model continues.
        return {"status": "ok", "message": "Hang-up scheduled after current utterance."}
    return {"error": f"No server handler for tool {name!r}"}


async def _twilio_hangup(call_sid: str) -> None:
    """Update the call status to "completed" via Twilio's REST API.
    Closing the media-stream WebSocket alone doesn't end the call — Twilio
    keeps the PSTN leg open and the caller hears silence. This is the clean
    way to actually drop the line."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and call_sid):
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls/{call_sid}.json"
    try:
        async with httpx.AsyncClient(timeout=10, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)) as client:
            await client.post(url, data={"Status": "completed"})
    except Exception as e:
        print(f"[twilio] hangup REST call failed: {e}")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def no_cache(request, call_next):
    """Dev convenience: defeat the browser cache for voice.js / index.html /
    config so prompt + tool edits are always picked up on reload."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# ---------------------------------------------------------------------------
# Browser-facing endpoints (unchanged behaviour)
# ---------------------------------------------------------------------------

@app.post("/token")
async def mint_token() -> JSONResponse:
    if not XAI_API_KEY:
        raise HTTPException(500, "XAI_API_KEY is not set. Add it to .env")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            XAI_TOKEN_URL,
            headers={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"expires_after": {"seconds": 300}},
        )
    if r.status_code >= 300:
        raise HTTPException(r.status_code, f"xAI token mint failed: {r.text}")
    return JSONResponse({"client_secret": r.json(), "model": MODEL})


@app.get("/config")
async def get_config() -> JSONResponse:
    return JSONResponse(_load_config())


class Reservation(BaseModel):
    name: str
    phone: str
    date: str         # YYYY-MM-DD
    time: str         # HH:MM (24h)
    party_size: int
    notes: str = ""


@app.post("/api/calendar/book")
async def book(res: Reservation) -> JSONResponse:
    return JSONResponse(await _create_calendar_event(res.model_dump()), status_code=200)


# ---------------------------------------------------------------------------
# Twilio voice path
# ---------------------------------------------------------------------------

@app.post("/twilio/voice")
async def twilio_voice(request: Request) -> Response:
    """Webhook hit by Twilio when a call comes in on the configured number.
    Returns TwiML that tells Twilio to open a bidirectional Media Stream
    WebSocket to /twilio/stream. The Host header is the public hostname seen
    by Twilio — that's what we want for the wss:// URL.

    Note: behind Nginx the Host header is preserved (we set proxy_set_header
    Host $host in deploy/nginx.conf.example) so this works out of the box."""
    host = request.headers.get("host") or request.url.hostname or "example.com"
    ws_url = f"wss://{host}/twilio/stream"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Connect><Stream url="{ws_url}" /></Connect>'
        '</Response>'
    )
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/twilio/stream")
async def twilio_stream(ws: WebSocket) -> None:
    """Bridge a Twilio Media Stream to an xAI realtime WS.

    Both sides exchange µ-law 8 kHz audio as base64 — Twilio's native format,
    and a format xAI accepts via session.audio.{input,output}.format = "audio/pcmu".
    No transcoding is needed: we just unwrap/rewrap the JSON envelope.
    """
    await ws.accept()
    print("[twilio] WS connected")

    if not XAI_API_KEY:
        await ws.close(code=1011, reason="XAI_API_KEY not configured")
        return

    config = _load_config()
    stream_sid: str | None = None
    call_sid: str | None = None
    pending_end_call = False

    xai_url = f"{XAI_REALTIME_WS}?model={MODEL}"
    headers = {"Authorization": f"Bearer {XAI_API_KEY}"}

    try:
        async with websockets.connect(xai_url, additional_headers=headers, max_size=None) as xai:
            # Configure session — µ-law 8 kHz so we can pass audio through verbatim.
            await xai.send(json.dumps({
                "type": "session.update",
                "session": {
                    "voice": VOICE,
                    "instructions": config["instructions"],
                    "tools": config["tools"],
                    "turn_detection": {"type": "server_vad"},
                    "input_audio_transcription": {"model": "whisper-1"},
                    "audio": {
                        "input":  {"format": {"type": "audio/pcmu"}},
                        "output": {"format": {"type": "audio/pcmu"}},
                    },
                },
            }))

            # Twilio doesn't speak first — kick off a greeting so the caller
            # doesn't pick up the phone to silence.
            await xai.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": (
                        "Salue brièvement et chaleureusement l'appelant en français, "
                        "présente-toi comme Margot du Petit Bistro, et demande "
                        "comment tu peux l'aider."
                    ),
                },
            }))

            async def twilio_to_xai() -> None:
                nonlocal stream_sid, call_sid
                try:
                    while True:
                        raw = await ws.receive_text()
                        evt = json.loads(raw)
                        kind = evt.get("event")
                        if kind == "start":
                            stream_sid = evt["start"]["streamSid"]
                            call_sid = evt["start"].get("callSid")
                            print(f"[twilio] start streamSid={stream_sid} callSid={call_sid}")
                        elif kind == "media":
                            await xai.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": evt["media"]["payload"],
                            }))
                        elif kind == "stop":
                            print("[twilio] stop")
                            return
                except WebSocketDisconnect:
                    print("[twilio] client disconnected")

            async def xai_to_twilio() -> None:
                nonlocal pending_end_call
                async for raw in xai:
                    evt = json.loads(raw)
                    t = evt.get("type", "")
                    # Log every non-audio event so we can see MCP calls,
                    # transcripts, errors, etc. Audio deltas are excluded
                    # because there are dozens per second.
                    if t not in ("response.audio.delta", "response.output_audio.delta"):
                        if t == "session.updated":
                            tools = (evt.get("session") or {}).get("tools") or []
                            tool_summary = ", ".join(
                                f"{tt.get('type')}:{tt.get('server_label') or tt.get('name','?')}" for tt in tools
                            ) or "(none)"
                            print(f"[xai] session.updated tools=[{tool_summary}]")
                        elif t in ("response.audio_transcript.delta", "response.output_audio_transcript.delta"):
                            # Skip per-token deltas, we'll log .done versions.
                            pass
                        elif t in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                            transcript = (evt.get("transcript") or "").replace("\n", " ").strip()
                            if transcript:
                                print(f"[margot] {transcript}")
                        elif t == "conversation.item.input_audio_transcription.completed":
                            transcript = (evt.get("transcript") or "").replace("\n", " ").strip()
                            if transcript:
                                print(f"[caller] {transcript}")
                        elif t == "error" or "error" in t.lower():
                            print(f"[xai] ERROR ({t}): {json.dumps(evt)[:600]}")
                        elif "mcp" in t.lower() or "tool" in t.lower() or "fail" in t.lower():
                            print(f"[xai] {t}: {json.dumps(evt)[:600]}")
                    if t in ("response.audio.delta", "response.output_audio.delta"):
                        if stream_sid:
                            await ws.send_text(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": evt["delta"]},
                            }))
                    elif t == "response.function_call_arguments.done":
                        name = evt.get("name", "")
                        cid = evt.get("call_id", "")
                        try:
                            args = json.loads(evt.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        print(f"[tool] → {name}({args})")
                        result = await _server_tool_call(name, args)
                        print(f"[tool] ← {name} → {result}")
                        if name == "end_call":
                            pending_end_call = True
                        await xai.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": cid,
                                "output": json.dumps(result),
                            },
                        }))
                        await xai.send(json.dumps({"type": "response.create"}))
                    elif t == "response.done":
                        if pending_end_call:
                            print("[tool] end_call → hanging up")
                            # Small grace period so Twilio finishes playing the
                            # buffered "au revoir" before we drop the call.
                            await asyncio.sleep(1.0)
                            await _twilio_hangup(call_sid or "")
                            return
                    elif t == "error":
                        print(f"[xai] error: {evt}")

            twilio_task = asyncio.create_task(twilio_to_xai())
            xai_task = asyncio.create_task(xai_to_twilio())
            done, pending = await asyncio.wait(
                [twilio_task, xai_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

    except Exception as e:
        print(f"[twilio/stream] error: {e!r}")
    finally:
        try:
            await ws.close()
        except Exception:
            pass
        print("[twilio] WS closed")


# ---------------------------------------------------------------------------
# Static SPA (must come last because of the catch-all "/" mount)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve index.html with a ?v=<mtime> cache-buster on voice.js."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    ver = int((STATIC_DIR / "voice.js").stat().st_mtime)
    return HTMLResponse(html.replace('src="/voice.js"', f'src="/voice.js?v={ver}"'))


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
