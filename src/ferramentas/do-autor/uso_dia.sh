#!/bin/bash
# Resumo do uso da máquina num dia, por hora (lê data/uso.log). Uso: ferramentas/uso_dia.sh [AAAA-MM-DD] [watts fixos fora do processador] [R$/kWh]
# Tomada estimada = watts do processador (medido) + resto da placa e pen drives (padrão 2.5 W, estimativa; troque se medir na tomada).
DIA=${1:-$(date +%F)}; BASE=${2:-2.5}; TARIFA=${3:-1.04}
awk -v d="$DIA" -v base="$BASE" -v tar="$TARIFA" '
$1==d { h=substr($2,1,2); n[h]++; c[h]+=$3; if($3>cm[h])cm[h]=$3; m[h]+=$4; if($5>tm[h])tm[h]=$5; w[h]+=$6; N++; C+=$3; M+=$4; W+=$6; if($4>MM)MM=$4; if($5>TM)TM=$5 }
END {
  if(!N){print "sem amostras em " d; exit}
  print "hora  cpu%med  cpu%pico  memMB  tempC  W(proc)"
  for(i=0;i<24;i++){h=sprintf("%02d",i); if(n[h]) printf "%sh   %6.1f   %7.1f  %5d  %5d  %6.2f\n", h, c[h]/n[h], cm[h], m[h]/n[h], tm[h], w[h]/n[h]}
  wt=W/N+base; kwh=wt*24/1000
  printf "\ndia %s: %d amostras | cpu media %.1f%% | memoria media %d MB (pico %d) | temp max %d C\n", d, N, C/N, M/N, MM, TM
  printf "processador %.2f W + resto %.1f W = ~%.1f W na tomada | %.3f kWh em 24 h | R$ %.2f por dia, R$ %.2f por mes (tarifa R$ %.2f/kWh)\n", W/N, base, wt, kwh, kwh*tar, kwh*tar*30, tar
}' /opt/promobot/data/uso.log
