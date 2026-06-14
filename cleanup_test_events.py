#!/usr/bin/env python3
"""Supprime les 7 evenements de TEST crees le 2026-06-14 par la verif bout en bout
des demos (workflow #43). Tous nommes "[TEST CS auto] Verif <metier>" le 2026-06-20.

Lance-le depuis le dossier template-grok-voice-agent (il lit .env) :
    ./.venv/bin/python cleanup_test_events.py
ou en dry-run d'abord pour juste lister :
    ./.venv/bin/python cleanup_test_events.py --dry-run

Aucune autre donnee n'est touchee : suppression ciblee par event_id exact.
"""
import os, sys, json, pathlib, urllib.request

HERE = pathlib.Path(__file__).parent

# Charge .env (KEY=VALUE) sans dependance externe
for line in (HERE / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

API_KEY = os.environ.get("COMPOSIO_API_KEY")
USER_ID = os.environ.get("COMPOSIO_USER_ID", "margot-bistro-demo")
RESTO_CAL = os.environ.get("RESTAURANT_CALENDAR_ID", "primary")
SHARED_CAL = "89884ac999c1466943700e44935680309c680bae2c264970df2ba0000c9cf93f@group.calendar.google.com"
DEL_URL = "https://backend.composio.dev/api/v3/tools/execute/GOOGLECALENDAR_DELETE_EVENT"

# (metier, event_id, calendar_id) — issus du rapport de verif w518rmdj1
EVENTS = [
    ("restaurant", "di4r7db47ej9evi2taed4003kg", RESTO_CAL),
    ("hotel",      "jbovugo2idqfie6jktd025mnrs", SHARED_CAL),
    ("medical",    "dpmng4htefvb2r09jva4mco084", SHARED_CAL),
    ("immobilier", "1s4lr66hik7mnd3e9gm6guka2g", SHARED_CAL),
    ("artisan",    "k29tfpl7o9mulqo4oomjirbav8", SHARED_CAL),
    ("coach",      "pc5822550tu9sj7ghtfr2513m0", SHARED_CAL),
    ("beaute",     "9o06qe2eponu7k3j4i9g24l4lk", SHARED_CAL),
]

dry = "--dry-run" in sys.argv
if not API_KEY:
    print("COMPOSIO_API_KEY absente du .env"); sys.exit(1)

for metier, eid, cal in EVENTS:
    if dry:
        print(f"[dry-run] supprimerait {metier:11s} event={eid} cal={cal[:24]}...")
        continue
    body = json.dumps({"user_id": USER_ID,
                       "arguments": {"calendar_id": cal, "event_id": eid}}).encode()
    req = urllib.request.Request(DEL_URL, data=body, method="POST",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            out = json.loads(r.read())
        ok = out.get("successful", out.get("success", False))
        print(f"{'OK ' if ok else '!! '}{metier:11s} {eid}  -> {ok}")
    except Exception as e:
        print(f"!! {metier:11s} {eid}  -> ERREUR {e}")

print("Termine." if not dry else "Dry-run termine.")
