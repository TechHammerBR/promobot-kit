#!/bin/bash
# Copia de hora em hora do SSD (/srv/cache) para o pendrive de 64 GB (/srv/cache-copia). So roda se o SSD estiver saudavel
# (marcador .ssd_ok, sem failover), para nunca apagar a copia boa com dados ruins. Log: data/logs/copia_cache.log
LOG=/opt/promobot/data/logs/copia_cache.log
exec 9>/tmp/copia_cache.lock; flock -n 9 || exit 0
[ -e /opt/promobot/data/MAINTENANCE ] && exit 0
[ -e /opt/promobot/data/FAILOVER_CACHE ] && exit 0
mountpoint -q /srv/cache && mountpoint -q /srv/cache-copia || { echo "$(date '+%F %T') nao montado, pulei" >> $LOG; exit 0; }
[ -e /srv/cache/.ssd_ok ] || { echo "$(date '+%F %T') sem .ssd_ok no SSD, pulei" >> $LOG; exit 0; }
SSD=$(sudo -n blkid -L SSD 2>/dev/null); FONTE=$(findmnt -no SOURCE /srv/cache)
[ -n "$SSD" ] && [ "$FONTE" = "$SSD" ] || { echo "$(date '+%F %T') /srv/cache nao e o SSD ($FONTE), pulei" >> $LOG; exit 0; }
t0=$(date +%s)
rsync -aH --delete --exclude=/lost+found --exclude=/tmp/ /srv/cache/ /srv/cache-copia/ >> $LOG 2>&1 && \
  echo "$(date '+%F %T') copia ok em $(( $(date +%s) - t0 ))s" >> $LOG || echo "$(date '+%F %T') copia FALHOU" >> $LOG
tail -n 400 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
