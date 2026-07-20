#!/bin/bash
# /opt/monitoring/recette-hebdo.sh — recette hebdo Lea (mission #31 Ops)
# Cree le 2026-07-20. Cron : lundi 05h30 UTC = 07h30 heure de Paris (ete).
#
# Lance le simulateur de conversations (tools/simulate_call.py) DANS le conteneur
# standard-voice (l'image a python3 + websockets + dotenv + XAI_API_KEY en env),
# scenarios rapides : coop + curieux. Le script est docker cp a chaque run
# (survit aux rebuilds). Verdict PASS/FAIL poste sur le webhook n8n monitor-alerte
# (prefixe [recette hebdo]). Transcripts dans /opt/standard-voice/data/recette/.
set -u

WEBHOOK_URL="https://n8n-cs.corsica-studio.com/webhook/monitor-alerte"
HOST_TAG=$(hostname -s)
LOG=/opt/monitoring/recette-hebdo.log
SRC=/opt/standard-voice/tools/simulate_call.py
TMP=$(mktemp)

docker exec -u root standard-voice mkdir -p /app/tools
docker cp "$SRC" standard-voice:/app/tools/simulate_call.py
docker exec -u root standard-voice mkdir -p /app/data/recette
docker exec -u root standard-voice chown -R app:app /app/data/recette

if timeout 900 docker exec standard-voice python3 /app/tools/simulate_call.py \
     -s coop -s curieux --outdir /app/data/recette > "$TMP" 2>&1; then
  verdict=PASS
else
  verdict=FAIL
fi

synth=$(grep -aiE 'PASS|FAIL|verdict|scenario|OK|KO' "$TMP" | tail -15 | cut -c1-200)
[ -n "$synth" ] || synth=$(tail -15 "$TMP" | cut -c1-200)
msg="[recette hebdo] Léa ${verdict} (scénarios coop + curieux)
${synth}"
msg=${msg:0:3500}

jq -cn --arg m "$msg" --arg h "$HOST_TAG" '{message:$m, source:"recette-hebdo", host:$h}' \
  | curl -s -m 15 -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' --data @- >/dev/null

{ echo "=== $(date '+%F %T') verdict=$verdict ==="; cat "$TMP"; } >> "$LOG"
rm -f "$TMP"
exit 0
