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
from datetime import datetime, timedelta
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

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
VOICE = "69smp8rm"  # voix française « Camille » (bibliothèque Grok Voice)

COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
COMPOSIO_EXEC_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_CREATE_EVENT"
COMPOSIO_LIST_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_EVENTS_LIST"
COMPOSIO_USER_ID = os.environ.get("COMPOSIO_USER_ID", "margot-bistro-demo")
RESTAURANT_TIMEZONE = "Europe/Paris"
TZ = ZoneInfo(RESTAURANT_TIMEZONE)

# Réservation multi-tables : capacité par créneau, durée d'une table.
RESTAURANT_CALENDAR_ID = os.environ.get("RESTAURANT_CALENDAR_ID", "primary")
CAPACITY_PER_SLOT = int(os.environ.get("CAPACITY_PER_SLOT", "10"))
TABLE_DURATION_MIN = int(os.environ.get("TABLE_DURATION_MIN", "90"))

# Fenêtres de service (heures locales) pour proposer des alternatives crédibles.
SERVICE_WINDOWS = [("12:00", "13:30"), ("19:30", "21:00")]  # dernière réservation

# --- Suivi de consommation xAI (le crédit est sur le compte de l'équipe, pas
#     celui de Vannina, donc on l'estime nous-mêmes côté serveur) ---------------
USAGE_LOG = Path(os.environ.get("USAGE_LOG_PATH", "/app/data/usage.jsonl"))
USAGE_TOKEN = os.environ.get("USAGE_TOKEN", "cs-margot")   # protège GET /usage
XAI_RATE_PER_MIN = float(os.environ.get("XAI_RATE_PER_MIN", "0.05"))  # ~0,05 $/min
XAI_CREDIT_TOTAL = float(os.environ.get("XAI_CREDIT_TOTAL", "40"))    # 40 $ équipe Alpha
AVG_SESSION_MIN = 1.5  # estimation pour les sessions sans durée remontée

# Alertes Telegram conso : palier tous les 10 $ + alerte "reste 10 $".
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ALERT_STEP_USD = 10.0


async def _telegram_send(text: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("[usage] telegram non configuré, alerte sautée")
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:  # noqa: BLE001
        print(f"[usage] telegram send failed: {e}")


def _alerts_fired() -> set[int]:
    fired: set[int] = set()
    if USAGE_LOG.exists():
        for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("event") == "alert":
                    fired.add(int(e["palier"]))
            except Exception:  # noqa: BLE001
                continue
    return fired


async def _check_credit_alerts() -> None:
    """Après chaque fin d'appel : franchit-on un nouveau palier de 10 $ ?"""
    agg = _aggregate_usage()
    cost = agg["cout_estime_usd"]
    restant = agg["credit_restant_estime_usd"]
    fired = _alerts_fired()
    # paliers consommés : 10, 20, 30… sous le total
    paliers = [int(p) for p in range(int(ALERT_STEP_USD), int(XAI_CREDIT_TOTAL), int(ALERT_STEP_USD))]
    for p in paliers:
        if cost >= p and p not in fired:
            reste10 = (XAI_CREDIT_TOTAL - p) <= ALERT_STEP_USD + 0.01
            if reste10:
                msg = (f"🔴 <b>Crédit Grok bientôt épuisé</b>\n"
                       f"Démo agent vocal : <b>{cost:.2f} $</b> consommés sur {XAI_CREDIT_TOTAL:.0f} $.\n"
                       f"Il ne reste plus que <b>{restant:.2f} $</b> ({agg['sessions_total']} appels).\n"
                       f"→ recharger le compte xAI de l'équipe.")
            else:
                msg = (f"🟠 <b>Conso Grok : palier {p} $</b>\n"
                       f"Démo agent vocal : <b>{cost:.2f} $</b> consommés sur {XAI_CREDIT_TOTAL:.0f} $.\n"
                       f"Reste ~<b>{restant:.2f} $</b> ({agg['sessions_total']} appels, {agg['minutes_estimees']} min).")
            await _telegram_send(msg)
            _usage_append({"event": "alert", "palier": p, "cost": round(cost, 2)})
            fired.add(p)


def _usage_append(event: dict) -> None:
    """Append-only, best-effort : ne jamais casser un appel à cause du log."""
    try:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        event["ts"] = datetime.now(TZ).isoformat()
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[usage] write failed: {e}")

FR_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


def _today_fr() -> str:
    now = datetime.now(TZ)
    return f"{FR_DAYS[now.weekday()]} {now.day} {FR_MONTHS[now.month - 1]} {now.year} ({now.strftime('%Y-%m-%d')})"

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
    instructions = instructions.replace("{{TODAY}}", _today_fr())
    tools_raw = tools_path.read_text(encoding="utf-8") if tools_path.exists() else "[]"
    tools = json.loads(Template(tools_raw).safe_substitute(os.environ))
    return {"instructions": instructions, "tools": tools}


def _load_restaurant() -> dict:
    """Fiche restaurant (web/config/restaurant.json), hot-reloaded comme le prompt."""
    path = CONFIG_DIR / "restaurant.json"
    if not path.exists():
        return {"error": "restaurant.json introuvable"}
    return json.loads(path.read_text(encoding="utf-8"))


async def _composio_execute(url: str, arguments: dict) -> dict:
    """POST un tool execute Composio. Retourne le body JSON (ou un dict d'erreur)."""
    if not COMPOSIO_API_KEY:
        return {"successful": False, "error": "COMPOSIO_API_KEY not set"}
    payload = {"user_id": COMPOSIO_USER_ID, "arguments": arguments}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            url,
            headers={"x-api-key": COMPOSIO_API_KEY, "Content-Type": "application/json"},
            json=payload,
        )
    try:
        return r.json()
    except Exception:
        return {"successful": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}


def _parse_event_window(ev: dict) -> tuple[datetime, datetime] | None:
    """Extrait (start, end) d'un événement Google Calendar (dateTime ou date)."""
    try:
        s = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        e = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        if not s or not e:
            return None
        sd = datetime.fromisoformat(s.replace("Z", "+00:00"))
        ed = datetime.fromisoformat(e.replace("Z", "+00:00"))
        if sd.tzinfo is None:
            sd = sd.replace(tzinfo=TZ)
        if ed.tzinfo is None:
            ed = ed.replace(tzinfo=TZ)
        return sd.astimezone(TZ), ed.astimezone(TZ)
    except Exception:
        return None


async def _list_events_window(day_start: datetime, day_end: datetime) -> list[tuple[datetime, datetime]] | None:
    """Liste les réservations du calendrier resto sur une fenêtre. None = erreur API."""
    # Le slug Composio EVENTS_LIST accepte les paramètres style Google (camelCase) ;
    # fallback snake_case si la validation refuse.
    for args in (
        {"calendarId": RESTAURANT_CALENDAR_ID,
         "timeMin": day_start.isoformat(), "timeMax": day_end.isoformat(),
         "singleEvents": True, "maxResults": 250},
        {"calendar_id": RESTAURANT_CALENDAR_ID,
         "time_min": day_start.isoformat(), "time_max": day_end.isoformat(),
         "single_events": True, "max_results": 250},
    ):
        body = await _composio_execute(COMPOSIO_LIST_URL, args)
        if body.get("successful"):
            rd = body.get("data", {}).get("response_data", body.get("data", {})) or {}
            items = rd.get("items") or rd.get("events") or []
            windows = []
            for ev in items:
                if str(ev.get("status", "")).lower() == "cancelled":
                    continue
                w = _parse_event_window(ev)
                if w:
                    windows.append(w)
            return windows
        print(f"[calendar] EVENTS_LIST refusé ({json.dumps(args)[:80]}…) : {str(body.get('error'))[:200]}")
    return None


def _count_overlaps(windows: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> int:
    return sum(1 for (s, e) in windows if s < end and e > start)


async def _check_availability(args: dict) -> dict:
    """Disponibilité multi-tables : un créneau est libre tant que moins de
    CAPACITY_PER_SLOT réservations (durée TABLE_DURATION_MIN) le chevauchent.
    Si complet : propose jusqu'à 2 alternatives dans le même service."""
    try:
        start = datetime.strptime(f"{args.get('date','')} {args.get('time','')}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return {"status": "error", "message": "Date ou heure invalide (attendu YYYY-MM-DD et HH:MM)."}
    duration = timedelta(minutes=TABLE_DURATION_MIN)
    end = start + duration

    day_start = start.replace(hour=0, minute=0)
    day_end = day_start + timedelta(days=1)
    windows = await _list_events_window(day_start, day_end)
    if windows is None:
        return {"status": "error",
                "message": "Le livre de réservations est momentanément inaccessible. Propose qu'un membre de l'équipe rappelle."}

    booked = _count_overlaps(windows, start, end)
    free = max(0, CAPACITY_PER_SLOT - booked)
    if free > 0:
        return {"status": "ok", "available": True, "tables_libres": free}

    # Complet : chercher des alternatives dans les fenêtres de service du jour.
    alternatives: list[str] = []
    for win_start, win_last in SERVICE_WINDOWS:
        t = datetime.strptime(f"{args.get('date','')} {win_start}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        last = datetime.strptime(f"{args.get('date','')} {win_last}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        while t <= last and len(alternatives) < 2:
            if t != start and _count_overlaps(windows, t, t + duration) < CAPACITY_PER_SLOT:
                # privilégier les créneaux proches de la demande
                if abs((t - start).total_seconds()) <= 2 * 3600:
                    alternatives.append(t.strftime("%H:%M"))
            t += timedelta(minutes=30)
    return {"status": "ok", "available": False, "tables_libres": 0, "alternatives": alternatives}


async def _create_calendar_event(args: dict) -> dict:
    """Build the Google Calendar payload server-side (the model kept hallucinating
    fields like workingLocationProperties when given the raw schema) and POST to
    Composio. Returns a dict the voice agent can read back to the caller."""
    if not COMPOSIO_API_KEY:
        return {"status": "error", "message": "COMPOSIO_API_KEY not set"}
    # Reject obvious placeholder phones — otherwise Margot blindly saves
    # "anonymous" because Twilio sent it as the masked caller's From=.
    phone = str(args.get("phone") or "").strip()
    if phone.lower() in {"", "anonymous", "restricted", "unavailable", "unknown", "private", "none", "n/a"}:
        return {
            "status": "error",
            "message": "INVALID_PHONE: aucun numéro valide fourni — demande au client un vrai numéro de téléphone et rappelle book_reservation avec.",
        }
    # Garde anti-surbooking : re-vérifie la capacité juste avant de créer.
    avail = await _check_availability(args)
    if avail.get("status") == "ok" and not avail.get("available"):
        return {
            "status": "full",
            "message": "Ce créneau vient de se remplir.",
            "alternatives": avail.get("alternatives", []),
        }

    body = await _composio_execute(COMPOSIO_EXEC_URL, {
        "calendar_id": RESTAURANT_CALENDAR_ID,
        "summary": f"Réservation : {args.get('name','?')} ({args.get('party_size','?')} pers.)",
        "description": f"Téléphone : {args.get('phone','?')}\nNotes : {args.get('notes') or '—'}\nPrise par Margot (agent vocal Corsica Studio)",
        "start_datetime": f"{args.get('date','')}T{args.get('time','')}:00",
        "event_duration_hour": TABLE_DURATION_MIN // 60,
        "event_duration_minutes": TABLE_DURATION_MIN % 60,
        "timezone": RESTAURANT_TIMEZONE,
    })
    if not body.get("successful"):
        return {"status": "error", "message": str(body.get("error") or "unknown error")[:300]}
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
    if name == "check_availability":
        return await _check_availability(args)
    if name == "get_restaurant_info":
        return _load_restaurant()
    if name == "get_restaurant_hours":  # compat legacy
        return _load_restaurant().get("horaires", RESTAURANT_HOURS)
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
    _usage_append({"event": "start", "path": "browser"})
    return JSONResponse({"client_secret": r.json(), "model": MODEL})


class UsageEnd(BaseModel):
    seconds: float = 0.0


@app.post("/usage/end")
async def usage_end(u: UsageEnd) -> JSONResponse:
    """La SPA remonte la durée réelle de l'appel au raccrochage (sendBeacon)."""
    secs = max(0.0, min(u.seconds, 3600))  # garde-fou : 1 h max
    _usage_append({"event": "end", "path": "browser", "seconds": round(secs, 1)})
    await _check_credit_alerts()
    return JSONResponse({"ok": True})


def _aggregate_usage() -> dict:
    sessions = 0
    durations: list[float] = []
    today = datetime.now(TZ).date().isoformat()
    today_sessions = 0
    by_day: dict[str, int] = {}
    if USAGE_LOG.exists():
        for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            day = (e.get("ts") or "")[:10]
            if e.get("event") == "start":
                sessions += 1
                by_day[day] = by_day.get(day, 0) + 1
                if day == today:
                    today_sessions += 1
            elif e.get("event") == "end" and e.get("seconds"):
                durations.append(float(e["seconds"]))
    # minutes mesurées (sessions terminées proprement) + estimation pour le reste
    measured_min = sum(durations) / 60.0
    unmeasured = max(0, sessions - len(durations))
    est_min = measured_min + unmeasured * AVG_SESSION_MIN
    est_cost = est_min * XAI_RATE_PER_MIN
    return {
        "sessions_total": sessions,
        "sessions_today": today_sessions,
        "minutes_estimees": round(est_min, 1),
        "cout_estime_usd": round(est_cost, 2),
        "credit_total_usd": XAI_CREDIT_TOTAL,
        "credit_restant_estime_usd": round(max(0.0, XAI_CREDIT_TOTAL - est_cost), 2),
        "pourcent_consomme": round(100 * est_cost / XAI_CREDIT_TOTAL, 1) if XAI_CREDIT_TOTAL else None,
        "tarif_min_usd": XAI_RATE_PER_MIN,
        "par_jour": dict(sorted(by_day.items())),
        "note": "Estimation côté serveur (le solde exact reste sur console.x.ai du compte équipe).",
    }


@app.get("/usage")
async def usage_report(key: str = "") -> JSONResponse:
    if key != USAGE_TOKEN:
        raise HTTPException(403, "clé d'accès invalide (paramètre ?key=)")
    return JSONResponse(_aggregate_usage())


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


class AvailabilityQuery(BaseModel):
    date: str         # YYYY-MM-DD
    time: str         # HH:MM (24h)
    party_size: int = 2


@app.post("/api/calendar/availability")
async def availability(q: AvailabilityQuery) -> JSONResponse:
    return JSONResponse(await _check_availability(q.model_dump()), status_code=200)


@app.get("/api/restaurant")
async def restaurant_info() -> JSONResponse:
    return JSONResponse(_load_restaurant())


# ---------------------------------------------------------------------------
# Twilio voice path
# ---------------------------------------------------------------------------

@app.post("/twilio/voice")
async def twilio_voice(request: Request) -> Response:
    """Webhook hit by Twilio when a call comes in on the configured number.
    Returns TwiML that tells Twilio to open a bidirectional Media Stream
    WebSocket to /twilio/stream, and passes the caller's number as a custom
    Stream <Parameter> so the WS handler can inject it into the system prompt
    (otherwise the model has no way to know what number the caller is calling
    from, and can't honour "use the number I'm calling from")."""
    host = request.headers.get("host") or request.url.hostname or "example.com"
    ws_url = f"wss://{host}/twilio/stream"
    form = await request.form()
    caller_from = (form.get("From") or "").strip()
    param_xml = f'<Parameter name="from" value="{caller_from}" />' if caller_from else ""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Connect><Stream url="{ws_url}">{param_xml}</Stream></Connect>'
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

            async def twilio_to_xai() -> None:
                """Reads Twilio events and forwards audio to xAI.

                The session.update + greeting are deferred until we receive
                the Twilio `start` event, because that's when we learn the
                caller's phone number (passed in as a custom <Parameter>).
                We inject it into the system prompt so Margot can honour
                'use the number I'm calling from'."""
                nonlocal stream_sid, call_sid
                try:
                    while True:
                        raw = await ws.receive_text()
                        evt = json.loads(raw)
                        kind = evt.get("event")
                        if kind == "start":
                            stream_sid = evt["start"]["streamSid"]
                            call_sid = evt["start"].get("callSid")
                            custom = evt["start"].get("customParameters") or {}
                            caller_from = (custom.get("from") or "").strip()
                            print(f"[twilio] start streamSid={stream_sid} callSid={call_sid} from={caller_from!r}")

                            instructions = config["instructions"]
                            # Twilio sends literal strings like "anonymous" / "restricted"
                            # / "unavailable" when the caller's number is hidden. Treat
                            # them as "no CallerID" — otherwise the model passes the
                            # literal "anonymous" as the phone field.
                            HIDDEN = {"", "anonymous", "restricted", "unavailable", "unknown", "private"}
                            if caller_from.lower() in HIDDEN:
                                instructions += (
                                    "\n\n[Contexte de l'appel]\n"
                                    "Le numéro de l'appelant est MASQUÉ (numéro privé). "
                                    "Tu n'as PAS de CallerID exploitable. "
                                    "Tu DOIS demander explicitement un numéro à l'appelant. "
                                    "Si l'appelant dit «utilisez celui qui s'affiche» ou similaire, "
                                    "réponds : «Désolée, votre numéro est masqué. Pouvez-vous me le donner ?»"
                                )
                            else:
                                instructions += (
                                    f"\n\n[Contexte de l'appel]\n"
                                    f"Le numéro depuis lequel l'appelant te contacte (CallerID) "
                                    f"est : {caller_from}. Si l'appelant dit «mon numéro est celui "
                                    f"qui s'affiche», «le numéro depuis lequel j'appelle», ou ne "
                                    f"donne pas explicitement de numéro, utilise CE numéro pour "
                                    f"book_reservation."
                                )

                            await xai.send(json.dumps({
                                "type": "session.update",
                                "session": {
                                    "voice": VOICE,
                                    "instructions": instructions,
                                    "tools": config["tools"],
                                    "turn_detection": {"type": "server_vad"},
                                    "input_audio_transcription": {
                                        "model": "whisper-1",
                                        "language": "fr",
                                    },
                                    "audio": {
                                        "input":  {"format": {"type": "audio/pcmu"}},
                                        "output": {"format": {"type": "audio/pcmu"}},
                                    },
                                },
                            }))

                            # Trigger an opening greeting — Twilio doesn't speak first.
                            await xai.send(json.dumps({
                                "type": "response.create",
                                "response": {
                                    "instructions": (
                                        "Salue en français, avec l'élégance chaleureuse d'une hôtesse "
                                        "de belle maison provençale. Ex : 'LOU PATIO, bonjour, Margot "
                                        "à votre écoute.' Une seule phrase, posée."
                                    ),
                                },
                            }))
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
                                # Safety net: Grok routinely says "au revoir" out loud
                                # but forgets to invoke end_call. If we hear the goodbye
                                # in the transcript, we trigger the hangup ourselves
                                # at response.done. If the model also calls end_call,
                                # pending_end_call is already True — no harm.
                                low = transcript.lower()
                                GOODBYES = (
                                    "au revoir", "bonne soirée", "bonne journée",
                                    "à très vite", "à bientôt", "bonne fin de",
                                    "merci d'avoir appelé", "à plus tard",
                                )
                                if not pending_end_call and any(g in low for g in GOODBYES):
                                    print("[twilio] auto-hangup armed (goodbye in transcript)")
                                    pending_end_call = True
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
    """Serve index.html with ?v=<mtime> cache-busters on voice.js and style.css."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    ver_js = int((STATIC_DIR / "voice.js").stat().st_mtime)
    ver_css = int((STATIC_DIR / "style.css").stat().st_mtime)
    html = html.replace('src="/voice.js"', f'src="/voice.js?v={ver_js}"')
    html = html.replace('href="/style.css"', f'href="/style.css?v={ver_css}"')
    return HTMLResponse(html)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
