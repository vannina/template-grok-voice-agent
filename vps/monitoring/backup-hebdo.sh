#!/bin/bash
# /opt/monitoring/backup-hebdo.sh — archive hebdo des configs critiques (mission #31 Ops)
# Cree le 2026-07-20. Cron : dimanche 02h30 UTC.
#
# Archive dans /root/backups (tar.gz date, chmod 600, retention 8 semaines) :
#   /opt/demo-voice/.env, /opt/standard-voice/.env, /opt/monitoring, /docker/docker-compose.yml
# Le contenu des .env n'est JAMAIS affiche ni loggue.
# Complement du backup quotidien existant /opt/backups/backup.sh (postgres, volumes
# n8n/qdrant, confs /docker, demo-voice — retention 14 j + off-site Drive chiffre) :
# celui-ci ajoute le .env de standard-voice et une retention longue (8 semaines).
set -u

BK=/root/backups
MON=/opt/monitoring
TS=$(date +%F)
TAR=$BK/config-vps-$TS.tar.gz

mkdir -p "$BK"
chmod 700 "$BK"

tar czf "$TAR" \
  --exclude="$MON/*.log" --exclude="$MON/state" \
  /opt/demo-voice/.env \
  /opt/standard-voice/.env \
  "$MON" \
  /docker/docker-compose.yml 2>/dev/null
chmod 600 "$TAR"

# retention : 8 semaines
find "$BK" -name 'config-vps-*.tar.gz' -mtime +56 -delete 2>/dev/null

echo "[$(date '+%F %T')] archive $TAR ($(du -h "$TAR" | cut -f1)) — $(ls "$BK" | grep -c 'config-vps-') archives conservees" >> "$MON/backup-hebdo.log"
exit 0
