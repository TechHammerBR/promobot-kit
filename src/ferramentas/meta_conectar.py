"""Conecta o Instagram + a Pagina do Facebook ao robo (Meta Graph API) e grava no .env SEM mostrar nenhum token na tela.

Uso (no servidor, na pasta /opt/promobot):  venv/bin/python ferramentas/meta_conectar.py

Voce so precisa ter:  (1) o ID e a chave secreta do APP (developers.facebook.com > seu app > Configuracoes > Basico)
                      (2) um TOKEN DE USUARIO gerado no Explorador da Graph API com as permissoes certas (docs/03, passo 12)
O script: troca o token por um de LONGA DURACAO (~60 dias), lista as suas Paginas, pega o token da PAGINA (nao expira), descobre sozinho o ID da Pagina e o do Instagram
vinculado, confere o @ do Instagram e grava META_APP_ID, META_APP_SECRET, META_USER_TOKEN, META_PAGE_ID, META_PAGE_TOKEN e META_IG_ID no .env (chmod 600).
NAO liga a publicacao: SOCIAL_ENABLED continua como esta (ligue so depois de ver as previas)."""
import getpass
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values

G = "https://graph.facebook.com/v21.0"
ENV = Path(os.getenv("PROMOBOT_ENV", "/opt/promobot/.env"))


def grava(chaves: dict) -> None:
    texto = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    for k, v in chaves.items():
        texto = re.sub(rf"^{k}=.*\n?", "", texto, flags=re.M)
        texto = texto.rstrip("\n") + f"\n{k}={v}\n"
    os.umask(0o077)
    tmp = ENV.with_suffix(".novo")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, ENV)
    os.chmod(ENV, 0o600)


def erro(msg: str) -> None:
    print(f"\n  ERRO: {msg}\n  Nada foi gravado.")
    sys.exit(1)


def main() -> None:
    env = dotenv_values(ENV) if ENV.exists() else {}
    print("\n=== Conectar Meta (Instagram + Pagina do Facebook) ===\n")
    app_id = (env.get("META_APP_ID") or input("ID do app (Configuracoes > Basico): ")).strip()
    app_secret = (env.get("META_APP_SECRET") or getpass.getpass("Chave secreta do app (nao aparece na tela): ")).strip()
    curto = "".join(getpass.getpass("Token de acesso do Explorador da Graph API (nao aparece na tela): ").split())
    if len(curto) < 50 or not app_id or not app_secret:
        erro("faltou o ID do app, a chave secreta ou o token (o token tem mais de 50 caracteres).")
    try:
        r = httpx.get(f"{G}/oauth/access_token", timeout=30, params={"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret, "fb_exchange_token": curto}).json()
        longo = r.get("access_token")
        if not longo:
            erro(f"a Meta recusou o token: {str(r.get('error', {}).get('message', r))[:200]}\n  (o token do Explorador vale ~1 hora: gere outro e tente de novo)")
        pag = httpx.get(f"{G}/me/accounts", timeout=30, params={"access_token": longo, "fields": "id,name,access_token,instagram_business_account{id,username}"}).json()
        paginas = pag.get("data", [])
        if not paginas:
            erro("nenhuma Pagina veio no token. Ao gerar o token, na janela da Meta marque a PAGINA (e o Instagram) que o robo vai usar, e as permissoes do passo 12.")
        print("  Paginas liberadas neste token:")
        for i, p in enumerate(paginas, 1):
            ig = (p.get("instagram_business_account") or {}).get("username")
            print(f"   {i}) {p['name']}  |  Instagram: {'@' + ig if ig else 'NENHUM vinculado'}")
        n = 1 if len(paginas) == 1 else int(input("  Qual Pagina o robo vai usar? (numero): ").strip() or "1")
        p = paginas[n - 1]
        ig = p.get("instagram_business_account") or {}
        if not ig.get("id"):
            erro(f"a Pagina '{p['name']}' nao tem Instagram profissional vinculado. No Instagram: Configuracoes > Conta > Conta profissional; e na Pagina do Facebook: Configuracoes > Contas vinculadas > Instagram.")
        # validade do token de usuario (informativo)
        dbg = httpx.get(f"{G}/debug_token", timeout=30, params={"input_token": longo, "access_token": f"{app_id}|{app_secret}"}).json().get("data", {})
        exp = dbg.get("expires_at") or 0
        grava({"META_APP_ID": app_id, "META_APP_SECRET": app_secret, "META_USER_TOKEN": longo, "META_PAGE_ID": p["id"], "META_PAGE_TOKEN": p["access_token"], "META_IG_ID": ig["id"]})
    except httpx.HTTPError as e:
        erro(f"falha de rede ({str(e)[:150]})")
    print(f"\n  OK: Pagina '{p['name']}' e Instagram @{ig.get('username', '?')} conectados.")
    print(f"  Token da Pagina: NAO expira.   Token de usuario: {'expira em ' + datetime.fromtimestamp(exp).strftime('%d/%m/%Y') if exp else 'sem data (ok)'}.")
    print("  Gravado em .env (chmod 600). Proximo passo: ferramentas/social_verificar.py  e so entao SOCIAL_ENABLED=true.\n")


if __name__ == "__main__":
    main()
