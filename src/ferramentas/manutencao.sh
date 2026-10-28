#!/bin/bash
# Manutenção diária do Wyse (roda como root às 04:20, fora do horário de posts — /etc/cron.d/promobot-manutencao).
# Objetivo do dono (13/10/2026): servidor sempre enxuto, sem risco de travar. Tudo aqui é automático e registrado em data/saude.log.
#   1) para o robô, enxuga o banco (ofertas recusadas/expiradas antigas), compacta e religa -> memória sempre "zerada" de manhã
#   2) limpa temporários, cache do apt, relatórios e logs velhos
#   3) confere disco, memória, temperatura e serviços; problema vai para data/alertas.log (o Claude lê com `ctl alertas`)
# Teste manual: sudo /opt/promobot/ferramentas/manutencao.sh
set -u
APP=/opt/promobot
DB=$APP/data/promobot.db
LOG=$APP/data/saude.log
DONO=promobot
agora() { date '+%Y-%m-%d %H:%M'; }
alerta() { printf '{"quando": "%s", "msg": "MANUTENCAO: %s"}\n' "$(date -Iseconds)" "$1" >> $APP/data/alertas.log; chown $DONO: $APP/data/alertas.log; }

[ -f $APP/data/MAINTENANCE ] && { echo "$(agora) pulada (data/MAINTENANCE existe)" >> $LOG; exit 0; }

# ---- 1) banco: com o robô parado (ninguém escrevendo)
ANTES=$(du -k $DB | cut -f1)
systemctl stop promobot-bot
sudo -u $DONO sqlite3 $DB <<'SQL' >/dev/null 2>&1
DELETE FROM offers WHERE status IN ('rejected','expired','failed') AND created_at < datetime('now','-3 days');
DELETE FROM offers WHERE status = 'posted' AND posted_at < datetime('now','-60 days');
DELETE FROM offers WHERE status IN ('new','pending') AND created_at < datetime('now','-2 days');
DELETE FROM coupons WHERE last_seen < datetime('now','-30 days');
DELETE FROM price_history WHERE day < date('now','-90 days');
PRAGMA wal_checkpoint(TRUNCATE);
PRAGMA optimize;
SQL
# compactação completa só aos domingos (reescreve o arquivo inteiro: poupa a memória interna)
[ "$(date +%u)" = "7" ] && sudo -u $DONO sqlite3 $DB 'VACUUM;' >/dev/null 2>&1
OK_DB=$(sudo -u $DONO sqlite3 $DB 'PRAGMA quick_check;' 2>&1 | head -1)
systemctl restart promobot-wa
systemctl restart promobot-linkgen  # recicla o navegador todo dia na janela sem posts (3h-6h): evita 'Page crashed' por vazamento de memória
sleep 20
systemctl start promobot-bot
DEPOIS=$(du -k $DB | cut -f1)

# ---- 2) limpeza
find /tmp -mindepth 1 -maxdepth 1 -user $DONO -mmin +360 -exec rm -rf {} + 2>/dev/null
find $APP/data/relatorios -name '*.txt' -mtime +365 -delete 2>/dev/null
find $APP/data/logs -name 'promobot.log.*' -mtime +14 -delete 2>/dev/null
find $APP/data/wa/inbox -type f -mtime +2 -delete 2>/dev/null
find /var/log -name '*.gz' -mtime +14 -delete 2>/dev/null
apt-get clean >/dev/null 2>&1
[ "$(date +%u)" = "7" ] && fstrim -a >/dev/null 2>&1

# ---- 3) saúde
DISCO=$(df --output=pcent / | tail -1 | tr -dc '0-9')
MEM=$(free -m | awk '/^Mem/ {print $3"/"$2"MB"}')
TEMP=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1 | awk '{printf "%d", $1/1000}')
SWAPUSB=$(awk '$1 ~ /^\/dev\/sd/ {print int($4/1024)}' /proc/swaps)  # reserva de 4 GB no SSD externo (MB em uso; vazio = ausente) - 26/10/2026
sleep 25
FALHAS=$(systemctl --failed --no-legend | wc -l)
BOT=$(systemctl is-active promobot-bot); WA=$(systemctl is-active promobot-wa)
BKP=$(find /srv/backup/promobot -name 'promobot-*.tar.gz' -mmin -1560 2>/dev/null | wc -l)
echo "$(agora) disco ${DISCO}% | mem ${MEM} | cpu ${TEMP:-?}C | banco ${ANTES}->${DEPOIS}KB (${OK_DB}) | bot ${BOT} wa ${WA} | swap pendrive ${SWAPUSB:-ausente}MB | servicos com falha ${FALHAS} | backup 26h ${BKP} | ligado ha $(uptime -p | cut -c4-)" >> $LOG
tail -n 120 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
chown $DONO: $LOG

[ "$DISCO" -ge 80 ] && alerta "disco interno em ${DISCO}%"
[ "$OK_DB" != "ok" ] && alerta "banco com problema: ${OK_DB}"
[ "$BOT" != "active" ] && alerta "robo nao voltou depois da manutencao (${BOT})"
[ "$WA" != "active" ] && alerta "conector do WhatsApp nao voltou (${WA})"
[ "$BKP" -eq 0 ] && alerta "nenhum backup nas ultimas 26 horas"
[ "${TEMP:-0}" -ge 85 ] && alerta "processador a ${TEMP}C"
[ -z "$SWAPUSB" ] && alerta "reserva de memoria do SSD (swap de 4 GB) nao esta ativa (SSD solto?)"
[ "${SWAPUSB:-0}" -ge 512 ] && alerta "Wyse usando ${SWAPUSB} MB da reserva no SSD: memoria apertada"
exit 0
