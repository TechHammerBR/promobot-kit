"""Conecta o Threads ao robo e grava o token no .env e em data/threads_token.txt SEM mostrar o token na tela.

Uso (no servidor, na pasta /opt/promobot):  venv/bin/python ferramentas/threads_conectar.py

Voce so precisa ter: a chave secreta do app do THREADS (developers.facebook.com > seu app do Threads > Configuracoes do app > Basico: "Chave secreta do app do Threads")
e um token gerado no painel do app (Casos de uso > Acessar a API do Threads > Configuracoes > "Gerador de token de usuario"), com as permissoes
threads_basic e threads_content_publish. O script confere o token, troca por um de LONGA DURACAO (~60 dias) e o robo renova sozinho toda semana (domingo 4h)."""
import getpass
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

G = "https://graph.threads.net"
ENV = Path(os.getenv("PROMOBOT_ENV", "/opt/promobot/.env"))
ARQ_TOKEN = Path(os.getenv("PROMOBOT_DATA", "/opt/promobot/data")) / "threads_token.txt"


def grava_env(chaves: dict) -> None:
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
    print("\n=== Conectar Threads ===\n")
    segredo = (env.get("THREADS_APP_SECRET") or getpass.getpass("Chave secreta do app do Threads (nao aparece na tela): ")).strip()
    token = "".join(getpass.getpass("Token gerado no painel do app do Threads (nao aparece na tela): ").split())
    if len(token) < 30 or not segredo:
        erro("faltou a chave secreta ou o token.")
    try:
        eu = httpx.get(f"{G}/v1.0/me", timeout=30, params={"fields": "id,username", "access_token": token}).json()
        if "username" not in eu:
            erro(f"o Threads recusou o token: {str(eu.get('error', {}).get('message', eu))[:200]}\n  (o token do gerador vale ~1 hora: gere outro e tente de novo)")
        r = httpx.get(f"{G}/access_token", timeout=30, params={"grant_type": "th_exchange_token", "client_secret": segredo, "access_token": token}).json()
        longo = r.get("access_token")
        if not longo:  # talvez ja seja de longa duracao: tenta renovar
            r2 = httpx.get(f"{G}/refresh_access_token", timeout=30, params={"grant_type": "th_refresh_token", "access_token": token}).json()
            longo = r2.get("access_token")
        if not longo:
            erro(f"nao consegui trocar por um token de longa duracao: {str(r.get('error', {}).get('message', r))[:200]}")
    except httpx.HTTPError as e:
        erro(f"falha de rede ({str(e)[:150]})")
    dias = round(int(r.get("expires_in", 0)) / 86400) if r.get("expires_in") else None
    grava_env({"THREADS_APP_SECRET": segredo, "THREADS_TOKEN": longo})
    ARQ_TOKEN.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    ARQ_TOKEN.write_text(longo, encoding="utf-8")
    os.chmod(ARQ_TOKEN, 0o600)
    print(f"\n  OK: Threads conectado como @{eu['username']}. Token de longa duracao{f' (~{dias} dias)' if dias else ''}; o robo renova toda semana.")
    print("  Proximo passo: ferramentas/social_verificar.py  e so entao THREADS_ENABLED=true.\n")


if __name__ == "__main__":
    main()
