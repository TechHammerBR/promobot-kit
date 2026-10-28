#!/bin/bash
# Grava o acesso da Meta (Página do Facebook + Instagram) no .env do robô SEM passar pelo chat.
# Chamado pelo atalho "Gravar token Meta.bat". O dono cola o token de USUÁRIO gerado no Explorador da Graph API;
# aqui ele vira token de longa duração (60 dias) e dele sai o token da Página (não expira). Só o resultado aparece na tela.
cd /opt/promobot || exit 1
echo
echo "  Cole aqui o token de acesso gerado no site da Meta e aperte ENTER."
echo "  (o texto nao aparece na tela enquanto voce cola: e normal)"
echo
read -rs -p "  Token: " TOKEN
echo
TOKEN=$(printf '%s' "$TOKEN" | tr -d '[:space:]')
if [ ${#TOKEN} -lt 50 ]; then
  echo "  Token vazio ou curto demais. Nada foi gravado."
  exit 1
fi
export TOKEN
./venv/bin/python - <<'EOF'
import os, re
import httpx
from dotenv import dotenv_values

G = "https://graph.facebook.com/v21.0"
e = dotenv_values(".env")
curto = os.environ["TOKEN"]
try:
    r = httpx.get(f"{G}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": e["META_APP_ID"], "client_secret": e["META_APP_SECRET"],
        "fb_exchange_token": curto}).json()
    longo = r.get("access_token")
    if not longo:
        raise SystemExit(f"  ERRO: a Meta recusou o token ({str(r.get('error', {}).get('message', r))[:160]})")
    paginas = httpx.get(f"{G}/me/accounts", timeout=30, params={"access_token": longo, "fields": "id,name,access_token"}).json()
    pagina = next((p for p in paginas.get("data", []) if p["id"] == e.get("META_PAGE_ID")), None)
    if not pagina:
        nomes = ", ".join(p["name"] for p in paginas.get("data", [])) or "nenhuma"
        raise SystemExit(f"  ERRO: a Pagina TechHammer nao veio no token (paginas liberadas: {nomes}). Marque a Pagina ao gerar o token.")
    ig = httpx.get(f"{G}/{e['META_IG_ID']}", timeout=30, params={"access_token": pagina["access_token"], "fields": "username"}).json()
    texto = open(".env", encoding="utf-8").read()
    for k, v in (("META_USER_TOKEN", longo), ("META_PAGE_TOKEN", pagina["access_token"])):
        texto = re.sub(rf"^{k}=.*\n?", "", texto, flags=re.M)
        texto = texto.rstrip("\n") + f"\n{k}={v}\n"
    os.umask(0o077)
    open(".env.novo", "w", encoding="utf-8").write(texto)
    os.replace(".env.novo", ".env")
    os.chmod(".env", 0o600)
    print(f"  OK: Pagina '{pagina['name']}' conectada.")
    print(f"  Instagram: {'@' + ig['username'] if 'username' in ig else 'SEM ACESSO (' + str(ig.get('error', {}).get('message', ''))[:120] + ')'}")
except httpx.HTTPError as x:
    raise SystemExit(f"  ERRO de rede: {str(x)[:160]}")
EOF
unset TOKEN
echo "  Pode fechar esta janela e avisar o Claude."
