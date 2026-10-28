#!/bin/bash
# Espelho (25/10/2026): cópia diária dos itens críticos do robô para o pendrive de 4 GB (/srv/espelho), caso o pendrive de 16 GB (/srv/backup, que guarda a fila e os backups) falhe.
mountpoint -q /srv/espelho || { echo "$(date '+%F %T') espelho nao montado" >> /opt/promobot/data/logs/espelho.log; exit 1; }
D=/srv/espelho
mkdir -p $D/backups $D/cache
ls -1t /srv/backup/promobot/promobot-*.tar.gz 2>/dev/null | head -3 | while read f; do [ -f "$D/backups/$(basename $f)" ] || cp -p "$f" $D/backups/; done
ls -1t $D/backups/promobot-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
rsync -a --delete /srv/cache/ml-perfil-backup/ $D/cache/ml-perfil-backup/
rsync -a --delete /srv/cache/perfis/ $D/cache/perfis/
rsync -a --delete /srv/cache/aprovados/ $D/cache/aprovados/
rsync -a /opt/promobot/.env $D/env.copia && chmod 600 $D/env.copia
rsync -a /opt/promobot/data/linkgen/session_cookies.json $D/ 2>/dev/null
echo "$(date '+%F %T') ok: $(du -sh $D | cut -f1)" >> /opt/promobot/data/logs/espelho.log
