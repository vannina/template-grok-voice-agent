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
from urllib.parse import quote
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

# --- Métier servi par cette instance --------------------------------------
# Un SEUL conteneur sert les 7 métiers : le métier est résolu par le
# sous-domaine (Host header) — demo-<metier>.corsica-studio.com → <metier> ;
# demo.corsica-studio.com / localhost / IP → DEFAULT_METIER (rétro-compat).
# En local, forcer un métier précis avec la variable d'env METIER.
DEFAULT_METIER = (os.environ.get("METIER", "restaurant").strip().lower() or "restaurant")
PUBLIC_BASE_DOMAIN = os.environ.get("PUBLIC_BASE_DOMAIN", "corsica-studio.com")

# --- Standard téléphonique bi-marque (CS + CD) ------------------------------
# Le numéro « standard » (04 12 13 60 10) arrive sur un Host dédié :
# standard.corsica-studio.com → annonce légale + IVR DTMF (1 = Corsica Studio,
# 2 = Corsica Design) puis Media Stream avec Parameter entite=cs|cd.
# Tous les autres Hosts gardent le comportement démo INCHANGÉ.
# Hosts du standard configurables (liste séparée par des virgules) via env.
STANDARD_HOSTS = {
    h.strip().lower()
    for h in os.environ.get("STANDARD_HOSTS", "standard.corsica-studio.com").split(",")
    if h.strip()
}

COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
COMPOSIO_EXEC_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_CREATE_EVENT"
COMPOSIO_LIST_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_EVENTS_LIST"
COMPOSIO_USER_ID = os.environ.get("COMPOSIO_USER_ID", "margot-bistro-demo")
RESTAURANT_TIMEZONE = "Europe/Paris"
TZ = ZoneInfo(RESTAURANT_TIMEZONE)

# Réservation multi-tables : capacité par créneau, durée d'une table.
RESTAURANT_CALENDAR_ID = os.environ.get("RESTAURANT_CALENDAR_ID", "primary")
CAPACITY_PER_SLOT = int(os.environ.get("CAPACITY_PER_SLOT", "10"))

# --- Demande de rappel (escalade) — PRÉPARÉ MAIS DÉSACTIVÉ PAR DÉFAUT ---------
# Quand l'agent ne peut pas répondre ou pas finaliser un rendez-vous, il capte
# nom + téléphone + motif via l'outil `prendre_message` et le transmet au pro par
# Telegram + copie email (Resend). DORMANT tant que ENABLE_CALLBACK_TOOL != 1 :
# l'outil n'est PAS exposé à l'agent et le comportement actuel ne change pas.
# Activation et test : voir docs/MECANISME-RAPPEL.md.
NOTIFY_ENABLED = os.environ.get("ENABLE_CALLBACK_TOOL", "0").strip().lower() in ("1", "true", "yes", "on")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL")
NOTIFY_FROM = os.environ.get("NOTIFY_FROM", "Corsica Studio <noreply@corsica-studio.com>")

# Outil exposé à l'agent UNIQUEMENT si NOTIFY_ENABLED (injecté dans _load_config).
CALLBACK_TOOL = {
    "type": "function",
    "name": "prendre_message",
    "description": (
        "Capte une demande de rappel quand tu ne peux pas répondre à la question "
        "ou pas finaliser le rendez-vous. Recueille le nom, le numéro et le motif, "
        "rédige un résumé structuré de l'échange, puis appelle cet outil : la demande "
        "est transmise aussitôt à l'équipe pour qu'un humain rappelle la personne en "
        "connaissant déjà le contexte. N'invente jamais : si tu ne sais pas, prends un message."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "nom": {"type": "string", "description": "Nom de la personne à rappeler"},
            "telephone": {"type": "string", "description": "Numéro de rappel"},
            "motif": {"type": "string", "description": "Demande en une phrase (l'essentiel)"},
            "resume": {"type": "string", "description": "Résumé structuré de l'échange : ce que la personne veut précisément, le contexte, les informations déjà fournies et tout détail utile pour la rappeler efficacement. Quelques lignes claires."},
        },
        "required": ["nom", "telephone", "motif"],
    },
}
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

# --- Attribution démo cold email -------------------------------------------
# Quand un prospect identifié (lien email ...?lead=recXXX) lance une démo, on
# logue son record_id Airtable dans usage.jsonl ET on notifie n8n (WF-13) qui
# rapproche la démo de l'étape de relance et alerte Vannina en temps réel.
DEMO_WEBHOOK_URL = os.environ.get("DEMO_WEBHOOK_URL", "").strip()

# --- Standard bi-marque : CRM Airtable + transfert + webhook fin d'appel (A.3) --
# Tools server-side du standard téléphonique (entités cs/cd UNIQUEMENT — les
# métiers démo n'exposent pas ces tools dans leurs tools.json, rien ne change
# pour eux). TOUT est best-effort : une panne Airtable / n8n / Twilio REST ne
# doit JAMAIS casser l'appel en cours. Env manquantes → les tools répondent
# {"status": "non_configuré"} proprement (+ warning en log) au lieu de crasher.
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
STANDARD_AIRTABLE_BASE_ID = os.environ.get("STANDARD_AIRTABLE_BASE_ID", "").strip()
STANDARD_CONTACTS_TABLE = os.environ.get("STANDARD_CONTACTS_TABLE", "Contacts").strip()
STANDARD_CALLS_TABLE = os.environ.get("STANDARD_CALLS_TABLE", "Appels").strip()
STANDARD_CONFIG_TABLE = os.environ.get("STANDARD_CONFIG_TABLE", "Config").strip()
# Récap de fin d'appel standard → n8n (même pattern que DEMO_WEBHOOK_URL).
STANDARD_WEBHOOK_URL = os.environ.get("STANDARD_WEBHOOK_URL", "").strip()
# Transfert vers Vannina (transfer_to_human) :
#  - TRANSFER_ENABLED=1|0 prime (toggle rapide) ; si NON définie, repli
#    optionnel sur Airtable table Config, champ `transfert_dispo` (checkbox).
#  - TRANSFER_NUMBER : ligne appelée par le <Dial>. ⚠️ Anti-boucle (archi §5) :
#    ce numéro NE DOIT PAS avoir de renvoi vers le standard, sinon l'appel
#    reboucle sur l'IA. Utiliser une ligne dédiée sans renvoi.
TRANSFER_ENABLED = os.environ.get("TRANSFER_ENABLED", "").strip()
TRANSFER_NUMBER = os.environ.get("TRANSFER_NUMBER", "").strip()
TRANSFER_DIAL_TIMEOUT = int(os.environ.get("TRANSFER_DIAL_TIMEOUT", "20"))

# --- Prospection sortante (D.3) — brique outbound B2B /CS ---------------------
# POST /outbound/call (appelé par n8n WF-OUT) compose un appel Twilio sortant
# vers un pro, qui atterrit sur /twilio/voice-out → Media Stream métier
# « prospection » (Léa, SDR). Garde-fous serveur NON contournables :
# horaires ouvrés B2B, numéro français uniquement, registre d'opposition
# (loi 2025-594 : B2B opt-out + droit d'opposition immédiat).
OUTBOUND_TOKEN = os.environ.get("OUTBOUND_TOKEN", "").strip()          # auth n8n → header X-Outbound-Token
OUTBOUND_HOURS = os.environ.get("OUTBOUND_HOURS", "9-12,14-18").strip()  # plages locales Europe/Paris, lun-ven
OUTBOUND_FROM_NUMBER = os.environ.get("OUTBOUND_FROM_NUMBER", "+33412136016").strip()
OUTBOUND_METIER = os.environ.get("OUTBOUND_METIER", "prospection").strip().lower()
# Host public embarqué dans l'Url Twilio (fallback : Host de la requête n8n).
OUTBOUND_PUBLIC_HOST = os.environ.get("OUTBOUND_PUBLIC_HOST", "").strip()
# Table Airtable du registre d'opposition (base STANDARD_AIRTABLE_BASE_ID).
# Schéma attendu : telephone (texte, clé), date (date), source (texte).
OPPOSITIONS_TABLE = os.environ.get("OPPOSITIONS_TABLE", "Oppositions").strip()

# Contexte prospect en mémoire process (rid → fiche), TTL 2 h : posé par
# /outbound/call, lu par le WS /twilio/stream pour personnaliser l'appel.
# Volontairement simple (un seul worker uvicorn en prod) — pas de Redis.
_OUTBOUND_TTL_S = 2 * 3600
_OUTBOUND_CTX: dict[str, tuple[float, dict]] = {}


def _outbound_ctx_put(key: str, prospect: dict) -> None:
    if not key:
        return
    now = datetime.now(TZ).timestamp()
    # purge opportuniste des entrées expirées
    for k in [k for k, (ts, _) in _OUTBOUND_CTX.items() if now - ts > _OUTBOUND_TTL_S]:
        _OUTBOUND_CTX.pop(k, None)
    _OUTBOUND_CTX[key] = (now, prospect)


def _outbound_ctx_get(key: str) -> dict:
    if not key:
        return {}
    item = _OUTBOUND_CTX.get(key)
    if not item:
        return {}
    ts, prospect = item
    if datetime.now(TZ).timestamp() - ts > _OUTBOUND_TTL_S:
        _OUTBOUND_CTX.pop(key, None)
        return {}
    return prospect


def _parse_hours_spec(spec: str) -> list[tuple[int, int]]:
    """"9-12,14-18" → [(9, 12), (14, 18)]. Plage invalide → ignorée (log)."""
    windows: list[tuple[int, int]] = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            if 0 <= start < end <= 24:
                windows.append((start, end))
            else:
                print(f"[outbound] plage horaire invalide ignorée : {part!r}")
        except ValueError:
            print(f"[outbound] plage horaire illisible ignorée : {part!r}")
    return windows


def _outbound_hours_ok(now: datetime | None = None, spec: str | None = None) -> bool:
    """Garde-fou horaires : jours ouvrés (lun-ven) + plages OUTBOUND_HOURS
    (heure locale Europe/Paris). Spec vide/invalide → False (fail closed)."""
    now = now or datetime.now(TZ)
    if now.weekday() >= 5:  # samedi/dimanche : jamais
        return False
    windows = _parse_hours_spec(spec if spec is not None else OUTBOUND_HOURS)
    if not windows:
        return False
    t = now.hour + now.minute / 60.0
    return any(start <= t < end for start, end in windows)


def _normalize_fr_phone(raw: str) -> str | None:
    """Numéro français uniquement (garde-fou B2B campagne FR).
    Accepte +33XXXXXXXXX ou 0XXXXXXXXX (espaces/points/tirets tolérés) →
    normalisé +33… ; tout le reste → None."""
    tel = "".join(ch for ch in str(raw or "") if ch.isdigit() or ch == "+")
    if tel.startswith("0033"):
        tel = "+33" + tel[4:]
    if tel.startswith("0") and len(tel) == 10 and tel[1] != "0":
        tel = "+33" + tel[1:]
    if tel.startswith("+33") and len(tel) == 12 and tel[3] != "0" and tel[3:].isdigit():
        return tel
    return None


def _local_oppositions() -> set[str]:
    """Registre local d'opposition (usage.jsonl, event=opposition) : filet quand
    Airtable est en panne — une opposition notée en appel reste respectée."""
    tels: set[str] = set()
    if USAGE_LOG.exists():
        for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("event") == "opposition" and e.get("telephone"):
                    tels.add(str(e["telephone"]).strip())
            except Exception:  # noqa: BLE001
                continue
    return tels

# Sentinelles Twilio « numéro masqué » (From= littéral quand le CallerID est caché).
HIDDEN_CALLERS = {"", "anonymous", "restricted", "unavailable", "unknown", "private"}

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


def _now_fr() -> str:
    now = datetime.now(TZ)
    return f"{FR_DAYS[now.weekday()]} {now.day} {FR_MONTHS[now.month - 1]} {now.year}, {now.strftime('%H:%M')}"


def _runtime_rules(recorded: bool = True) -> str:
    """Règles transverses injectées à chaque conversation (tous métiers, browser + Twilio).
    Recalculées à chaque appel pour donner l'heure réelle à l'agent.
    `recorded=False` (standard cs/cd) : les appels du standard ne sont PAS
    enregistrés — on ne dit pas le contraire à l'appelant (consigne Vannina)."""
    return (
        "\n\n[Règles en temps réel — à respecter absolument]\n"
        f"- Date et heure actuelles : {_now_fr()} (heure de Paris). Ne propose JAMAIS un créneau "
        "déjà passé : tout créneau que tu proposes doit être POSTÉRIEUR à cette date et heure. "
        "En fin de journée, propose plus tard aujourd'hui si c'est jouable, sinon les jours suivants.\n"
        "- Ne présume jamais le genre de la personne : n'utilise pas « Monsieur » ni « Madame » "
        "tant que tu ne le sais pas. Reste neutre et chaleureux, ou demande poliment son nom.\n"
        "- Si tu n'as pas l'information demandée (un tarif, un détail absent de tes informations), "
        "ne l'invente jamais : propose de prendre un message et qu'un membre de l'équipe rappelle "
        "la personne, ou de transmettre sa demande à un humain. Recueille alors son nom et son numéro.\n"
        "- Si on te demande si tu es une intelligence artificielle, un robot ou un répondeur, "
        "réponds clairement que OUI, tu es l'assistant vocal IA de l'établissement."
        + (" Indique aussi, le cas échéant, que l'appel peut être enregistré." if recorded else "")
    )

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
# Auth REST par clé API (SK + secret) — recommandé par Twilio, plus sûr que
# l'Auth Token. Si présents, on les utilise ; sinon fallback AccountSID+AuthToken.
TWILIO_API_KEY_SID = os.environ.get("TWILIO_API_KEY_SID")
TWILIO_API_KEY_SECRET = os.environ.get("TWILIO_API_KEY_SECRET")


def _twilio_rest_auth() -> tuple[str, str] | None:
    """Couple (user, pass) pour l'API REST Twilio : clé API en priorité."""
    if TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET:
        return (TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        return (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return None

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

# --- Socle « un agent par métier » -----------------------------------------
# Tout ce qui varie d'un métier à l'autre vit dans web/config/metiers/<metier>/
# (system_prompt.txt + tools.json + business.json + profile.json). Le restaurant
# reste servi par les fichiers historiques web/config/*.json (fallback), donc la
# prod actuelle n'est pas touchée. profile.json ne porte AUCUN secret : seulement
# des libellés UI, du SEO et des paramètres d'agenda.

# Valeurs par défaut = restaurant. Garantit que index.html (templatisé) et voice.js
# s'affichent correctement même sans aucun profile.json (rétro-compat totale).
_PROFILE_DEFAULTS = {
    "metier": "restaurant",
    "agent": "Margot",
    "agent_initial": "M",
    "agent_role": "l'hôtesse vocale",
    # Voix Grok Voice par métier. Défaut = Camille (FR féminine). Surchargée
    # dans profile.json : ara/eve (féminines), rex/leo (masculines, pour Hugo/Paul).
    "voice": "69smp8rm",
    "secteur": "restaurant",
    "objet": "réservation",
    "objet_pluriel": "réservations",
    "action_verbe": "réserver",
    # SEO / meta
    "meta_title": "Démo Agent Vocal IA · Corsica Studio",
    "meta_description": "Parlez à Margot, l'hôtesse vocale IA d'un restaurant : renseignements, carte, horaires et réservation de table en direct. Une démo Corsica Studio.",
    "og_title": "Démo Agent Vocal IA · Corsica Studio",
    "og_description": "Margot répond au téléphone du restaurant : carte, horaires, réservations dans l'agenda. Faites le test en direct.",
    "og_image": "",
    # scène démo (téléphones + CTA)
    "hero_title": "Appelez le restaurant.",
    "hero_accent": "Margot décroche.",
    "hero_sub": "Une vraie conversation au téléphone d'un restaurant, une vraie réservation dans l'agenda. Parlez-lui naturellement.",
    "home_name": "Lou Patio",
    "home_tag": "Saint-Rémy-de-Provence",
    "home_btn_secondary": "Réserver",
    "call_header": "LOU PATIO",
    "cta_label": "Appeler le restaurant",
    "chip_1": "Essayez : <b>« Une table pour 4 samedi soir »</b>",
    "chip_2": "<b>« Quel est le plat signature ? »</b>",
    "chip_3": "<b>« Vous avez un parking ? »</b>",
    "showcase_title": "La Carte",
    "showcase_sub": "Chef Nathan Helo · Produits des Alpilles",
    "showcase_kind": "menu",      # "menu" = rendu carte resto ; "fiche" = rendu générique
    # photos des mockups téléphone (gauche = établissement, droite = vitrine/carte).
    # Neutres par secteur pour chaque métier ; défaut = resto. Voir index.html {{HOME_PHOTO}}/{{SHOWCASE_PHOTO}}.
    "home_photo": "/img/resto-salle.jpg",
    "showcase_photo": "/img/resto-plat.jpg",
    # argumentaire — carte 1 (les cartes 2 et 3 sont identiques sur tous les métiers)
    "card1_title": "Zéro appel manqué",
    "card1_bullets": "<li>Décroche à <b>chaque appel</b>, même en plein coup de feu, 24h/24 et 7j/7</li><li>Prend les réservations directement <b>dans votre agenda</b></li><li>Renseigne vos clients : horaires, carte, services, accès</li><li>Votre équipe reste concentrée sur les clients présents</li><li>Un client qui a sa réponse ne rappelle pas le concurrent</li>",
    # conversion (bas de page)
    "conversion_title": "Et si Margot répondait au téléphone de <span style=\"color:var(--accent)\">votre</span> restaurant ?",
    "conversion_text": "Cette page est une démonstration : Margot décroche à chaque appel, renseigne vos clients et remplit votre agenda, même en plein service. <b>Installation offerte, premier mois offert.</b>",
    "mailto_subject": "Agent%20vocal%20pour%20mon%20restaurant",
    # bulles d'outil (le {placeholder} est substitué dans voice.js)
    "bubbles": {
        "info_start": "{agent} consulte la carte et les informations du restaurant…",
        "check_start": "{agent} vérifie les disponibilités du {date} à {time}…",
        "book_start": "Enregistrement de la réservation au nom de {name} ({party} pers.)…",
        "book_confirmed": "Réservation enregistrée dans l'agenda du restaurant.",
        "book_full": "Créneau complet : {agent} propose une alternative.",
        "check_yes": "Des tables sont disponibles ({free} libre(s) sur ce créneau).",
        "check_no": "Créneau complet : {agent} cherche une alternative.",
        "error": "Petit souci technique côté agenda : {agent} s'adapte.",
        "end": "Fin d'appel demandée.",
    },
    "info_label": "Agenda",
    "recap_title": "Réservation confirmée",
    "recap_unit": "table pour",
    "recap_note": "Elle est déjà dans l'agenda du restaurant.",
    # agenda / réservation
    "event_summary_label": "Réservation",
    "calendar_note": "Prise par Margot (agent vocal Corsica Studio)",
    "calendar_id": "",            # vide → fallback RESTAURANT_CALENDAR_ID (env)
    "capacity_per_slot": CAPACITY_PER_SLOT,
    "slot_duration_min": TABLE_DURATION_MIN,
    # accroche d'ouverture (chemin Twilio)
    "greeting_instruction": "Salue en français, avec l'élégance chaleureuse d'une hôtesse de belle maison provençale. Ex : 'LOU PATIO, bonjour, Margot à votre écoute.' Une seule phrase, posée.",
}


def _metier_dir(metier: str) -> Path:
    """Dossier de config d'un métier (web/config/metiers/<metier>/) ou d'une
    entité du standard bi-marque (slug interne « entite/<e> » →
    web/config/entites/<e>/), avec fallback web/config/ si le dossier
    n'existe pas (rétro-compat pour le restaurant historique)."""
    if metier.startswith("entite/"):
        d = CONFIG_DIR / "entites" / metier.split("/", 1)[1]
    else:
        d = CONFIG_DIR / "metiers" / metier
    return d if d.exists() else CONFIG_DIR


def _entite_slug(entite: str | None) -> str | None:
    """Slug interne « entite/<e> » si la config de l'entité (cs|cd) existe
    dans web/config/entites/<e>/, sinon None (→ fallback config par défaut)."""
    e = (entite or "").strip().lower()
    return f"entite/{e}" if e and (CONFIG_DIR / "entites" / e).exists() else None


def _is_standard_host(host: str | None) -> bool:
    """True si le Host entrant est celui du standard bi-marque (STANDARD_HOSTS).
    Tout autre Host (démo web + démo Twilio) garde le comportement existant."""
    return (host or "").split(":")[0].strip().lower() in STANDARD_HOSTS


def _metier_exists(slug: str | None) -> str | None:
    slug = (slug or "").strip().lower()
    return slug if slug and (CONFIG_DIR / "metiers" / slug).exists() else None


def _resolve_metier(host: str | None, override: str | None = None) -> str:
    """Métier de la requête. Priorité : ?metier= (test local) >
    sous-domaine demo-<metier>.<base> > DEFAULT_METIER (demo.<base>, localhost, IP)."""
    cand = _metier_exists(override)
    if cand:
        return cand
    h = (host or "").split(":")[0].strip().lower()
    if h.startswith("demo-"):
        cand = _metier_exists(h[len("demo-"):].split(".")[0])
        if cand:
            return cand
    return DEFAULT_METIER


def _load_profile(metier: str) -> dict:
    """Profil UI/SEO/agenda du métier : valeurs par défaut (restaurant) écrasées
    par web/config/metiers/<metier>/profile.json. Hot-reloaded à chaque appel."""
    prof = json.loads(json.dumps(_PROFILE_DEFAULTS))  # copie profonde
    path = _metier_dir(metier) / "profile.json"
    if path.exists():
        try:
            override = json.loads(path.read_text(encoding="utf-8"))
            bubbles = dict(prof.get("bubbles", {}))
            bubbles.update(override.get("bubbles", {}))
            prof.update(override)
            prof["bubbles"] = bubbles
        except Exception as e:  # noqa: BLE001
            print(f"[profile] {metier} parse error: {e}")
    prof["metier"] = metier
    return prof


def _load_config(metier: str) -> dict:
    """Read system prompt + tools fresh from disk on every call, for one métier.
    Expands ${ENV_VAR} placeholders in tools.json via Template.safe_substitute
    (NB: os.path.expandvars on Windows breaks on apostrophes — don't use it)."""
    d = _metier_dir(metier)
    prompt_path = d / "system_prompt.txt"
    tools_path = d / "tools.json"
    instructions = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    instructions = instructions.replace("{{TODAY}}", _today_fr())
    prof = _load_profile(metier)
    # heure réelle + genre neutre + escalade humain + disclosure IA (tous métiers).
    # Standard cs/cd : pas de mention d'enregistrement (appels non enregistrés).
    # Surcharge par profil (profile.json "recorded": false) : la prospection
    # sortante n'est PAS enregistrée — ne pas dire le contraire au prospect.
    recorded_default = not metier.startswith("entite/")
    instructions += _runtime_rules(recorded=bool(prof.get("recorded", recorded_default)))
    # Multilingue : seulement les métiers du tourisme (profile.multilingual=true : hôtel, restaurant).
    if prof.get("multilingual"):
        instructions += (
            "\n- Tu es multilingue. Si l'appelant s'exprime dans une autre langue "
            "(anglais, espagnol, italien, allemand...), réponds naturellement et couramment "
            "DANS SA langue (essentiel dans le tourisme). Sinon, réponds en français."
        )
    if NOTIFY_ENABLED:
        instructions += (
            "\n- Pour transmettre une demande de rappel (tu n'as pas l'information "
            "demandée, ou tu ne peux pas finaliser le rendez-vous), recueille le nom, "
            "le numéro et le motif, rédige un résumé structuré de l'échange (ce que la "
            "personne veut précisément, le contexte, les infos déjà données), puis appelle "
            "l'outil prendre_message avec le champ resume rempli. La demande part aussitôt "
            "à l'équipe ; confirme alors à la personne qu'elle sera rappelée."
        )
    tools_raw = tools_path.read_text(encoding="utf-8") if tools_path.exists() else "[]"
    tools = json.loads(Template(tools_raw).safe_substitute(os.environ))
    if NOTIFY_ENABLED:
        tools = tools + [CALLBACK_TOOL]
    return {"instructions": instructions, "tools": tools}


def _load_business(metier: str) -> dict:
    """Fiche établissement (business.json, ou restaurant.json en fallback),
    hot-reloaded comme le prompt."""
    d = _metier_dir(metier)
    for fname in ("business.json", "restaurant.json"):
        p = d / fname
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {"error": "fiche établissement introuvable"}


def _metier_ctx(metier: str) -> dict:
    """Contexte agenda d'un métier (calendrier, capacité, durée, libellés),
    résolu depuis le profil avec fallback sur les variables d'env globales."""
    prof = _load_profile(metier)
    return {
        "metier": metier,
        "profile": prof,
        "calendar_id": prof.get("calendar_id") or RESTAURANT_CALENDAR_ID,
        "capacity": int(prof.get("capacity_per_slot") or CAPACITY_PER_SLOT),
        "duration": int(prof.get("slot_duration_min") or TABLE_DURATION_MIN),
        "summary_label": prof.get("event_summary_label") or "Réservation",
        "event_note": prof.get("calendar_note") or "",
        "telegram_chat_id": prof.get("telegram_chat_id") or TELEGRAM_CHAT_ID,
        "notify_email": prof.get("notify_email") or NOTIFY_EMAIL,
    }


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


async def _list_events_window(day_start: datetime, day_end: datetime, calendar_id: str) -> list[tuple[datetime, datetime]] | None:
    """Liste les réservations d'un calendrier sur une fenêtre. None = erreur API."""
    # Le slug Composio EVENTS_LIST accepte les paramètres style Google (camelCase) ;
    # fallback snake_case si la validation refuse.
    for args in (
        {"calendarId": calendar_id,
         "timeMin": day_start.isoformat(), "timeMax": day_end.isoformat(),
         "singleEvents": True, "maxResults": 250},
        {"calendar_id": calendar_id,
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


async def _check_availability(args: dict, *, calendar_id: str, capacity: int, duration_min: int) -> dict:
    """Disponibilité multi-places : un créneau est libre tant que moins de
    `capacity` réservations (durée `duration_min`) le chevauchent.
    Si complet : propose jusqu'à 2 alternatives dans le même service."""
    try:
        start = datetime.strptime(f"{args.get('date','')} {args.get('time','')}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return {"status": "error", "message": "Date ou heure invalide (attendu YYYY-MM-DD et HH:MM)."}
    duration = timedelta(minutes=duration_min)
    end = start + duration

    day_start = start.replace(hour=0, minute=0)
    day_end = day_start + timedelta(days=1)
    windows = await _list_events_window(day_start, day_end, calendar_id)
    if windows is None:
        return {"status": "error",
                "message": "Le livre de réservations est momentanément inaccessible. Propose qu'un membre de l'équipe rappelle."}

    booked = _count_overlaps(windows, start, end)
    free = max(0, capacity - booked)
    if free > 0:
        return {"status": "ok", "available": True, "tables_libres": free}

    # Complet : chercher des alternatives dans les fenêtres de service du jour.
    alternatives: list[str] = []
    for win_start, win_last in SERVICE_WINDOWS:
        t = datetime.strptime(f"{args.get('date','')} {win_start}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        last = datetime.strptime(f"{args.get('date','')} {win_last}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        while t <= last and len(alternatives) < 2:
            if t != start and _count_overlaps(windows, t, t + duration) < capacity:
                # privilégier les créneaux proches de la demande
                if abs((t - start).total_seconds()) <= 2 * 3600:
                    alternatives.append(t.strftime("%H:%M"))
            t += timedelta(minutes=30)
    return {"status": "ok", "available": False, "tables_libres": 0, "alternatives": alternatives}


async def _create_calendar_event(args: dict, *, calendar_id: str, capacity: int,
                                 duration_min: int, summary_label: str, event_note: str) -> dict:
    """Build the Google Calendar payload server-side (the model kept hallucinating
    fields like workingLocationProperties when given the raw schema) and POST to
    Composio. Returns a dict the voice agent can read back to the caller."""
    if not COMPOSIO_API_KEY:
        return {"status": "error", "message": "COMPOSIO_API_KEY not set"}
    # Reject obvious placeholder phones — otherwise the agent blindly saves
    # "anonymous" because Twilio sent it as the masked caller's From=.
    phone = str(args.get("phone") or "").strip()
    if phone.lower() in {"", "anonymous", "restricted", "unavailable", "unknown", "private", "none", "n/a"}:
        return {
            "status": "error",
            "message": "INVALID_PHONE: aucun numéro valide fourni — demande au client un vrai numéro de téléphone et rappelle book_reservation avec.",
        }
    # Garde anti-surbooking : re-vérifie la capacité juste avant de créer.
    avail = await _check_availability(args, calendar_id=calendar_id, capacity=capacity, duration_min=duration_min)
    if avail.get("status") == "ok" and not avail.get("available"):
        return {
            "status": "full",
            "message": "Ce créneau vient de se remplir.",
            "alternatives": avail.get("alternatives", []),
        }

    pers = args.get("party_size")
    suffix = f" ({pers} pers.)" if pers else ""
    body = await _composio_execute(COMPOSIO_EXEC_URL, {
        "calendar_id": calendar_id,
        "summary": f"{summary_label} : {args.get('name','?')}{suffix}",
        "description": f"Téléphone : {args.get('phone','?')}\nNotes : {args.get('notes') or '—'}\n{event_note}".rstrip(),
        "start_datetime": f"{args.get('date','')}T{args.get('time','')}:00",
        "event_duration_hour": duration_min // 60,
        "event_duration_minutes": duration_min % 60,
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


async def _notify_callback(ctx: dict, args: dict, *, dry_run: bool = False) -> dict:
    """Transmet une demande de rappel (nom + tel + motif) au pro via Telegram + copie
    email (Resend). Destinataires résolus par métier (profil) avec repli sur les vars
    d'env CS. `dry_run` formate le message SANS rien envoyer (test). Cf. CALLBACK_TOOL.
    Préparé mais inerte tant que l'agent n'appelle pas l'outil (NOTIFY_ENABLED off)."""
    prof = ctx.get("profile", {})
    etablissement = prof.get("home_name") or prof.get("secteur") or ctx.get("metier", "")
    nom = (args.get("nom") or args.get("name") or "").strip() or "(non précisé)"
    tel = (args.get("telephone") or args.get("phone") or "").strip() or "(non précisé)"
    motif = (args.get("motif") or args.get("message") or "").strip() or "(non précisé)"
    resume = (args.get("resume") or args.get("transcription") or "").strip()
    chat_id = ctx.get("telegram_chat_id") or TELEGRAM_CHAT_ID
    to_email = ctx.get("notify_email") or NOTIFY_EMAIL
    text = (f"[RAPPEL] {etablissement}\n"
            f"Nom : {nom}\n"
            f"Telephone : {tel}\n"
            f"Motif : {motif}\n"
            + (f"\nDemande detaillee :\n{resume}\n" if resume else "")
            + f"\nRecu : {_now_fr()}\n"
            "Demande captee par l'agent vocal : la personne attend un rappel.")
    out = {"telegram": None, "email": None,
           "payload": {"chat_id": chat_id, "to": to_email, "text": text}}
    if dry_run:
        return {"status": "dry_run", **out}
    if TELEGRAM_BOT_TOKEN and chat_id:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text})
            out["telegram"] = r.status_code
        except Exception as e:
            out["telegram"] = f"error: {e}"
    if RESEND_API_KEY and to_email:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                             "Content-Type": "application/json"},
                    json={"from": NOTIFY_FROM, "to": [to_email],
                          "subject": f"[Rappel] {etablissement} — {nom}",
                          "text": text, "html": text.replace(chr(10), "<br>")})
            out["email"] = r.status_code
        except Exception as e:
            out["email"] = f"error: {e}"
    ok = out["telegram"] == 200 or out["email"] == 200
    return {"status": "transmis" if ok else "error", **out}


# ---------------------------------------------------------------------------
# Standard bi-marque — tools A.3 (identify_caller, qualify_lead,
# request_callback, transfer_to_human) + webhook de fin d'appel.
# Airtable = base « Standard IA » : tables Contacts / Appels / Config.
# ---------------------------------------------------------------------------

def _standard_airtable_ready() -> bool:
    return bool(AIRTABLE_API_KEY and STANDARD_AIRTABLE_BASE_ID)


def _at_escape(v: str) -> str:
    """Échappe une valeur injectée dans une filterByFormula Airtable."""
    return str(v).replace("\\", "\\\\").replace("'", "\\'")


def _ctx_entite(ctx: dict) -> str:
    """« CS » / « CD » depuis le slug interne entite/<e>, sinon le métier brut."""
    m = str(ctx.get("metier") or "")
    return m.split("/", 1)[1].upper() if m.startswith("entite/") else m


def _is_standard_ctx(ctx: dict) -> bool:
    return str(ctx.get("metier") or "").startswith("entite/")


async def _airtable_request(method: str, table: str, *, record_id: str = "",
                            params: dict | None = None, payload: dict | None = None,
                            timeout: float = 6.0) -> dict | None:
    """Appel REST Airtable best-effort. None = échec (déjà loggé) — ne lève JAMAIS."""
    if not _standard_airtable_ready():
        return None
    url = f"https://api.airtable.com/v0/{STANDARD_AIRTABLE_BASE_ID}/{quote(table, safe='')}"
    if record_id:
        url += f"/{record_id}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(
                method, url,
                headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}",
                         "Content-Type": "application/json"},
                params=params, json=payload)
        if r.status_code >= 300:
            print(f"[standard] airtable {method} {table} → HTTP {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[standard] airtable {method} {table} failed: {e}")
        return None


async def _airtable_find_contact(phone: str) -> dict | None:
    """Première fiche Contacts dont {telephone} == phone. None si absente/échec."""
    body = await _airtable_request("GET", STANDARD_CONTACTS_TABLE, params={
        "filterByFormula": f"{{telephone}}='{_at_escape(phone)}'",
        "maxRecords": 1,
    })
    recs = (body or {}).get("records") or []
    return recs[0] if recs else None


async def _identify_caller(phone: str) -> dict:
    """Recherche le numéro appelant dans Airtable (table Contacts).
    Trouvé → {connu:true, nom, entite_habituelle, dernier_contact, notes}.
    Absent, masqué ou Airtable non configuré → {connu:false} (jamais d'exception)."""
    phone = (phone or "").strip()
    if not phone or phone.lower() in HIDDEN_CALLERS:
        return {"connu": False}
    if not _standard_airtable_ready():
        print("[standard] identify_caller : Airtable non configuré "
              "(AIRTABLE_API_KEY / STANDARD_AIRTABLE_BASE_ID) → accueil standard")
        return {"connu": False, "status": "non_configuré"}
    rec = await _airtable_find_contact(phone)
    if not rec:
        return {"connu": False}
    f = rec.get("fields", {})
    return {
        "connu": True,
        "nom": f.get("nom") or "",
        "entite_habituelle": f.get("entite_habituelle") or "",
        "dernier_contact": str(f.get("dernier_contact") or "")[:10],
        "notes": str(f.get("notes") or "")[:500],
    }


async def _upsert_contact(phone: str, fields: dict) -> None:
    """Crée / actualise la fiche Contacts (clé = telephone), notes en append.
    Best-effort : rien ne remonte à l'appel si Airtable est en panne."""
    phone = (phone or "").strip()
    if not phone or phone.lower() in HIDDEN_CALLERS or not _standard_airtable_ready():
        return
    fields = {k: v for k, v in fields.items() if v}
    fields["dernier_contact"] = datetime.now(TZ).strftime("%Y-%m-%d")
    rec = await _airtable_find_contact(phone)
    if rec:
        old_notes = str(rec.get("fields", {}).get("notes") or "")
        if fields.get("notes") and old_notes:
            fields["notes"] = (old_notes + "\n" + fields["notes"])[:2000]
        await _airtable_request("PATCH", STANDARD_CONTACTS_TABLE, record_id=rec["id"],
                                payload={"fields": fields, "typecast": True})
    else:
        fields["telephone"] = phone
        await _airtable_request("POST", STANDARD_CONTACTS_TABLE,
                                payload={"fields": fields, "typecast": True})


async def _log_call_row(fields: dict) -> None:
    """Ajoute une ligne à la table Appels (CRM des appels). Best-effort."""
    fields = {k: v for k, v in fields.items() if v not in ("", None)}
    fields.setdefault("date", datetime.now(TZ).isoformat())
    await _airtable_request("POST", STANDARD_CALLS_TABLE,
                            payload={"fields": fields, "typecast": True})


async def _qualify_lead(ctx: dict, args: dict) -> dict:
    """Tool qualify_lead : upsert Contacts + ligne Appels (intention=qualif).
    Écritures best-effort : un échec Airtable est loggé mais ne bloque pas l'appel."""
    if not _standard_airtable_ready():
        print("[standard] WARNING qualify_lead : Airtable non configuré")
        return {"status": "non_configuré",
                "message": "CRM indisponible : note la qualification dans les notes du rendez-vous ou du message."}
    entite = _ctx_entite(ctx)
    phone = (args.get("telephone") or ctx.get("caller_from") or "").strip()
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    note_bits = [f"[{stamp}] Qualification ({entite})"]
    for k in ("besoin", "type_projet", "delai", "canal_rappel", "budget"):
        if args.get(k):
            note_bits.append(f"{k} : {args[k]}")
    await _upsert_contact(phone, {
        "nom": (args.get("nom") or "").strip(),
        "entite_habituelle": entite,
        "notes": " · ".join(note_bits),
    })
    await _log_call_row({
        "entite": entite,
        "numero_appelant": phone,
        "nom": (args.get("nom") or "").strip(),
        "intention": "qualif",
        "besoin": args.get("besoin") or "",
        "type_projet": args.get("type_projet") or "",
        "delai": args.get("delai") or "",
        "canal_rappel": args.get("canal_rappel") or "",
        "budget": args.get("budget") or "",
    })
    return {"status": "ok"}


async def _request_callback(ctx: dict, args: dict) -> dict:
    """Tool request_callback : ligne Appels (intention=rappel) + notif Telegram/email
    via le mécanisme _notify_callback existant. Best-effort sur chaque canal."""
    entite = _ctx_entite(ctx)
    nom = (args.get("nom") or "").strip()
    tel = (args.get("telephone") or ctx.get("caller_from") or "").strip()
    creneau = (args.get("creneau_souhaite") or "").strip() or "dès que possible"
    can_notify = bool((TELEGRAM_BOT_TOKEN and (ctx.get("telegram_chat_id") or TELEGRAM_CHAT_ID))
                      or (RESEND_API_KEY and (ctx.get("notify_email") or NOTIFY_EMAIL)))
    if not (_standard_airtable_ready() or can_notify):
        print("[standard] WARNING request_callback : aucune sortie configurée (Airtable/Telegram/Resend)")
        return {"status": "non_configuré",
                "message": "Rappel non programmable automatiquement : confirme quand même à l'appelant "
                           "qu'il sera rappelé, sa demande est transcrite."}
    await _log_call_row({
        "entite": entite,
        "numero_appelant": tel,
        "nom": nom,
        "intention": "rappel",
        "message": f"Rappel souhaité : {creneau}",
        "statut": "à rappeler",
    })
    await _upsert_contact(tel, {
        "nom": nom,
        "entite_habituelle": entite,
        "notes": f"[{datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}] Demande de rappel ({creneau})",
    })
    notif = {"status": "skipped"}
    if can_notify:
        notif = await _notify_callback(ctx, {
            "nom": nom, "telephone": tel,
            "motif": f"[{entite}] Demande de rappel — créneau souhaité : {creneau}",
        })
    return {"status": "ok", "notification": notif.get("status")}


async def _transfer_available() -> bool:
    """Toggle « Vannina dispo » : env TRANSFER_ENABLED (1|0) prioritaire ; si la
    variable n'est PAS définie, repli optionnel sur Airtable table Config, champ
    `transfert_dispo` (checkbox, 1er enregistrement). Échec / rien → indisponible."""
    if TRANSFER_ENABLED:
        return TRANSFER_ENABLED.lower() in ("1", "true", "yes", "on")
    if _standard_airtable_ready():
        try:
            body = await asyncio.wait_for(
                _airtable_request("GET", STANDARD_CONFIG_TABLE,
                                  params={"maxRecords": 1}, timeout=2.0),
                timeout=2.5)
            recs = (body or {}).get("records") or []
            if recs:
                return bool(recs[0].get("fields", {}).get("transfert_dispo"))
        except Exception as e:  # noqa: BLE001
            print(f"[standard] lecture Config.transfert_dispo échouée: {e}")
    return False


async def _transfer_to_human(ctx: dict, args: dict) -> dict:
    """Tool transfer_to_human — vérifie SEULEMENT la faisabilité ici.
    Le <Dial> Twilio effectif est déclenché par la boucle de relais à
    response.done (flag pending_transfer), pour laisser l'agent annoncer la
    mise en relation AVANT que la redirection ne coupe le Media Stream."""
    if not _is_standard_ctx(ctx):
        return {"status": "indisponible",
                "message": "Transfert réservé au standard : propose un message ou un rappel."}
    if not (TRANSFER_NUMBER and _twilio_rest_auth() and TWILIO_ACCOUNT_SID and ctx.get("call_sid")):
        print("[standard] WARNING transfer_to_human : non configuré "
              "(TRANSFER_NUMBER / auth Twilio REST / call_sid)")
        return {"status": "non_configuré",
                "message": "Transfert impossible techniquement : propose un message ou un rappel."}
    if not await _transfer_available():
        return {"status": "indisponible",
                "message": "Vannina n'est pas joignable en ce moment : propose un message ou un rappel."}
    return {"status": "transfert",
            "message": "Annonce en UNE phrase courte que tu mets l'appelant en relation avec Vannina, puis attends."}


async def _twilio_transfer(call_sid: str, host: str, entite: str) -> None:
    """Transfert effectif : update REST du call avec un TwiML <Dial>.
    Comportement retenu (documenté) : <Say> mise en relation → <Dial timeout=20>
    vers TRANSFER_NUMBER → si non-réponse, <Say> « je reprends votre appel »
    puis <Redirect> ABSOLU vers /twilio/route?Digits=1|2 : l'appelant retombe
    directement sur l'agent de la MÊME entité (nouvelle session, sans repasser
    par l'IVR). NB : l'update REST termine le Media Stream courant — c'est
    attendu, le webhook de fin d'appel part quand même."""
    auth = _twilio_rest_auth()
    if not (TWILIO_ACCOUNT_SID and auth and call_sid and TRANSFER_NUMBER):
        print("[standard] transfert annulé : configuration Twilio incomplète")
        return
    digit = {"cs": "1", "cd": "2"}.get((entite or "").lower(), "1")
    back_url = f"https://{host}/twilio/route?Digits={digit}" if host else ""
    redirect = f'<Redirect method="POST">{back_url}</Redirect>' if back_url else "<Hangup/>"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        '<Say language="fr-FR" voice="Polly.Lea-Neural">Je vous mets en relation avec Vannina. Un instant, ne quittez pas.</Say>'
        f'<Dial timeout="{TRANSFER_DIAL_TIMEOUT}"><Number>{TRANSFER_NUMBER}</Number></Dial>'
        '<Say language="fr-FR" voice="Polly.Lea-Neural">Vannina n\'est pas joignable pour le moment. '
        "Je reprends votre appel pour noter un message.</Say>"
        f"{redirect}"
        "</Response>"
    )
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls/{call_sid}.json"
    try:
        async with httpx.AsyncClient(timeout=10, auth=auth) as client:
            r = await client.post(url, data={"Twiml": twiml})
        print(f"[standard] transfert Twilio déclenché vers {TRANSFER_NUMBER} (HTTP {r.status_code})")
    except Exception as e:  # noqa: BLE001
        print(f"[standard] transfert Twilio échoué: {e}")


async def _standard_call_webhook(ctx: dict) -> None:
    """Fin d'appel standard : POST best-effort du récap vers n8n
    (STANDARD_WEBHOOK_URL) — même pattern que _demo_webhook. Ne bloque jamais."""
    if not (STANDARD_WEBHOOK_URL and _is_standard_ctx(ctx)):
        return
    started = ctx.get("call_started_ts")
    duree = round((datetime.now(TZ) - started).total_seconds(), 1) if started else None
    payload = {
        "entite": _ctx_entite(ctx),
        "from": ctx.get("caller_from") or "",
        "duree_s": duree,
        "tools_appeles": ctx.get("tools_called") or [],
        "transcript": "\n".join(ctx.get("transcript") or [])[:4000],
        "call_sid": ctx.get("call_sid") or "",
        "ts": datetime.now(TZ).isoformat(),
        "source": "standard",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(STANDARD_WEBHOOK_URL, json=payload)
        print(f"[standard] webhook fin d'appel envoyé ({payload['entite']}, {duree}s)")
    except Exception as e:  # noqa: BLE001
        print(f"[standard] webhook fin d'appel échoué: {e}")


async def _is_opposed(tel: str) -> bool:
    """Le numéro figure-t-il au registre d'opposition ? Vérifie le registre
    local (usage.jsonl) PUIS Airtable (table Oppositions, best-effort : une
    panne / table absente ne bloque pas — déjà loggée par _airtable_request)."""
    tel = (tel or "").strip()
    if not tel:
        return False
    if tel in _local_oppositions():
        return True
    if _standard_airtable_ready():
        body = await _airtable_request("GET", OPPOSITIONS_TABLE, params={
            "filterByFormula": f"{{telephone}}='{_at_escape(tel)}'",
            "maxRecords": 1,
        })
        if body and (body.get("records") or []):
            return True
    return False


async def _marquer_opposition(ctx: dict, args: dict) -> dict:
    """Tool marquer_opposition (prospection sortante) : opt-out immédiat.
    Écrit {telephone, date, source} dans la table Airtable Oppositions
    (best-effort : table absente / 404 / panne → warning loggé, jamais
    d'exception) ET dans le registre local usage.jsonl (filet : l'opposition
    est respectée même si Airtable est down). Le statut renvoyé est TOUJOURS
    ok : côté agent, la personne doit être confirmée retirée puis l'appel
    raccroché, quoi qu'il arrive côté CRM."""
    tel = (args.get("telephone") or ctx.get("caller_from") or "").strip()
    date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    # 1) registre local, toujours (append-only, best-effort)
    _usage_append({"event": "opposition", "telephone": tel,
                   "source": "appel", "rid": ctx.get("rid") or ""})
    # 2) Airtable, best-effort
    if _standard_airtable_ready():
        body = await _airtable_request("POST", OPPOSITIONS_TABLE, payload={
            "fields": {"telephone": tel, "date": date_str, "source": "appel"},
            "typecast": True,
        })
        if body is None:
            print(f"[outbound] WARNING opposition {tel!r} non écrite dans Airtable "
                  f"(table {OPPOSITIONS_TABLE!r} absente ou panne) — registre local OK")
    else:
        print("[outbound] WARNING marquer_opposition : Airtable non configuré "
              "(AIRTABLE_API_KEY / STANDARD_AIRTABLE_BASE_ID) — registre local seul")
    print(f"[outbound] opposition enregistrée : {tel!r}")
    return {"status": "ok",
            "message": "Opposition enregistrée : cette personne ne sera plus jamais "
                       "rappelée. Confirme-le lui en UNE phrase, remercie, dis au revoir "
                       "et raccroche immédiatement (end_call), sans argumenter."}


async def _server_tool_call(name: str, args: dict, ctx: dict) -> dict:
    """Function-tool dispatcher for the Twilio path (no browser to handle them).
    Mirrors the FUNCTIONS map in voice.js — keep them in sync when adding tools.
    `ctx` carries the métier's calendar/capacity/labels (cf. _metier_ctx)."""
    if name == "book_reservation":
        return await _create_calendar_event(
            args, calendar_id=ctx["calendar_id"], capacity=ctx["capacity"],
            duration_min=ctx["duration"], summary_label=ctx["summary_label"],
            event_note=ctx["event_note"])
    if name == "check_availability":
        return await _check_availability(
            args, calendar_id=ctx["calendar_id"], capacity=ctx["capacity"],
            duration_min=ctx["duration"])
    if name in ("get_business_info", "get_restaurant_info"):
        return _load_business(ctx["metier"])
    if name == "get_restaurant_hours":  # compat legacy
        return _load_business(ctx["metier"]).get("horaires", RESTAURANT_HOURS)
    if name == "prendre_message":
        return await _notify_callback(ctx, args)
    # --- Tools du standard bi-marque (A.3) — exposés uniquement dans les
    # tools.json des entités cs/cd ; tous best-effort / non bloquants. --------
    if name == "identify_caller":
        # Normalement inutile : le pré-fetch au `start` Twilio injecte déjà
        # l'identité dans les instructions. Utile si l'agent veut vérifier un
        # AUTRE numéro donné oralement.
        return await _identify_caller(args.get("telephone") or ctx.get("caller_from") or "")
    if name == "qualify_lead":
        return await _qualify_lead(ctx, args)
    if name == "request_callback":
        return await _request_callback(ctx, args)
    if name == "transfer_to_human":
        # Vérifie la faisabilité ; le <Dial> effectif est déclenché à
        # response.done par la boucle de relais (flag pending_transfer).
        return await _transfer_to_human(ctx, args)
    if name == "marquer_opposition":
        # Prospection sortante (D.3) : opt-out immédiat, registre local +
        # Airtable Oppositions, best-effort — voir _marquer_opposition.
        return await _marquer_opposition(ctx, args)
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
    auth = _twilio_rest_auth()
    if not (TWILIO_ACCOUNT_SID and auth and call_sid):
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls/{call_sid}.json"
    try:
        async with httpx.AsyncClient(timeout=10, auth=auth) as client:
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

async def _demo_webhook(lead: str, metier: str) -> None:
    """Notifie n8n (WF-13) qu'un prospect identifié lance une démo. Best-effort :
    ne jamais bloquer le mint de token à cause du webhook."""
    if not (DEMO_WEBHOOK_URL and lead):
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(DEMO_WEBHOOK_URL, json={
                "lead": lead,
                "metier": metier,
                "ts": datetime.now(TZ).isoformat(),
                "source": "browser",
            })
    except Exception as e:  # noqa: BLE001
        print(f"[demo] webhook failed: {e}")


@app.post("/token")
async def mint_token(request: Request) -> JSONResponse:
    if not XAI_API_KEY:
        raise HTTPException(500, "XAI_API_KEY is not set. Add it to .env")
    # Lead optionnel transmis par la SPA (lien email ...?lead=recXXX).
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    lead = str((payload or {}).get("lead") or "").strip()[:40]
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
    metier = _resolve_metier(request.headers.get("host"), request.query_params.get("metier"))
    _usage_append({"event": "start", "path": "browser", "metier": metier, **({"lead": lead} if lead else {})})
    if lead:
        await _demo_webhook(lead, metier)
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
    by_lead: dict[str, int] = {}
    by_metier: dict[str, int] = {}
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
                lead = e.get("lead")
                if lead:
                    by_lead[lead] = by_lead.get(lead, 0) + 1
                m = e.get("metier")
                if m:
                    by_metier[m] = by_metier.get(m, 0) + 1
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
        "par_lead": dict(sorted(by_lead.items(), key=lambda kv: -kv[1])),
        "par_metier": dict(sorted(by_metier.items(), key=lambda kv: -kv[1])),
        "sessions_identifiees": sum(by_lead.values()),
        "note": "Estimation côté serveur (le solde exact reste sur console.x.ai du compte équipe).",
    }


@app.get("/usage")
async def usage_report(key: str = "") -> JSONResponse:
    if key != USAGE_TOKEN:
        raise HTTPException(403, "clé d'accès invalide (paramètre ?key=)")
    return JSONResponse(_aggregate_usage())


@app.get("/config")
async def get_config(request: Request) -> JSONResponse:
    metier = _resolve_metier(request.headers.get("host"), request.query_params.get("metier"))
    return JSONResponse(_load_config(metier))


class Reservation(BaseModel):
    name: str
    phone: str
    date: str         # YYYY-MM-DD
    time: str         # HH:MM (24h)
    party_size: int = 1   # défaut 1 : métiers sans notion de groupe (artisan, médical, immo, beauté) n'envoient pas ce champ
    notes: str = ""


@app.post("/api/calendar/book")
async def book(res: Reservation, request: Request) -> JSONResponse:
    ctx = _metier_ctx(_resolve_metier(request.headers.get("host"), request.query_params.get("metier")))
    return JSONResponse(await _create_calendar_event(
        res.model_dump(), calendar_id=ctx["calendar_id"], capacity=ctx["capacity"],
        duration_min=ctx["duration"], summary_label=ctx["summary_label"],
        event_note=ctx["event_note"]), status_code=200)


class CallbackMessage(BaseModel):
    nom: str = ""
    telephone: str = ""
    motif: str = ""


@app.post("/api/message")
async def take_message(msg: CallbackMessage, request: Request) -> JSONResponse:
    """Demande de rappel (escalade). Transmet au pro via Telegram + email.
    Préparé mais inerte tant que l'agent ne dispose pas de l'outil prendre_message
    (NOTIFY_ENABLED off) ; l'endpoint répond quand même si appelé directement."""
    ctx = _metier_ctx(_resolve_metier(request.headers.get("host"), request.query_params.get("metier")))
    return JSONResponse(await _notify_callback(ctx, msg.model_dump()), status_code=200)


class AvailabilityQuery(BaseModel):
    date: str         # YYYY-MM-DD
    time: str         # HH:MM (24h)
    party_size: int = 2


@app.post("/api/calendar/availability")
async def availability(q: AvailabilityQuery, request: Request) -> JSONResponse:
    ctx = _metier_ctx(_resolve_metier(request.headers.get("host"), request.query_params.get("metier")))
    return JSONResponse(await _check_availability(
        q.model_dump(), calendar_id=ctx["calendar_id"], capacity=ctx["capacity"],
        duration_min=ctx["duration"]), status_code=200)


@app.get("/api/restaurant")   # alias historique appelé par voice.js
@app.get("/api/business")
async def business_info(request: Request) -> JSONResponse:
    metier = _resolve_metier(request.headers.get("host"), request.query_params.get("metier"))
    return JSONResponse(_load_business(metier))


@app.get("/api/profile")
async def profile_info(request: Request) -> JSONResponse:
    metier = _resolve_metier(request.headers.get("host"), request.query_params.get("metier"))
    return JSONResponse(_load_profile(metier))


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
    form = await request.form()
    caller_from = (form.get("From") or "").strip()

    if _is_standard_host(host):
        # Mode standard bi-marque : accueil court puis IVR DTMF à 2 branches.
        # Le choix est POSTé par Twilio sur /twilio/route qui ouvre le Media
        # Stream avec l'entité. Sans choix (timeout), le <Redirect> repose la
        # question. La déclaration IA est faite par CHAQUE agent d'entité dès
        # son greeting (après le choix 1/2), pas ici. Consignes Vannina :
        # jamais le nom de famille prononcé (la TTS le massacre) — prénom seul ;
        # l'appel n'est PAS enregistré — si l'enregistrement est activé un jour,
        # REMETTRE ICI l'annonce légale (« cet appel est enregistré ») avant le <Gather>.
        print(f"[standard] appel entrant host={host!r} from={caller_from!r}")
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Gather input="dtmf" numDigits="1" timeout="6" action="/twilio/route" method="POST">'
            '<Say language="fr-FR" voice="Polly.Lea-Neural">'
            "Bonjour, vous êtes bien chez Vannina. "
            "Pour Corsica Studio, tapez 1. "
            "Pour Corsica Design, tapez 2."
            '</Say>'
            '</Gather>'
            '<Redirect>/twilio/voice</Redirect>'
            '</Response>'
        )
        return Response(content=twiml, media_type="application/xml")

    ws_url = f"wss://{host}/twilio/stream"
    param_xml = f'<Parameter name="from" value="{caller_from}" />' if caller_from else ""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Connect><Stream url="{ws_url}">{param_xml}</Stream></Connect>'
        '</Response>'
    )
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/route")
async def twilio_route(request: Request) -> Response:
    """IVR du standard bi-marque : Twilio POSTe ici le choix DTMF du <Gather>.
    Digits 1 → entité `cs` (Corsica Studio), 2 → entité `cd` (Corsica Design) ;
    tout autre choix repose la question (redirect /twilio/voice). Ouvre alors
    le Media Stream avec l'entité et le numéro appelant en <Parameter> — lus
    au `start` du WS /twilio/stream (même mécanisme que `from` aujourd'hui)."""
    host = request.headers.get("host") or request.url.hostname or "example.com"
    form = await request.form()
    # Digits en query = ré-entrée directe sur une entité SANS repasser par
    # l'IVR (utilisé par le <Redirect> post-<Dial> de transfer_to_human).
    digits = (form.get("Digits") or request.query_params.get("Digits") or "").strip()
    caller_from = (form.get("From") or "").strip()
    entite = {"1": "cs", "2": "cd"}.get(digits)
    if not entite:
        print(f"[standard] choix DTMF invalide digits={digits!r} → on repose la question")
        twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                 '<Response><Redirect>/twilio/voice</Redirect></Response>')
        return Response(content=twiml, media_type="application/xml")
    print(f"[standard] route digits={digits!r} → entite={entite!r} from={caller_from!r}")
    ws_url = f"wss://{host}/twilio/stream"
    param_from = f'<Parameter name="from" value="{caller_from}" />' if caller_from else ""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Connect><Stream url="{ws_url}">'
        f'<Parameter name="entite" value="{entite}" />{param_from}'
        '</Stream></Connect>'
        '</Response>'
    )
    return Response(content=twiml, media_type="application/xml")


# ---------------------------------------------------------------------------
# Prospection sortante (D.3) — POST /outbound/call + /twilio/voice-out
# ---------------------------------------------------------------------------

def _xml_attr(v: str) -> str:
    """Assainit une valeur injectée dans un attribut TwiML (rid / numéro)."""
    return "".join(ch for ch in str(v or "") if ch.isalnum() or ch in "+@._- ")[:80]


def _outbound_prospect_block(prospect: dict, to: str) -> str:
    """Bloc [Appel SORTANT] injecté dans les instructions avant response.create
    (même mécanique que l'accueil personnalisé du standard). Donne à Léa le
    contexte prospect (nom, entreprise, secteur, ville) + le numéro appelé."""
    lines = ["\n\n[Appel SORTANT — contexte prospect]",
             "Tu es en train d'APPELER ce professionnel (appel sortant B2B) : "
             "c'est TOI qui appelles, ne dis jamais « merci de votre appel »."]
    nom = str(prospect.get("nom") or "").strip()
    entreprise = str(prospect.get("entreprise") or "").strip()
    secteur = str(prospect.get("secteur") or "").strip()
    ville = str(prospect.get("ville") or "").strip()
    if nom:
        lines.append(f"Interlocuteur attendu : {nom}.")
    if entreprise:
        lines.append(f"Entreprise : {entreprise}.")
    if secteur:
        lines.append(f"Secteur d'activité : {secteur} — adapte ton pitch et tes "
                     "exemples à CE secteur (fiche get_business_info, par_profession).")
    if ville:
        lines.append(f"Ville : {ville}.")
    if to:
        lines.append(f"Le numéro appelé (celui du prospect) est : {to}. C'est son "
                     "numéro de rappel par défaut pour qualify_lead, book_reservation "
                     "et marquer_opposition : ne le redemande pas.")
    if not (nom or entreprise):
        lines.append("Aucune fiche prospect chargée : reste générique et demande "
                     "poliment à qui tu t'adresses avant le pitch.")
    return "\n".join(lines)


async def _twilio_call_create(to: str, from_number: str, url: str) -> dict:
    """POST Twilio REST /Calls.json (appel sortant). Retourne le JSON Twilio
    ou {"error": ...}. Isolé pour être mockable dans les tests."""
    auth = _twilio_rest_auth()
    if not (TWILIO_ACCOUNT_SID and auth):
        return {"error": "Twilio REST non configuré (TWILIO_ACCOUNT_SID / auth)"}
    api = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json"
    try:
        async with httpx.AsyncClient(timeout=15, auth=auth) as client:
            r = await client.post(api, data={
                "To": to, "From": from_number,
                "Url": url, "Method": "POST",
                "Timeout": "25",
            })
        body = r.json()
        if r.status_code >= 300:
            return {"error": f"HTTP {r.status_code}: {str(body)[:300]}"}
        return body
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e!r}"}


@app.post("/outbound/call")
async def outbound_call(request: Request) -> JSONResponse:
    """Compose un appel sortant de prospection B2B (appelé par n8n WF-OUT).
    Body : {"to": "+33...", "prospect": {nom, entreprise, secteur, ville, record_id}}.
    Garde-fous NON contournables, dans l'ordre : token, horaires ouvrés,
    numéro français, registre d'opposition. AUCUN appel ne part hors cadre."""
    # 1) Auth — header X-Outbound-Token == env OUTBOUND_TOKEN (fail closed).
    if not OUTBOUND_TOKEN:
        print("[outbound] refus : OUTBOUND_TOKEN non configuré côté serveur")
        return JSONResponse({"status": "non_configuré",
                             "message": "OUTBOUND_TOKEN absent du .env"}, status_code=403)
    if request.headers.get("x-outbound-token", "") != OUTBOUND_TOKEN:
        return JSONResponse({"status": "refus", "message": "token invalide"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    prospect = dict((payload or {}).get("prospect") or {})
    rid = str(prospect.get("record_id") or "").strip()[:40]

    # 2) Horaires ouvrés B2B (lun-ven, plages OUTBOUND_HOURS, Europe/Paris).
    if not _outbound_hours_ok():
        print(f"[outbound] refus hors_horaires (rid={rid!r}, plages={OUTBOUND_HOURS!r})")
        return JSONResponse({"status": "hors_horaires",
                             "plages": OUTBOUND_HOURS,
                             "message": "appels autorisés lun-ven sur les plages configurées"},
                            status_code=423)

    # 3) Numéro français uniquement.
    to = _normalize_fr_phone(str((payload or {}).get("to") or ""))
    if not to:
        return JSONResponse({"status": "numero_invalide",
                             "message": "numéro français attendu (+33XXXXXXXXX ou 0XXXXXXXXX)"},
                            status_code=400)

    # 4) Registre d'opposition (local + Airtable, best-effort).
    if await _is_opposed(to):
        print(f"[outbound] refus opposition {to!r} (rid={rid!r})")
        return JSONResponse({"status": "opposition",
                             "message": "numéro au registre d'opposition : ne jamais rappeler"},
                            status_code=403)

    # 5) Compose l'appel : Twilio rappellera /twilio/voice-out?rid=… (TwiML).
    host = OUTBOUND_PUBLIC_HOST or (request.headers.get("host") or "").split(":")[0]
    if not host:
        return JSONResponse({"status": "non_configuré",
                             "message": "host public introuvable (OUTBOUND_PUBLIC_HOST)"},
                            status_code=503)
    url = f"https://{host}/twilio/voice-out" + (f"?rid={quote(rid)}" if rid else "")
    body = await _twilio_call_create(to, OUTBOUND_FROM_NUMBER, url)
    if body.get("error"):
        print(f"[outbound] calls.create échoué : {body['error']}")
        return JSONResponse({"status": "erreur_twilio", "message": body["error"]},
                            status_code=502)
    call_sid = str(body.get("sid") or "")

    # 6) Contexte prospect en mémoire (rid ET CallSid) pour le WS + tracking.
    prospect["to"] = to
    _outbound_ctx_put(rid, prospect)
    _outbound_ctx_put(call_sid, prospect)
    _usage_append({"event": "start", "path": "outbound", "metier": OUTBOUND_METIER,
                   "to": to, **({"lead": rid} if rid else {})})
    print(f"[outbound] appel lancé → {to} (rid={rid!r}, call_sid={call_sid!r})")
    return JSONResponse({"status": "lancé", "call_sid": call_sid, "to": to, "rid": rid})


@app.post("/twilio/voice-out")
async def twilio_voice_out(request: Request) -> Response:
    """Webhook TwiML de l'appel SORTANT (Url du calls.create) : ouvre le Media
    Stream vers /twilio/stream avec le métier prospection, le rid (fiche
    prospect en mémoire), la direction et le numéro appelé en <Parameter>."""
    host = request.headers.get("host") or request.url.hostname or "example.com"
    form = await request.form()
    to = _xml_attr(form.get("To") or "")          # numéro du prospect (Twilio POSTe To=)
    rid = _xml_attr(request.query_params.get("rid") or "")
    print(f"[outbound] voice-out host={host!r} to={to!r} rid={rid!r}")
    ws_url = f"wss://{host}/twilio/stream"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Connect><Stream url="{ws_url}">'
        f'<Parameter name="metier" value="{_xml_attr(OUTBOUND_METIER)}" />'
        f'<Parameter name="direction" value="out" />'
        f'<Parameter name="rid" value="{rid}" />'
        f'<Parameter name="to" value="{to}" />'
        '</Stream></Connect>'
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

    # --- Handshake xAI lancé EN PARALLÈLE de la pré-lecture Twilio ---------
    # (recette Léa : silence au décroché, sortant compris.) L'URL et la clé
    # ne dépendent ni du métier ni du `start` Twilio : on ouvre la session
    # xAI dès l'accept du WS, pendant qu'on attend le `start`. Le handshake
    # TLS+WS xAI sort ainsi du chemin critique avant le premier mot. Côté
    # outbound, le contexte prospect vient de la mémoire process
    # (_outbound_ctx_get) : AUCUN I/O bloquant avant le response.create.
    xai_url = f"{XAI_REALTIME_WS}?model={MODEL}"
    xai_headers = {"Authorization": f"Bearer {XAI_API_KEY}"}

    async def _xai_connect():
        return await websockets.connect(
            xai_url, additional_headers=xai_headers, max_size=None)

    xai_connect_task = asyncio.create_task(_xai_connect())

    async def _xai_abort() -> None:
        """Annule (ou ferme) le handshake xAI si l'appel meurt avant `start`."""
        xai_connect_task.cancel()
        try:
            conn = await xai_connect_task
            await conn.close()
        except Exception:  # noqa: BLE001 — annulé ou handshake raté : rien à fermer
            pass

    metier = _resolve_metier(ws.headers.get("host"))
    ctx = _metier_ctx(metier)
    config = _load_config(metier)
    print(f"[twilio] métier résolu = {metier!r}")
    stream_sid: str | None = None
    call_sid: str | None = None
    pending_end_call = False
    # Transfert vers Vannina (standard) : armé par transfer_to_human, exécuté
    # à response.done pour laisser l'agent annoncer la mise en relation.
    pending_transfer = False

    # --- Pré-lecture Twilio jusqu'à l'événement `start` --------------------
    # Twilio envoie `connected` puis `start` quelques millisecondes après
    # l'ouverture du WS. On lit ces événements AVANT le handshake xAI : on
    # connaît ainsi l'appelant (customParameters) tout de suite, ce qui permet
    # de lancer le lookup Airtable identify_caller EN PARALLÈLE de l'ouverture
    # de la session xAI au lieu de tout sérialiser (latence perçue avant le
    # premier mot de l'assistante après le choix 1/2).
    start_evt: dict | None = None
    try:
        while start_evt is None:
            raw = await ws.receive_text()
            evt = json.loads(raw)
            kind = evt.get("event")
            if kind == "start":
                start_evt = evt
            elif kind == "stop":
                print("[twilio] stop reçu avant start — fermeture")
                await _xai_abort()
                await ws.close()
                return
            # `connected` (et tout autre événement pré-start) : ignoré.
    except WebSocketDisconnect:
        print("[twilio] client disconnected avant start")
        await _xai_abort()
        return

    stream_sid = start_evt["start"]["streamSid"]
    call_sid = start_evt["start"].get("callSid")
    custom = start_evt["start"].get("customParameters") or {}
    caller_from = (custom.get("from") or "").strip()
    print(f"[twilio] start streamSid={stream_sid} callSid={call_sid} from={caller_from!r}")

    # Standard bi-marque : si l'IVR a transmis une entité (Parameter
    # entite=cs|cd via /twilio/route), la config vient de
    # web/config/entites/<entite>/ au lieu du métier résolu par Host.
    # Fallback : dossier absent → config par défaut inchangée + warning.
    entite_param = (custom.get("entite") or "").strip().lower()
    if entite_param:
        slug = _entite_slug(entite_param)
        if slug:
            metier = slug
            ctx = _metier_ctx(slug)
            config = _load_config(slug)
            print(f"[standard] entité résolue = {entite_param!r} (config {slug!r})")
        else:
            print(f"[standard] WARNING config entités absente pour {entite_param!r} → config par défaut ({metier!r})")

    # Prospection sortante (D.3) : /twilio/voice-out transmet metier=prospection,
    # direction=out, rid (fiche prospect en mémoire) et to (numéro appelé).
    # Le Parameter metier prime sur le Host — l'appel sortant part du webhook,
    # pas d'un sous-domaine démo. Dossier métier absent → config par défaut + warning.
    direction = (custom.get("direction") or "in").strip().lower()
    metier_param = (custom.get("metier") or "").strip().lower()
    out_rid = (custom.get("rid") or "").strip()
    out_to = (custom.get("to") or "").strip()
    if metier_param and not entite_param:
        m2 = _metier_exists(metier_param)
        if m2:
            metier = m2
            ctx = _metier_ctx(m2)
            config = _load_config(m2)
            print(f"[outbound] métier forcé par Parameter = {m2!r} (direction={direction!r})")
        else:
            print(f"[outbound] WARNING métier {metier_param!r} inconnu → config par défaut ({metier!r})")
    if direction == "out":
        ctx["direction"] = "out"
        ctx["rid"] = out_rid
        # Sortant : la « personne au bout du fil » est le prospect appelé —
        # son numéro sert de défaut aux tools (rappel, opposition, RDV).
        caller_from = out_to

    # Contexte partagé avec les tools server-side (A.3) et le webhook de
    # fin d'appel. Posé APRÈS la résolution d'entité (ctx vient d'être
    # rebindé pour le standard).
    ctx["call_sid"] = call_sid
    ctx["caller_from"] = caller_from
    ctx["call_started_ts"] = datetime.now(TZ)
    ctx["public_host"] = (ws.headers.get("host") or "").split(":")[0]

    # Standard bi-marque : pré-fetch identify_caller lancé EN TÂCHE DE FOND
    # dès le `start` (archi §5bis), en parallèle du handshake xAI. Son
    # résultat est attendu au plus 300 ms au moment de composer les
    # instructions ; au-delà → accueil standard SANS bloquer (le lookup
    # continue en arrière-plan mais son résultat est ignoré pour cet appel).
    # Échec ou timeout : SILENCIEUX, jamais bloquant.
    identify_task: asyncio.Task | None = None
    if _is_standard_ctx(ctx) and caller_from.lower() not in HIDDEN_CALLERS:
        async def _identify_caller_bg(phone: str) -> dict:
            try:
                return await asyncio.wait_for(_identify_caller(phone), timeout=1.5) or {}
            except Exception:  # noqa: BLE001 — timeout ou panne : accueil standard
                return {}
        identify_task = asyncio.create_task(_identify_caller_bg(caller_from))

    try:
        # Le handshake xAI a couru pendant la pré-lecture du `start` Twilio
        # (et la résolution métier/entité) : on ne fait que le récupérer ici.
        async with await xai_connect_task as xai:

            # --- Instructions + session.update + greeting -------------------
            # Envoyés dès l'ouverture de la session xAI : le `start` Twilio a
            # déjà été lu ci-dessus (le lookup Airtable a donc tourné pendant
            # le handshake xAI, pas après).
            instructions = config["instructions"]
            # Appel SORTANT (prospection D.3) : pas de logique CallerID entrant —
            # on injecte à la place la fiche prospect posée par /outbound/call
            # (même mécanique que l'accueil personnalisé du standard : le
            # contexte entre dans les instructions AVANT le response.create).
            if direction == "out":
                prospect = _outbound_ctx_get(out_rid) or _outbound_ctx_get(call_sid or "")
                instructions += _outbound_prospect_block(prospect, out_to)
                if prospect:
                    print(f"[outbound] contexte prospect injecté (rid={out_rid!r}) : "
                          f"{prospect.get('entreprise') or prospect.get('nom') or '?'}")
                else:
                    print(f"[outbound] WARNING aucune fiche prospect en mémoire (rid={out_rid!r})")
            # Twilio sends literal strings like "anonymous" / "restricted"
            # / "unavailable" when the caller's number is hidden. Treat
            # them as "no CallerID" — otherwise the model passes the
            # literal "anonymous" as the phone field.
            elif caller_from.lower() in HIDDEN_CALLERS:
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

            # Résultat du pré-fetch identify_caller : attente plafonnée à
            # 300 ms (la tâche a déjà eu la durée du handshake xAI pour
            # aboutir). asyncio.shield → le timeout n'annule pas la tâche
            # de fond, il la laisse simplement finir dans le vide.
            if identify_task is not None:
                caller_info: dict = {}
                try:
                    caller_info = await asyncio.wait_for(
                        asyncio.shield(identify_task), timeout=0.3) or {}
                except Exception:  # noqa: BLE001 — > 300 ms : accueil standard
                    print("[standard] identify_caller > 300 ms → accueil standard (résultat ignoré pour cet appel)")
                if caller_info.get("connu"):
                    nom = caller_info.get("nom") or ""
                    extras = []
                    if caller_info.get("entite_habituelle"):
                        extras.append(f"entité habituelle : {caller_info['entite_habituelle']}")
                    if caller_info.get("dernier_contact"):
                        extras.append(f"dernier contact : {caller_info['dernier_contact']}")
                    if caller_info.get("notes"):
                        extras.append(f"notes : {caller_info['notes']}")
                    instructions += (
                        "\n\n[Appelant identifié]\n"
                        f"Le numéro appelant correspond à un contact connu : {nom}"
                        + (f" ({' ; '.join(extras)})" if extras else "")
                        + ". Salue cette personne NOMINATIVEMENT dès l'ouverture "
                        f"(ex. « Bonjour {nom}, ravie de vous réentendre »), ne "
                        "redemande ni son nom ni son numéro, et utilise ce numéro "
                        "comme numéro de rappel par défaut."
                    )
                    print(f"[standard] appelant identifié : {nom!r}")

            # Langue Whisper par métier (profile.whisper_language) :
            # absent/"fr" = pin fr (comportement historique, évite les
            # dérives Hindi/Portugais) ; "auto" = pas de pin, détection
            # multilingue (ex. hotel-international FR/EN/IT/DE).
            whisper_lang = str(
                ctx["profile"].get("whisper_language") or "fr"
            ).strip().lower()
            transcription = {"model": "whisper-1"}
            if whisper_lang != "auto":
                transcription["language"] = whisper_lang
            # VAD par métier (profile.vad_silence_ms) : durée de silence (ms)
            # avant que le serveur considère le tour de parole terminé.
            # Absent ou invalide → {"type": "server_vad"} nu, strictement le
            # comportement historique (rétro-compatible). Prospection : valeur
            # plus réactive pour réduire la latence entre les tours.
            turn_detection: dict = {"type": "server_vad"}
            vad_ms = ctx["profile"].get("vad_silence_ms")
            if vad_ms is not None:
                try:
                    turn_detection["silence_duration_ms"] = int(vad_ms)
                    print(f"[twilio] vad silence_duration_ms={turn_detection['silence_duration_ms']} (profil {metier!r})")
                except (TypeError, ValueError):
                    print(f"[twilio] WARNING vad_silence_ms invalide ignoré : {vad_ms!r}")
            await xai.send(json.dumps({
                "type": "session.update",
                "session": {
                    "voice": ctx["profile"].get("voice") or VOICE,
                    "instructions": instructions,
                    "tools": config["tools"],
                    "turn_detection": turn_detection,
                    "input_audio_transcription": transcription,
                    "audio": {
                        "input":  {"format": {"type": "audio/pcmu"}},
                        "output": {"format": {"type": "audio/pcmu"}},
                    },
                },
            }))

            # Trigger an opening greeting — Twilio doesn't speak first.
            # (Sortant aussi : c'est l'agent qui parle en premier au décroché.)
            greeting = ctx["profile"].get(
                "greeting_instruction", _PROFILE_DEFAULTS["greeting_instruction"])
            if direction == "out":
                prospect = _outbound_ctx_get(out_rid) or _outbound_ctx_get(call_sid or "")
                who = ", ".join(x for x in (str(prospect.get("nom") or "").strip(),
                                            str(prospect.get("entreprise") or "").strip()) if x)
                if who:
                    greeting += f" Tu appelles : {who}."
            await xai.send(json.dumps({
                "type": "response.create",
                "response": {"instructions": greeting},
            }))

            async def twilio_to_xai() -> None:
                """Forwards Twilio media frames to xAI (le `start` a déjà été
                consommé avant le handshake xAI ; ici il ne reste que
                media/stop)."""
                try:
                    while True:
                        raw = await ws.receive_text()
                        evt = json.loads(raw)
                        kind = evt.get("event")
                        if kind == "media":
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
                nonlocal pending_end_call, pending_transfer
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
                                    # métiers multilingues (hotel-international) :
                                    # EN / IT / DE, jamais prononcés par les agents
                                    # francophones → aucun impact sur l'existant.
                                    "goodbye", "good bye", "have a lovely",
                                    "have a nice", "thank you for calling",
                                    "arrivederci", "buona giornata", "buona serata",
                                    "a presto", "auf wiederhören", "auf wiedersehen",
                                    "schönen tag noch", "einen schönen",
                                )
                                if not pending_end_call and any(g in low for g in GOODBYES):
                                    print("[twilio] auto-hangup armed (goodbye in transcript)")
                                    pending_end_call = True
                                if _is_standard_ctx(ctx):
                                    ctx.setdefault("transcript", []).append(f"agent : {transcript}")
                        elif t == "conversation.item.input_audio_transcription.completed":
                            transcript = (evt.get("transcript") or "").replace("\n", " ").strip()
                            if transcript:
                                print(f"[caller] {transcript}")
                                if _is_standard_ctx(ctx):
                                    ctx.setdefault("transcript", []).append(f"appelant : {transcript}")
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
                        result = await _server_tool_call(name, args, ctx)
                        print(f"[tool] ← {name} → {result}")
                        if _is_standard_ctx(ctx):
                            ctx.setdefault("tools_called", []).append(name)
                        if name == "end_call":
                            pending_end_call = True
                        if name == "transfer_to_human" and result.get("status") == "transfert":
                            pending_transfer = True
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
                        if pending_transfer:
                            # L'agent a annoncé la mise en relation : on redirige
                            # maintenant le call vers le <Dial>. L'update REST coupe
                            # le Media Stream courant (attendu) — le webhook de fin
                            # d'appel part dans le finally.
                            print("[standard] transfer_to_human → redirection Twilio (Dial)")
                            await asyncio.sleep(1.0)
                            await _twilio_transfer(
                                call_sid or "",
                                ctx.get("public_host") or "",
                                _ctx_entite(ctx).lower())
                            return
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
        # Standard bi-marque : récap de fin d'appel → n8n (best-effort, no-op
        # hors standard ou sans STANDARD_WEBHOOK_URL).
        try:
            await _standard_call_webhook(ctx)
        except Exception as e:  # noqa: BLE001
            print(f"[standard] webhook fin d'appel (finally) échoué: {e}")
        try:
            await ws.close()
        except Exception:
            pass
        print("[twilio] WS closed")


# ---------------------------------------------------------------------------
# Static SPA (must come last because of the catch-all "/" mount)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Serve index.html for the resolved métier: inject the profile (text
    placeholders {{KEY}} + window.__PROFILE__ for voice.js) and ?v=<mtime>
    cache-busters on voice.js / style.css."""
    metier = _resolve_metier(request.headers.get("host"), request.query_params.get("metier"))
    profile = _load_profile(metier)
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    # 1) placeholders texte {{KEY}} (les valeurs non-chaînes, ex. bubbles, sont ignorées)
    for key, val in profile.items():
        if isinstance(val, str):
            html = html.replace("{{" + key.upper() + "}}", val)
    # 2) profil complet exposé à voice.js (agent, objet, bulles d'outil…)
    inject = "<script>window.__PROFILE__=" + json.dumps(profile, ensure_ascii=False) + ";</script>"
    html = html.replace("</head>", inject + "</head>", 1)
    # 3) cache-busters
    ver_js = int((STATIC_DIR / "voice.js").stat().st_mtime)
    ver_css = int((STATIC_DIR / "style.css").stat().st_mtime)
    html = html.replace('src="/voice.js"', f'src="/voice.js?v={ver_js}"')
    html = html.replace('href="/style.css"', f'href="/style.css?v={ver_css}"')
    return HTMLResponse(html)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
