#!/bin/sh
# Backup noturno do robô leve: banco (cópia consistente), sessão do WhatsApp, configuração e estado.
# Destino: pen drive de 16 GB (/srv/backup). Se ele não estiver montado, guarda no disco interno (só os 3 últimos).
set -e
cd /opt/promobot
DEST=/srv/backup/promobot; MANTER=14
mountpoint -q /srv/backup || { DEST=/opt/promobot/backup-local; MANTER=3; }
mkdir -p "$DEST"; TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
sqlite3 data/promobot.db ".backup '$TMP/promobot.db'"
tar -czf "$DEST/promobot-$(date +%Y%m%d-%H%M).tar.gz" -C "$TMP" promobot.db -C /opt/promobot .env data/wa data/control.json $(cd /opt/promobot && ls data/*.json data/*_idx data/*_index data/*_last_post 2>/dev/null | grep -v control.json)
ls -1t "$DEST"/promobot-*.tar.gz | tail -n +$((MANTER+1)) | xargs -r rm -f
