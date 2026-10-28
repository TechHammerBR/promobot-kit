#!/bin/bash
# Grava o token da API da Awin no .env do robô SEM passar pelo chat (chamado pelo atalho "Gravar token Awin.bat").
cd /opt/promobot || exit 1
echo
echo "  Cole aqui o token da API da Awin e aperte ENTER."
echo "  (o texto nao aparece na tela enquanto voce cola: e normal)"
echo
read -rs -p "  Token: " TOKEN
echo
TOKEN=$(printf '%s' "$TOKEN" | tr -d '[:space:]')
if [ ${#TOKEN} -lt 20 ]; then
  echo "  Token vazio ou curto demais. Nada foi gravado."
  exit 1
fi
umask 077
grep -v '^AWIN_TOKEN=' .env > .env.novo
printf 'AWIN_TOKEN=%s\n' "$TOKEN" >> .env.novo
mv .env.novo .env
chmod 600 .env
unset TOKEN
echo "  Token gravado. Testando a conexao com a Awin..."
./venv/bin/python - <<'EOF'
import json
from app import awin
try:
    print(json.dumps(awin.situacao(), ensure_ascii=False, indent=2))
except Exception as e:
    print("  ERRO ao falar com a Awin:", str(e)[:200])
EOF
sudo systemctl restart promobot-bot
echo "  Robo reiniciado. Pode fechar esta janela."
