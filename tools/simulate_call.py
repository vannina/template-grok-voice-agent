#!/usr/bin/env python3
"""Simulateur de conversations Léa (prospection sortante) — sans téléphone.

Rejoue en MODE TEXTE, contre le WS xAI réel, des scénarios de prospect
scriptés, avec les instructions EXACTES construites comme en prod par le
pont Twilio outbound (web/server.py) :

    _load_config("prospection")           → system_prompt + runtime rules
  + _outbound_prospect_block(fiche, tel)  → contexte [Appel SORTANT]
  + _outbound_greeting(fiche)             → response.create du 1er tour
    (v12 : instruction déterministe du serveur, JAMAIS le texte du canned)

v12 — flux MANUEL aligné sur le pont : turn_detection.create_response=false
dans le session.update, chaque réponse est créée EXPLICITEMENT par le
simulateur (comme le pont : fin de tour → response.create ; silence →
instruction watchdog _OUTBOUND_NUDGE_INSTRUCTION ; clôture →
_OUTBOUND_CLOSE_INSTRUCTION). Le simulateur compte les response.created /
response.done et VÉRIFIE qu'il n'y a jamais deux réponses en vol
(verdict single_response sur tous les scénarios).

Les répliques du prospect sont injectées via conversation.item.create
(input_text) + response.create ; SILENCE (None) = pas d'item, relance
watchdog ; CLOSE = clôture watchdog. Les tool calls du modèle sont stubbés
localement (agenda toujours libre, Airtable simulée). Le texte de Léa est
lu depuis les events response.output_text.* / response.*audio_transcript.*
selon la modalité que l'API accepte.

Usage :
    ./.venv/bin/python tools/simulate_call.py                # les 7 scénarios
    ./.venv/bin/python tools/simulate_call.py -s meta -s coop
    ./.venv/bin/python tools/simulate_call.py --outdir /tmp/transcripts

Sort un transcript lisible par scénario dans --outdir + des VERDICTS
automatiques (pas de méta, 1re réplique conforme, pas de re-bonjour,
escalier de closing, opposition → outil + raccrochage, progression sur
silence, jamais deux réponses superposées). Exit code 0 si tous les
verdicts passent, 1 sinon. Nécessite XAI_API_KEY dans .env.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import websockets  # noqa: E402

from web import server as srv  # noqa: E402  (load_dotenv() tourne à l'import)

METIER = "prospection"
RESPONSE_TIMEOUT_S = 90.0

# Fiche prospect simulée — même forme que _outbound_ctx_put / _find_prospect_by_phone.
PROSPECT = {
    "record_id": "recSIMULATION00000",
    "nom": "Jean-Marc Rossi",
    "entreprise": "Rossi Plomberie",
    "secteur": "artisan du bâtiment",
    "metier": "plombier",
    "ville": "Ajaccio",
}
PROSPECT_TEL = "+33612345678"


# ---------------------------------------------------------------------------
# Scénarios : répliques du prospect, dans l'ordre. La 1re est le décroché
# (en prod : « allô » → opener canned → response.create greeting).
# SILENCE (None) = le prospect ne dit rien : le simulateur rejoue la relance
# du watchdog (response.create + _OUTBOUND_NUDGE_INSTRUCTION, comme le pont
# après 4 s de silence). CLOSE = clôture watchdog (_OUTBOUND_CLOSE_INSTRUCTION).
# ---------------------------------------------------------------------------
SILENCE = None
CLOSE = "<CLOSE>"

SCENARIOS: dict[str, dict] = {
    "coop": {
        "titre": "(a) Coopératif : allô → oui → intérêt → accepte mardi",
        "user": [
            "Allô ?",
            "Oui oui, c'est bien nous.",
            "Ah ouais ?",
            "Allez, mardi matin pourquoi pas.",
            "Neuf heures c'est bien.",
            "Rossi. Jean-Marc Rossi.",
            "Oui, ce numéro-là c'est bon.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "booked"],
    },
    "meta": {
        "titre": "(b) Transcription pourrie : « Ready? » puis « Hello? »",
        "user": [
            "Ready?",
            "Hello?",
            "Euh oui, c'est qui ?",
            "Ah d'accord. Bon, j'ai du travail là.",
            "Non merci.",
            "Non, vraiment pas.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "stays_french"],
    },
    "presse": {
        "titre": "(c) Pressé : « j'ai pas le temps »",
        "user": [
            "Allô oui ?",
            "J'ai pas le temps là.",
            "Non vraiment, je suis sur un chantier.",
            "Bon... rappelez-moi plutôt demain en fin de journée.",
            "C'est ça, au revoir.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "rappel_ou_fin"],
    },
    "refus": {
        "titre": "(d) Refus escalier : non au RDV, non au rappel",
        "user": [
            "Allô ?",
            "Oui c'est nous.",
            "Mouais.",
            "Non, pas de rendez-vous.",
            "Non, pas de rappel non plus.",
            "C'est ça, au revoir.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "escalier"],
    },
    "robot": {
        "titre": "(e) Demande si robot",
        "user": [
            "Allô ?",
            "Attendez... c'est un robot là ? Vous êtes une vraie personne ?",
            "Ah ouais ? C'est bluffant. Et donc ?",
            "Allez, jeudi alors.",
            "Onze heures.",
            "Colombani.",
            "Oui, ce numéro.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "revelation_ia"],
    },
    "opposition": {
        "titre": "(f) Opposition : « arrêtez de m'appeler »",
        "user": [
            "Allô ?",
            "Encore du démarchage... Arrêtez de m'appeler, retirez-moi de votre liste.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "opposition"],
    },
    "curieux": {
        "titre": "(h) Curieux : demande des infos — réponses réelles, pas de boucle RDV",
        "user": [
            "Allô ?",
            "Oui, c'est nous.",
            "Et ça marche comment votre truc ?",
            "Attendez, avant de parler rendez-vous... expliquez-moi. "
            "Elle fait quoi concrètement quand un client appelle ?",
            "Et si le client veut un dépannage en urgence, elle fait quoi ?",
            "D'accord. Et niveau installation, je dois changer de numéro ?",
            "OK. Bon, je vais y réfléchir.",
            "C'est ça, merci, au revoir.",
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "mode_info",
                   "no_rdv_loop", "disposition"],
    },
    "silencieux": {
        "titre": "(g) Silencieux : plus un mot après le décroché — Léa déroule seule",
        "user": [
            "Allô ?",
            SILENCE,   # watchdog → pitch
            SILENCE,   # watchdog → solution
            SILENCE,   # watchdog → closing
            CLOSE,     # watchdog close → clôture polie + end_call
        ],
        "checks": ["no_meta", "first_reply", "no_regreet", "progression_silence"],
    },
}


# ---------------------------------------------------------------------------
# Instructions : reproduction fidèle du chemin outbound du pont Twilio.
# ---------------------------------------------------------------------------
def build_instructions() -> tuple[str, str, dict]:
    """(instructions, greeting, config) exactement comme /twilio/stream
    direction=out : _load_config + _outbound_prospect_block +
    _outbound_greeting (v12 : le serveur impose la 1re réplique, instruction
    déterministe qui ne cite jamais le canned)."""
    config = srv._load_config(METIER)
    instructions = config["instructions"] + srv._outbound_prospect_block(
        PROSPECT, PROSPECT_TEL)
    greeting = srv._outbound_greeting(PROSPECT)
    return instructions, greeting, config


# ---------------------------------------------------------------------------
# Stubs d'outils (pas d'Airtable, pas de Google Calendar, pas de Twilio).
# ---------------------------------------------------------------------------
def stub_tool(name: str, args: dict, state: dict) -> dict:
    state["tools"].append({"name": name, "args": args})
    if name == "get_business_info":
        return srv._load_business(METIER)
    if name == "check_availability":
        return {"available": True, "free": 1,
                "date": args.get("date"), "time": args.get("time")}
    if name == "book_reservation":
        state["booked"] = dict(args)
        return {"status": "confirmed", "summary": "RDV découverte Corsica Studio",
                **{k: args.get(k) for k in ("name", "phone", "date", "time")}}
    if name == "qualify_lead":
        return {"status": "ok"}
    if name == "programmer_rappel":
        state["rappel"] = dict(args)
        return {"status": "ok", "date_rappel": args.get("date_souhaitee"),
                "creneau": args.get("creneau", "")}
    if name == "marquer_opposition":
        state["opposition"] = dict(args)
        return {"status": "ok", "opposition": True,
                "message": "Numéro inscrit sur la liste d'opposition."}
    if name == "end_call":
        state["ended"] = True
        return {"status": "ok"}
    return {"status": "ok", "note": f"outil {name} simulé"}


# ---------------------------------------------------------------------------
# Boucle WS
# ---------------------------------------------------------------------------
async def _collect_response(ws, state: dict, transcript: list[str]) -> str:
    """Lit les events jusqu'au response.done final du tour (en relançant un
    response.create après chaque salve de function calls). Retourne le texte
    parlé par Léa sur ce tour."""
    spoken: list[str] = []
    pending_calls: list[dict] = []
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=RESPONSE_TIMEOUT_S)
        ev = json.loads(raw)
        t = ev.get("type", "")
        if t == "error":
            msg = json.dumps(ev.get("error") or ev, ensure_ascii=False)
            transcript.append(f"    [xai error] {msg}")
            state["errors"].append(msg)
            # erreur bloquante sur le response courant : on rend la main
            if not spoken and not pending_calls:
                return ""
        elif t == "response.created":
            # v12 : vérif « jamais deux réponses en vol » (verdict
            # single_response) — même garde que le pont outbound.
            state["in_flight"] = state.get("in_flight", 0) + 1
            state["max_in_flight"] = max(state.get("max_in_flight", 0),
                                         state["in_flight"])
        elif t in ("response.output_text.done", "response.text.done",
                   "response.audio_transcript.done",
                   "response.output_audio_transcript.done"):
            txt = (ev.get("text") or ev.get("transcript") or "").strip()
            if txt:
                spoken.append(txt)
        elif t == "response.function_call_arguments.done":
            try:
                args = json.loads(ev.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": ev.get("arguments")}
            pending_calls.append({"call_id": ev.get("call_id"),
                                  "name": ev.get("name"), "args": args})
        elif t == "response.done":
            state["in_flight"] = max(0, state.get("in_flight", 0) - 1)
            if pending_calls:
                for call in pending_calls:
                    result = stub_tool(call["name"], call["args"], state)
                    transcript.append(
                        f"    [tool] {call['name']}({json.dumps(call['args'], ensure_ascii=False)})"
                        f" -> {json.dumps(result, ensure_ascii=False)[:200]}")
                    await ws.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {"type": "function_call_output",
                                 "call_id": call["call_id"],
                                 "output": json.dumps(result, ensure_ascii=False)},
                    }))
                pending_calls = []
                await ws.send(json.dumps({"type": "response.create"}))
                continue  # le tour continue sur le nouveau response
            return " ".join(spoken)
        # tout le reste (deltas texte/audio, session.updated, item.created,
        # rate_limits...) est ignoré : on ne lit que les .done.


async def run_scenario(key: str, sc: dict, outdir: Path) -> dict:
    instructions, greeting, config = build_instructions()
    state = {"tools": [], "errors": [], "ended": False,
             "booked": None, "rappel": None, "opposition": None,
             "in_flight": 0, "max_in_flight": 0}
    transcript: list[str] = [f"=== Scénario {key} — {sc['titre']} ==="]
    lea_turns: list[str] = []

    url = f"{srv.XAI_REALTIME_WS}?model={srv.MODEL}"
    headers = {"Authorization": f"Bearer {srv.XAI_API_KEY}"}
    async with websockets.connect(url, additional_headers=headers,
                                  max_size=None) as ws:
        prof = srv._load_profile(METIER)
        session: dict = {
            "voice": prof.get("voice") or srv.VOICE,
            "instructions": instructions,
            "tools": config["tools"],
            # v12 : même réglage que le pont outbound — pas de réponse auto,
            # le simulateur crée chaque réponse explicitement.
            "turn_detection": {"type": "server_vad", "create_response": False},
            # Modalité texte demandée ; si l'API la refuse, elle répond en
            # audio et on lit les transcripts (mêmes events *.done).
            "modalities": ["text"],
        }
        await ws.send(json.dumps({"type": "session.update", "session": session}))
        # Draine ~1 s : si session.update est rejeté à cause de "modalities",
        # on le renvoie sans ce champ (fallback audio→transcripts).
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=max(0.05, deadline - time.monotonic()))
            except asyncio.TimeoutError:
                break
            ev = json.loads(raw)
            if ev.get("type") == "error":
                msg = json.dumps(ev.get("error") or ev, ensure_ascii=False)
                if "modalit" in msg.lower():
                    session.pop("modalities", None)
                    await ws.send(json.dumps({"type": "session.update",
                                              "session": session}))
                    transcript.append("    [sim] modalities refusé → fallback audio/transcripts")
                else:
                    transcript.append(f"    [xai error session] {msg}")
                    state["errors"].append(msg)

        for i, user_msg in enumerate(sc["user"]):
            if state["ended"]:
                transcript.append(f"    [sim] appel raccroché — répliques restantes non jouées : {sc['user'][i:]}")
                break
            # v12 : flux MANUEL comme le pont — chaque réponse est créée
            # explicitement, jamais pendant qu'une autre est en vol
            # (_collect_response draine jusqu'au response.done avant de
            # rendre la main).
            create: dict = {"type": "response.create"}
            if user_msg is SILENCE:
                # Prospect muet : le pont relance via le watchdog (4 s) —
                # même instruction, response.create sans item utilisateur.
                transcript.append("[prospect] (silence — relance watchdog)")
                create["response"] = {
                    "instructions": srv._OUTBOUND_NUDGE_INSTRUCTION}
            elif user_msg == CLOSE:
                # Silence après relance : clôture polie + end_call (watchdog
                # close ; en prod le hangup force 8 s coupe quoi qu'il arrive).
                transcript.append("[prospect] (silence — clôture watchdog)")
                create["response"] = {
                    "instructions": srv._OUTBOUND_CLOSE_INSTRUCTION}
            else:
                transcript.append(f"[prospect] {user_msg}")
                await ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {"type": "message", "role": "user",
                             "content": [{"type": "input_text", "text": user_msg}]},
                }))
                if i == 0:
                    # 1er tour = exactement le response.create du pont après
                    # l'opener canned : l'instruction déterministe du serveur.
                    create["response"] = {"instructions": greeting}
            await ws.send(json.dumps(create))
            reply = await _collect_response(ws, state, transcript)
            transcript.append(f"[léa]      {reply}")
            lea_turns.append(reply)

    verdicts = evaluate(sc, lea_turns, state)
    transcript.append("")
    transcript.append("--- Verdicts ---")
    for name, (ok, detail) in verdicts.items():
        transcript.append(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"transcript-{key}.txt").write_text(
        "\n".join(transcript) + "\n", encoding="utf-8")
    return {"key": key, "titre": sc["titre"], "lea": lea_turns,
            "state": state, "verdicts": verdicts,
            "transcript": "\n".join(transcript)}


# ---------------------------------------------------------------------------
# Verdicts automatiques
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

# Méta = l'agent parle de son script / de sa consigne au lieu de la jouer.
_META_PATTERNS = [
    r"\bmon script\b", r"\ble script\b", r"\bscript\b",
    r"\bconsigne", r"\binstruction", r"\bscenario\b",
    r"\bmetteur en scene\b", r"\brepetition\b", r"\bmon role\b",
    r"\bma replique\b", r"\bbloc \d", r"\bsaluer\b", r"\bme presenter\b",
    r"\bje vais (saluer|verifier que je suis|me presenter|derouler|enchainer|jouer)\b",
    r"\bverifier que je suis bien chez\b", r"\bpremiere replique\b",
    r"\bsysteme de\b.*\bprompt\b", r"\bprompt\b",
    r"transcri", r"\bmal transcrit", r"\bje poursuis quand meme\b",
    r"\bce que vous avez entendu\b",
]


def evaluate(sc: dict, lea: list[str], state: dict) -> dict:
    v: dict[str, tuple[bool, str]] = {}
    all_txt = _norm(" || ".join(lea))
    first = _norm(lea[0]) if lea else ""
    checks = sc["checks"]

    if "no_meta" in checks:
        hits = [p for p in _META_PATTERNS if re.search(p, all_txt)]
        v["no_meta"] = (not hits,
                        "aucune méta détectée" if not hits else f"motifs méta : {hits}")

    if "first_reply" in checks:
        ok = bool(first) and (
            "c'est bien" in first or "je suis bien chez" in first
        ) and len(lea[0]) <= 90
        v["first_reply"] = (ok, f"1re réplique : {lea[0]!r}" if lea else "aucune réplique")

    if "no_regreet" in checks:
        bad = ("bonjour" in first) or ("c'est lea" in first) or \
              ("corsica studio" in first)
        v["no_regreet"] = (not bad,
                           "pas de re-salutation" if not bad
                           else f"re-salutation dans la 1re réplique : {lea[0]!r}")

    if "stays_french" in checks:
        english = re.search(r"\b(hello|yes|sorry|please|how are you)\b", all_txt)
        v["stays_french"] = (not english,
                             "reste en français" if not english
                             else f"anglais détecté : {english.group(0)!r}")

    if "booked" in checks:
        ok = state["booked"] is not None
        v["booked"] = (ok, f"book_reservation : {state['booked']}" if ok
                       else "book_reservation jamais appelé")

    if "rappel_ou_fin" in checks:
        ok = state["rappel"] is not None or state["ended"]
        v["rappel_ou_fin"] = (ok,
                              f"programmer_rappel={state['rappel']} ended={state['ended']}")

    if "escalier" in checks:
        # après le non au RDV : proposer le rappel (marche 2), puis la démo
        # (marche 3), sans re-forcer le rendez-vous.
        m2 = "rappel" in all_txt or "rappelle" in all_txt or "rappeler" in all_txt
        m3 = ("douze" in all_txt and "treize" in all_txt) or "demo" in all_txt \
             or "testez" in all_txt or "jugez" in all_txt
        v["escalier"] = (m2 and m3,
                         f"marche2(rappel)={m2} marche3(démo)={m3}")

    if "revelation_ia" in checks:
        ok = ("intelligence artificielle" in all_txt or re.search(r"\bia\b", all_txt)
              or "assistante vocale" in all_txt or "pas une vraie personne" in all_txt
              or "je suis une" in all_txt)
        v["revelation_ia"] = (bool(ok), "admet être une IA" if ok
                              else "n'admet pas être une IA")

    if "opposition" in checks:
        tool_ok = state["opposition"] is not None
        end_ok = state["ended"]
        confirm = ("plus" in all_txt and ("appel" in all_txt or "liste" in all_txt
                                          or "rappel" in all_txt))
        v["opposition"] = (tool_ok and end_ok and confirm,
                           f"marquer_opposition={tool_ok} end_call={end_ok} "
                           f"confirmation_orale={confirm}")

    if "no_rdv_loop" in checks:
        # v14 (cahier 6.10) : jamais plus de 2 propositions de RDV par appel.
        props = [t for t in lea
                 if re.search(r"quinze minutes|rendez.?vous", _norm(t))
                 and re.search(r"\?|mardi|jeudi|creneau|je vous bloque|on se cale",
                               _norm(t))]
        v["no_rdv_loop"] = (len(props) <= 2,
                            f"propositions de RDV = {len(props)} (max 2) : "
                            f"{[p[:60] for p in props]}")

    if "mode_info" in checks:
        # v14 (cahier 6.9/6.11) : aux demandes d'infos, des réponses CONCRÈTES
        # et proactives — jamais de demande de permission pour expliquer.
        marks = [k for k in ("coordonnees", "note", "sms", "agenda",
                             "numero actuel", "rien a installer", "se branche",
                             "relais", "decroche", "urgence")
                 if k in all_txt]
        permission = re.search(
            r"(voulez[- ]vous|vous voulez|souhaitez[- ]vous) que je (vous )?"
            r"(explique|detaille|presente)|je peux vous (expliquer|en dire plus)",
            all_txt)
        # v14.1 (cahier 6.12) : jamais d'annonce avant la réponse.
        annonce = re.search(
            r"\bje vais vous (expliquer|donner|detailler|presenter)\b"
            r"|\bje vous explique\b\s*[.!]?\s*$",
            all_txt)
        v["mode_info"] = (len(marks) >= 3 and not permission and not annonce,
                          f"infos concrètes={marks} "
                          f"demande_permission={bool(permission)} "
                          f"annonce_avant_réponse={bool(annonce)}")

    if "disposition" in checks:
        # v14 (cahier 6.10) : clôture service — à disposition + démo à essayer.
        demo = "douze" in all_txt and "treize" in all_txt
        dispo = "disposition" in all_txt or "testez" in all_txt or demo
        v["disposition"] = (dispo,
                            f"démo_donnée={demo} à_disposition={dispo}")

    if "progression_silence" in checks:
        # prospect muet : les relances watchdog doivent faire AVANCER le
        # script (pitch → solution → closing), puis la clôture raccroche.
        mids = [t for t in lea[1:-1] if t]
        last = _norm(lea[-1]) if lea and lea[-1] else ""
        mid_txt = _norm(" || ".join(mids))
        pitch = any(k in mid_txt for k in ("perd", "client", "appel", "solution"))
        solution = any(k in mid_txt for k in ("assistante", "decroche", "agenda",
                                              "rendez-vous", "note", "coordonnees"))
        closing = any(k in mid_txt for k in ("rappel", "demo", "testez", "jugez",
                                             "quinze minutes", "rendez-vous"))
        distinct = len(set(mids)) == len(mids)  # jamais deux fois la même relance
        bye = any(k in last for k in ("au revoir", "bonne journee", "je vous laisse"))
        ok = pitch and solution and closing and distinct and (bye or state["ended"])
        v["progression_silence"] = (
            ok, f"pitch={pitch} solution={solution} closing={closing} "
                f"relances_distinctes={distinct} clôture(bye={bye}, "
                f"end_call={state['ended']})")

    # v12 : garde structurelle vérifiée sur TOUS les scénarios — jamais deux
    # réponses en vol (miroir de la garde response_active du pont).
    v["single_response"] = (
        state.get("max_in_flight", 0) <= 1,
        f"max réponses en vol = {state.get('max_in_flight', 0)}")

    return v


# ---------------------------------------------------------------------------
async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-s", "--scenario", action="append", choices=sorted(SCENARIOS),
                    help="scénario(s) à jouer (défaut : tous)")
    ap.add_argument("--outdir", default=str(REPO / "tools" / "transcripts"),
                    help="dossier des transcripts (défaut : tools/transcripts/)")
    args = ap.parse_args()

    if not srv.XAI_API_KEY:
        print("ERREUR : XAI_API_KEY absent du .env")
        return 2

    keys = args.scenario or list(SCENARIOS)
    outdir = Path(args.outdir)
    results = []
    for key in keys:
        print(f"\n––– scénario {key} : {SCENARIOS[key]['titre']}")
        try:
            res = await run_scenario(key, SCENARIOS[key], outdir)
        except Exception as e:  # noqa: BLE001 — un scénario KO n'arrête pas la série
            print(f"  EXCEPTION : {type(e).__name__}: {e}")
            results.append({"key": key, "verdicts": {"run": (False, str(e))},
                            "lea": [], "state": {}})
            continue
        results.append(res)
        for line in res["transcript"].splitlines():
            print("  " + line)

    print("\n================ SYNTHÈSE ================")
    failed = 0
    for res in results:
        oks = all(ok for ok, _ in res["verdicts"].values())
        failed += 0 if oks else 1
        flags = " ".join(f"{name}={'OK' if ok else 'FAIL'}"
                         for name, (ok, _) in res["verdicts"].items())
        print(f"  [{'PASS' if oks else 'FAIL'}] {res['key']}: {flags}")
    print(f"Transcripts : {outdir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
