#!/bin/bash
# /opt/monitoring/couts.sh — suivi quotidien des couts agents vocaux (mission #31 Ops)
# Cree le 2026-07-20. Cron : 21h50 UTC = 23h50 heure de Paris (ete).
#
# Agrege dans /opt/monitoring/couts.csv (date,app,sessions,minutes) :
#   - sessions du jour par app depuis /opt/<app>/data/usage.jsonl (event=start)
#   - appels + minutes Twilio du jour via l'API Calls (credentials extraits du .env
#     de standard-voice, JAMAIS affiches ni loggues)
set -u

MON=/opt/monitoring
CSV=$MON/couts.csv
ENV_STANDARD=/opt/standard-voice/.env
DAY=$(TZ=Europe/Paris date +%F)

[ -f "$CSV" ] || echo "date,app,sessions,minutes" > "$CSV"

# ---------- sessions par app (usage.jsonl) ----------
for app in demo-voice standard-voice; do
  f=/opt/$app/data/usage.jsonl
  n=0
  if [ -f "$f" ]; then
    n=$(grep '"event": "start"' "$f" 2>/dev/null | grep -c "\"ts\": \"$DAY" || true)
    n=${n:-0}
  fi
  echo "$DAY,$app,$n," >> "$CSV"
done

# ---------- minutes Twilio du jour (API Calls) ----------
SID=$(grep -E '^TWILIO_ACCOUNT_SID=' "$ENV_STANDARD" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
TOK=$(grep -E '^TWILIO_AUTH_TOKEN=' "$ENV_STANDARD" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
if [ -n "$SID" ] && [ -n "$TOK" ]; then
  resp=$(curl -s -m 20 -u "$SID:$TOK" \
    "https://api.twilio.com/2010-04-01/Accounts/$SID/Calls.json?StartTime=$DAY&PageSize=1000" 2>/dev/null)
  if echo "$resp" | jq -e '.calls' >/dev/null 2>&1; then
    ncalls=$(echo "$resp" | jq '.calls | length')
    secs=$(echo "$resp" | jq '[.calls[].duration // "0" | tonumber] | add // 0')
    mins=$(( (secs + 59) / 60 ))
    echo "$DAY,twilio,$ncalls,$mins" >> "$CSV"
  else
    echo "$DAY,twilio,ERR," >> "$CSV"
    echo "[$(date '+%F %T')] API Twilio KO (reponse sans .calls)" >> "$MON/couts.log"
  fi
else
  echo "[$(date '+%F %T')] credentials Twilio absents du .env standard-voice" >> "$MON/couts.log"
fi

exit 0
