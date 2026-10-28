#!/bin/bash
# Retoma o robo depois de mexer nos pendrives (25/10/2026): monta tudo do fstab, religa o swap, restaura o cron e liga os servicos.
sudo mount -a
mountpoint /srv/backup /srv/cache /srv/espelho
sudo swapon -a
crontab /opt/promobot/data/cron_salvo.txt && echo "cron restaurado"
rm -f /opt/promobot/data/MAINTENANCE
sudo systemctl start promobot-wa promobot-linkgen promobot-tela promobot-bot promobot-fila-reels.timer
sleep 5; systemctl is-active promobot-wa promobot-linkgen promobot-tela promobot-bot promobot-fila-reels.timer
