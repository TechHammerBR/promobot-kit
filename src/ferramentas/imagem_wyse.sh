#!/bin/bash
# Imagem do disco interno do Wyse (eMMC: sistema + robo + banco) SO no pendrive de 16 GB (/srv/backup/imagem-wyse), para recuperacao se o eMMC morrer.
# Semanal (cron domingo 04:30), guarda as 2 ultimas. A imagem e "crash-consistent" (como um desligamento brusco: o ext4 refaz o diario ao restaurar).
# Log: data/logs/imagem_wyse.log
LOG=/opt/promobot/data/logs/imagem_wyse.log
D=/srv/backup/imagem-wyse
exec 9>/tmp/imagem_wyse.lock; flock -n 9 || exit 0
mountpoint -q /srv/backup || { echo "$(date '+%F %T') /srv/backup nao montado, pulei" >> $LOG; exit 1; }
[ "$(df --output=avail -B1 /srv/backup | tail -1)" -gt 6000000000 ] || { echo "$(date '+%F %T') pouco espaco no 16 GB, pulei" >> $LOG; exit 1; }
mkdir -p $D; ts=$(date +%Y%m%d); t0=$(date +%s)
echo "$(date '+%F %T') iniciando imagem $ts" >> $LOG
sync
sudo -n sfdisk -d /dev/mmcblk0 > $D/mmcblk0-particoes-$ts.sfdisk 2>> $LOG
cp /etc/fstab $D/fstab-$ts.txt
for p in 1 2 3; do
  out=$D/mmcblk0p$p-$ts.img.gz
  sudo -n nice -n 19 ionice -c3 dd if=/dev/mmcblk0p$p bs=4M status=none 2>> $LOG | nice -n 19 gzip -1 > $out.tmp
  if gzip -t $out.tmp 2>> $LOG; then mv $out.tmp $out; else echo "$(date '+%F %T') FALHA na imagem p$p" >> $LOG; rm -f $out.tmp; fi
done
( cd $D && sha256sum mmcblk0p?-$ts.img.gz > SHA256-$ts.txt )
cat > $D/COMO-RESTAURAR.txt <<R
Imagem do eMMC do Wyse 3040 ($ts). Particoes: p1 = EFI (vfat), p2 = sistema + robo (ext4), p3 = reserva do fabricante.
Para restaurar (de um pendrive Linux, com o novo eMMC/disco visivel como /dev/mmcblk0):
  1) sfdisk /dev/mmcblk0 < mmcblk0-particoes-$ts.sfdisk
  2) zcat mmcblk0p1-$ts.img.gz | dd of=/dev/mmcblk0p1 bs=4M ; idem p2 e p3
  3) conferir com sha256sum -c SHA256-$ts.txt antes (os .gz) e fsck -f /dev/mmcblk0p2 depois.
Os dados grandes (fila de Reels etc.) ficam no SSD/pendrives e nao estao na imagem; o banco do robo esta em /opt/promobot/data (dentro da p2).
R
# guarda so as 2 ultimas
ls -1 $D/mmcblk0p2-*.img.gz 2>/dev/null | sort | head -n -2 | while read f; do d=$(basename $f | sed 's/mmcblk0p2-\(.*\).img.gz/\1/'); rm -f $D/*-$d.* ; done
echo "$(date '+%F %T') imagem $ts pronta em $(( $(date +%s) - t0 ))s: $(du -sh $D | cut -f1)" >> $LOG
