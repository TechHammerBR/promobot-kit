#!/bin/sh
# Vigia de recursos (cron a cada 5 min): RAM disponível < 300 MB ou disco livre < 1 GB -> uma linha em data/alertas.log
# (no máx. 1 por problema a cada 6 h). Só LÊ e anota; não reinicia nada.
LOG=/opt/promobot/data/alertas.log
ESTADO=/opt/promobot/data/vigia_recursos.estado
mkdir -p /opt/promobot/data
agora=$(date +%s)
avisa() {  # $1 = chave, $2 = mensagem
    ultimo=$(grep "^$1 " "$ESTADO" 2>/dev/null | cut -d' ' -f2)
    if [ -z "$ultimo" ] || [ $((agora - ultimo)) -ge 21600 ]; then
        printf '{"quando": "%s", "msg": "%s"}\n' "$(date -Iseconds)" "$2" >> "$LOG"
        grep -v "^$1 " "$ESTADO" 2>/dev/null > "$ESTADO.novo"; echo "$1 $agora" >> "$ESTADO.novo"; mv "$ESTADO.novo" "$ESTADO"
    fi
}
ram_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
[ -n "$ram_mb" ] && [ "$ram_mb" -lt 300 ] && avisa ram "Servidor com pouca memoria livre: ${ram_mb} MB disponiveis (limite 300 MB)"
for ponto in / /srv/cache /srv/backup; do
    [ -d "$ponto" ] || continue          # só confere os pontos que existem neste servidor
    livre_mb=$(df -Pm "$ponto" 2>/dev/null | awk 'NR==2 {print $4}')
    [ -n "$livre_mb" ] && [ "$livre_mb" -lt 1024 ] && avisa "disco$(echo "$ponto" | tr / _)" "Servidor com pouco disco em $ponto: ${livre_mb} MB livres (limite 1 GB)"
done
exit 0
