#!/bin/sh
# Vigia de recursos do Wyse (cron a cada 5 min): RAM disponível < 300 MB ou disco livre < 1 GB -> uma linha em data/alertas.log (no máx. 1 por problema a cada 6 h).
# Só LÊ e anota; não reinicia nada. 15/10/2026.
LOG=/opt/promobot/data/alertas.log
ESTADO=/srv/cache/tmp/vigia_recursos.estado
mkdir -p /srv/cache/tmp
agora=$(date +%s)
avisa() {  # $1 = chave, $2 = mensagem
    ultimo=$(grep "^$1 " "$ESTADO" 2>/dev/null | cut -d' ' -f2)
    if [ -z "$ultimo" ] || [ $((agora - ultimo)) -ge 21600 ]; then
        printf '{"quando": "%s", "msg": "%s"}\n' "$(date -Iseconds)" "$2" >> "$LOG"
        grep -v "^$1 " "$ESTADO" 2>/dev/null > "$ESTADO.novo"; echo "$1 $agora" >> "$ESTADO.novo"; mv "$ESTADO.novo" "$ESTADO"
    fi
}
ram_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
[ "$ram_mb" -lt 300 ] && avisa ram "Wyse com pouca memoria livre: ${ram_mb} MB disponiveis (limite 300 MB)"
for ponto in / /srv/cache; do
    livre_mb=$(df -Pm "$ponto" | awk 'NR==2 {print $4}')
    [ "$livre_mb" -lt 1024 ] && avisa "disco$(echo "$ponto" | tr / _)" "Wyse com pouco disco em $ponto: ${livre_mb} MB livres (limite 1 GB)"
done
exit 0
