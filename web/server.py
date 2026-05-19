"""Local FastAPI server for the Grok Voice Agent web demo.

Endpoints:
  GET  /            -> serves static/index.html
  GET  /guide       -> serves static/guide.html
  GET  /config      -> returns editable system_prompt.txt + tools.json
  POST /token       -> mints an xAI ephemeral token for the browser

Run:
  uvicorn web.server:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from string import Template

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

XAI_API_KEY = os.environ.get("XAI_API_KEY")
XAI_TOKEN_URL = "https://api.x.ai/v1/realtime/client_secrets"
MODEL = "grok-voice-think-fast-1.0"

COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
COMPOSIO_EXEC_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_CREATE_EVENT"
COMPOSIO_USER_ID = "margot-bistro-demo"
RESTAURANT_TIMEZONE = "Europe/Paris"

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
CONFIG_DIR = ROOT / "config"

app = FastAPI(title="Grok Voice Agent - Web")


@app.middleware("http")
async def no_cache(request, call_next):
    """Dev convenience: defeat the browser cache for voice.js / index.html /
    config so prompt + tool edits are always picked up on reload, no Ctrl+F5
    dance required."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


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
    """Return system prompt + tools, freshly read from disk each time
    so editing the files doesn't require a server restart.

    tools.json may contain ${ENV_VAR} placeholders (e.g. COMPOSIO_API_KEY,
    COMPOSIO_MCP_URL) — they're expanded server-side so secrets stay out of
    the file but still reach xAI via the session.update payload."""
    prompt_path = CONFIG_DIR / "system_prompt.txt"
    tools_path = CONFIG_DIR / "tools.json"
    instructions = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    tools_raw = tools_path.read_text(encoding="utf-8") if tools_path.exists() else "[]"
    # NB: don't use os.path.expandvars on Windows — it has shell-quote
    # semantics, so a stray apostrophe in the JSON (e.g. "restaurant's")
    # silently disables expansion of every ${...} that follows.
    tools = json.loads(Template(tools_raw).safe_substitute(os.environ))
    return JSONResponse({"instructions": instructions, "tools": tools})


class Reservation(BaseModel):
    name: str
    phone: str
    date: str         # YYYY-MM-DD
    time: str         # HH:MM (24h)
    party_size: int
    notes: str = ""


@app.post("/api/calendar/book")
async def book(res: Reservation) -> JSONResponse:
    """Create the calendar event via Composio's REST API. We build the
    payload here (not in the voice agent) so the model can't inject random
    Google Calendar fields like `workingLocationProperties` — Grok kept
    hallucinating those and Google rejected the request."""
    if not COMPOSIO_API_KEY:
        return JSONResponse({"status": "error", "message": "COMPOSIO_API_KEY not set"}, status_code=200)
    payload = {
        "user_id": COMPOSIO_USER_ID,
        "arguments": {
            "calendar_id": "primary",
            "summary": f"Réservation : {res.name} ({res.party_size})",
            "description": f"Téléphone : {res.phone}\nNotes : {res.notes or '—'}",
            "start_datetime": f"{res.date}T{res.time}:00",
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
        return JSONResponse({"status": "error", "message": body.get("error") or "unknown error"}, status_code=200)
    rd = body.get("data", {}).get("response_data", {})
    return JSONResponse({
        "status": "confirmed",
        "event_id": rd.get("id"),
        "html_link": rd.get("htmlLink"),
        "start": rd.get("start"),
        "end": rd.get("end"),
    })


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve index.html with a dynamic cache-buster on /voice.js so browser
    caches can never serve a stale module (a real headache during dev)."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    ver = int((STATIC_DIR / "voice.js").stat().st_mtime)
    return HTMLResponse(html.replace('src="/voice.js"', f'src="/voice.js?v={ver}"'))


# Static frontend (guide.html, voice.js, style.css). The "/" path is handled
# above so it can inject the voice.js cache buster.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
