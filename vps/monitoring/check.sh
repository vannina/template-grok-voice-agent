#!/bin/bash
# /opt/monitoring/check.sh — healthcheck agents vocaux Corsica Studio (mission #31 Ops)
# Cree le 2026-07-20. Cron : toutes les 5 minutes (crontab root).
#
# Verifie :
#   (a) conteneurs demo-voice + standard-voice en etat "running"
#   (b) HTTPS 200 sur demo.corsica-studio.com et standard.corsica-studio.com
#   (c) erreurs recurrentes dans les logs des 5 dernieres minutes (seuil)
#
# Alerte : POST JSON -> n8n WF-Monitor (webhook /monitor-alerte -> Telegram Vannina).
# Fallback si n8n injoignable : Telegram direct (token source depuis .env, JAMAIS affiche).
# Anti-spam : 1 alerte/heure max par probleme (fichiers d'etat dans state/),
# message de retablissement 🟢 quand le probleme disparait.
set -u

MON=/opt/monitoring
STATE=$MON/state
LOG=$MON/check.log
mkdir -p "$STATE"

WEBHOOK_URL="https://n8n-cs.corsica-studio.com/webhook/monitor-alerte"
ENV_STANDARD=/opt/standard-voice/.env
HOST_TAG=$(hostname -s)
REALERT_S=3600           # ne pas repeter la meme alerte plus d'une fois par heure
LOG_THRESHOLD=5          # erreurs / 5 min avant alerte
BENIGN='error=None|"error": *null|errors=0|0 errors'   # lignes benignes exclues

log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

send_alert(){  # $1 = message
  local msg="$1"
  if jq -cn --arg m "$msg" --arg h "$HOST_TAG" '{message:$m, source:"check.sh", host:$h}' \
     | curl -s -m 10 -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' --data @- \
     | grep -q OK; then
    log "alerte envoyee (webhook n8n): $msg"
    return 0
  fi
  # Fallback : n8n injoignable -> Telegram direct. Token jamais loggue ni affiche.
  local tok chat
  tok=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_STANDARD" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' )
  chat=$(grep -E '^TELEGRAM_CHAT_ID=' "$ENV_STANDARD" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' )
  if [ -n "$tok" ] && [ -n "$chat" ]; then
    if curl -s -m 10 "https://api.telegram.org/bot${tok}/sendMessage" \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${msg} [fallback direct — n8n injoignable]" >/dev/null; then
      log "alerte envoyee (fallback telegram direct): $msg"
      return 0
    fi
  fi
  log "ECHEC envoi alerte (webhook ET fallback KO): $msg"
  return 1
}

problem(){  # $1 = cle etat, $2 = message
  local key="$1" msg="$2" f="$STATE/$1" now last
  now=$(date +%s)
  if [ -f "$f" ]; then
    last=$(cat "$f" 2>/dev/null || echo 0)
    if [ $((now - last)) -lt "$REALERT_S" ]; then
      log "probleme '$key' persiste (derniere alerte il y a $((now - last))s) : $msg"
      return
    fi
  fi
  send_alert "🔴 $msg" && echo "$now" > "$f"
}

recovered(){  # $1 = cle etat, $2 = message retablissement
  local key="$1" msg="$2" f="$STATE/$1"
  if [ -f "$f" ]; then
    rm -f "$f"
    send_alert "🟢 $msg"
  fi
}

# ---------- (a) conteneurs ----------
for c in demo-voice standard-voice; do
  st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo absent)
  if [ "$st" = "running" ]; then
    recovered "container_$c" "Conteneur $c de nouveau UP"
  else
    problem "container_$c" "Conteneur $c DOWN (etat: $st)"
  fi
done

# ---------- (b) HTTPS ----------
for d in demo.corsica-studio.com standard.corsica-studio.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "https://$d/" 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then
    recovered "https_$d" "https://$d/ repond de nouveau 200"
  else
    problem "https_$d" "https://$d/ repond $code (attendu 200)"
  fi
done

# ---------- (c) erreurs recurrentes dans les logs (5 min) ----------
for c in demo-voice standard-voice; do
  n=$(docker logs --since 5m "$c" 2>&1 | grep -iE 'error|traceback|failed' | grep -vciE "$BENIGN")
  n=${n:-0}
  if [ "$n" -ge "$LOG_THRESHOLD" ]; then
    sample=$(docker logs --since 5m "$c" 2>&1 | grep -iE 'error|traceback|failed' \
             | grep -viE "$BENIGN" | tail -3 | cut -c1-200 | tr '\n' ' | ')
    problem "logs_$c" "$n lignes d'erreur en 5 min dans les logs de $c. Extraits: $sample"
  else
    recovered "logs_$c" "Logs de $c redevenus sains (< $LOG_THRESHOLD erreurs/5 min)"
  fi
done

exit 0
