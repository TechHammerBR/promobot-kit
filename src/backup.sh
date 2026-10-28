#!/bin/sh
# Backup noturno do robô: banco (cópia consistente), sessão do WhatsApp, configuração e estado.
# Destino: /srv/backup/promobot se esse disco estiver montado; senão /opt/promobot/backup-local (guarda só os 3 últimos).
# Troque DEST (ou monte um disco/pendrive em /srv/backup) para guardar em outro lugar. O backup CONTÉM SEGREDOS (.env): proteja-o.
set -e
cd /opt/promobot
DEST=/srv/backup/promobot; MANTER=14
mountpoint -q /srv/backup 2>/dev/null || { DEST=/opt/promobot/backup-local; MANTER=3; }
mkdir -p "$DEST"; TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
sqlite3 data/promobot.db ".backup '$TMP/promobot.db'"
# só inclui o que existe (numa instalação nova, control.json e outros estados ainda não existem)
LISTA=$(ls -d .env data/wa data/*.json data/*_idx data/*_index data/*_last_post 2>/dev/null | sort -u | tr '\n' ' ')
tar -czf "$DEST/promobot-$(date +%Y%m%d-%H%M).tar.gz" -C "$TMP" promobot.db -C /opt/promobot $LISTA
ls -1t "$DEST"/promobot-*.tar.gz | tail -n +$((MANTER+1)) | xargs -r rm -f
chmod 600 "$DEST"/promobot-*.tar.gz 2>/dev/null || true
echo "backup ok: $(ls -1t "$DEST"/promobot-*.tar.gz | head -1)"
