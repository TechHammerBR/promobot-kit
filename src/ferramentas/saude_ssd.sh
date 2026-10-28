#!/bin/bash
# Saude do SSD externo (NVMe ADATA com 255% de desgaste em 25/10/2026): le o SMART todo dia e avisa em alertas.log se algo piorar.
# Log: data/logs/saude_ssd.log
LOG=/opt/promobot/data/logs/saude_ssd.log
SSD=$(sudo -n blkid -L SSD 2>/dev/null); [ -n "$SSD" ] || { echo "$(date '+%F %T') SSD nao encontrado" >> $LOG; exit 0; }
DEV=/dev/$(lsblk -no PKNAME $SSD)
S=$(sudo -n smartctl -A -d sntrealtek $DEV 2>/dev/null) || exit 0
v() { echo "$S" | awk -F: -v k="$1" '$1 ~ k {gsub(/Celsius/,"",$2); gsub(/[ ,%]/,"",$2); print $2; exit}'; }
temp=$(v "^Temperature"); spare=$(v "^Available Spare$"); used=$(v "Percentage Used"); media=$(v "Media and Data"); crit=$(v "Critical Warning"); unsafe=$(v "Unsafe Shutdowns")
ANT=/opt/promobot/data/saude_ssd_anterior.txt
prev_media=0; [ -f $ANT ] && prev_media=$(awk '{print $1}' $ANT)
echo "$(date '+%F %T') temp=${temp}C reserva=${spare}% desgaste=${used}% erros_de_dado=${media} aviso_critico=${crit} desligamentos_bruscos=${unsafe}" >> $LOG
echo "$media" > $ANT
avisa() {
  /opt/promobot/venv/bin/python - "$1" <<'PY' 2>/dev/null
import sys; sys.path.insert(0, "/opt/promobot")
from app.publisher import alert
alert(sys.argv[1])
PY
}
[ "${media:-0}" -gt "${prev_media:-0}" ] && avisa "SSD externo: erros de dados subiram para $media. Trocar de disco: o robo roda pela copia do pendrive de 64 GB."
[ "${crit:-0x00}" != "0x00" ] && [ -n "$crit" ] && avisa "SSD externo: aviso critico $crit."
[ "${spare:-100}" -lt 90 ] && avisa "SSD externo: reserva de blocos caiu para ${spare}%."
[ "${temp:-0}" -gt 65 ] && avisa "SSD externo: temperatura alta (${temp} C)."
exit 0
