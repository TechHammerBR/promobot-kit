#!/bin/bash
# Vigia dos discos (v2, 25/10/2026). /srv/cache = SSD externo (principal); /srv/cache-copia = pendrive de 64 GB (copia de hora em hora);
# /srv/backup = pendrive 16 GB (backups); /srv/espelho = pendrive 4 GB. Cron de 5 em 5 min. Log: data/logs/vigia_armazenamento.log
# Se algo travar/sumir (USB caiu), para o robo, remonta por LABEL e religa. Se o SSD nao voltar, o robo passa a rodar pela COPIA
# (bind de /srv/cache-copia em /srv/cache) e avisa; a copia automatica fica travada (flag data/FAILOVER_CACHE) para nao apagar a copia boa.
LOG=/opt/promobot/data/logs/vigia_armazenamento.log
LOCK=/tmp/vigia_armazenamento.lock
SERV="promobot-bot promobot-linkgen promobot-tela promobot-wa"
[ -e /opt/promobot/data/MAINTENANCE ] && exit 0
exec 9>$LOCK; flock -n 9 || exit 0

avisa() {
  /opt/promobot/venv/bin/python - "$1" <<'PY' 2>/dev/null
import sys; sys.path.insert(0, "/opt/promobot")
from app.publisher import alert
alert(sys.argv[1])
PY
}
escreve() { timeout 10 bash -c "f=$1/.vigia.\$\$; touch \$f && rm -f \$f" 2>/dev/null; }
teste() {
  mountpoint -q /srv/backup && mountpoint -q /srv/cache && mountpoint -q /srv/espelho || return 1
  escreve /srv/cache || return 1
  escreve /srv/espelho || return 1
  timeout 10 ls /srv/backup >/dev/null 2>&1 || return 1
  return 0
}

teste && { mountpoint -q /srv/cache-copia || sudo -n mount /srv/cache-copia 2>/dev/null; exit 0; }
sleep 20; teste && exit 0   # confirma (queda breve)

echo "$(date '+%F %T') armazenamento com problema: remontando" >> $LOG
sudo -n systemctl stop promobot-fila-reels.timer $SERV
sudo -n umount -l /srv/cache /srv/cache-copia /srv/espelho /srv/backup 2>/dev/null
sleep 5
sudo -n mount -a 2>> $LOG
sudo -n swapon -a 2>/dev/null   # religa o swap do SSD (LABEL=SWAPSSD) se ele tiver voltado
for d in /srv/backup /srv/cache /srv/cache-copia /srv/espelho; do mountpoint -q $d || echo "$(date '+%F %T') $d NAO montou" >> $LOG; done
if teste; then
  sudo -n systemctl start $SERV promobot-fila-reels.timer
  echo "$(date '+%F %T') recuperado; servicos religados" >> $LOG
  avisa "Um disco USB caiu e o Wyse remontou sozinho; servicos religados."
  exit 0
fi

# SSD (principal) nao voltou: tenta rodar pela copia
if mountpoint -q /srv/cache-copia && ! mountpoint -q /srv/cache && [ -e /srv/cache-copia/.ssd_ok ]; then
  sudo -n mount --bind /srv/cache-copia /srv/cache && touch /opt/promobot/data/FAILOVER_CACHE
  if teste; then
    sudo -n systemctl start $SERV promobot-fila-reels.timer
    echo "$(date '+%F %T') FAILOVER: SSD nao voltou; robo rodando pela copia (pendrive 64 GB)" >> $LOG
    avisa "SSD externo falhou: o robo esta rodando pela copia no pendrive de 64 GB (ate 1 h defasada). Ver CLAUDE.md: failback."
    exit 0
  fi
fi
echo "$(date '+%F %T') NAO recuperou; servicos continuam parados (tentara de novo em 5 min)" >> $LOG
