#!/bin/sh
# Roda um comando pesado (render de vídeo, transcrição) SEM travar o Wyse: um por vez (flock), prioridade mínima de CPU e de disco,
# e temporários no pen drive (o /tmp é tmpfs de 256 MB). Uso: ferramentas/render.sh <comando...>
# 15/10/2026 — relatório de otimização do Wyse (itens 2, 4 e 6).
mkdir -p /srv/cache/tmp
export TMPDIR=/srv/cache/tmp
exec flock -w 7200 /srv/cache/tmp/render.lock nice -n 19 ionice -c3 "$@"
