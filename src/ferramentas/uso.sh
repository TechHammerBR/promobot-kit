#!/bin/bash
# Registro de uso da máquina (root, a cada 5 min — /etc/cron.d/promobot-uso). Pedido do dono em 13/10/2026: relatório diário de
# uso, horários de pico e custo de energia. Uma linha por amostra em data/uso.log (guarda ~14 dias). Custo: 1 processo por 20 s.
# Colunas: data hora | cpu% (média de 20 s, 4 núcleos) | memória usada MB | temperatura C | watts do processador (RAPL, não é o da tomada)
set -u
LOG=/opt/promobot/data/uso.log
R=/sys/class/powercap/intel-rapl:0/energy_uj
l1=($(head -1 /proc/stat)); e1=$(cat $R 2>/dev/null || echo 0)
sleep 20
l2=($(head -1 /proc/stat)); e2=$(cat $R 2>/dev/null || echo 0)
t1=0; for v in "${l1[@]:1}"; do t1=$((t1+v)); done
t2=0; for v in "${l2[@]:1}"; do t2=$((t2+v)); done
oc=$(( (l2[4]+l2[5]) - (l1[4]+l1[5]) )); tot=$((t2-t1))
CPU=$(awk -v o=$oc -v t=$tot 'BEGIN{printf "%.1f", (t>0) ? 100*(t-o)/t : 0}')
W=$(awk -v a=$e1 -v b=$e2 'BEGIN{printf "%.2f", (b>a) ? (b-a)/20/1000000 : 0}')
MEM=$(free -m | awk '/^Mem/ {print $3}')
TEMP=$(sort -n /sys/class/thermal/thermal_zone*/temp 2>/dev/null | tail -1 | awk '{printf "%d", $1/1000}')
echo "$(date '+%Y-%m-%d %H:%M') $CPU $MEM $TEMP $W" >> $LOG
[ "$(wc -l < $LOG)" -gt 4300 ] && { tail -n 4032 $LOG > $LOG.tmp && mv $LOG.tmp $LOG; }
chown promobot: $LOG
exit 0
