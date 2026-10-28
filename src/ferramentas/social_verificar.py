"""Verifica as integracoes de redes sociais SEM publicar nada (so leitura) e nunca imprime segredos.

Uso (no servidor, na pasta /opt/promobot):
  venv/bin/python ferramentas/social_verificar.py            # so leitura: Meta, Threads, YouTube
  venv/bin/python ferramentas/social_verificar.py --escrita  # + teste de ESCRITA na Pagina: sobe uma foto NAO PUBLICADA (invisivel) e apaga em seguida

Cada linha termina em  OK  /  FALHOU  /  nao configurado."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values

ENV = Path(os.getenv("PROMOBOT_ENV", "/opt/promobot/.env"))
DATA = Path(os.getenv("PROMOBOT_DATA", "/opt/promobot/data"))
G = "https://graph.facebook.com/v21.0"
GT = "https://graph.threads.net/v1.0"
env = dotenv_values(ENV) if ENV.exists() else {}
problemas = 0


def linha(ok, titulo: str, detalhe: str = "") -> None:
    global problemas
    if ok is None:
        print(f"  [ -- ] {titulo}: nao configurado {detalhe}")
        return
    print(f"  [{' OK ' if ok else 'FALHOU'}] {titulo} {detalhe}")
    problemas += 0 if ok else 1


def meta(escrita: bool) -> None:
    print("\nMeta (Instagram + Pagina do Facebook)")
    pt, pid, iid = env.get("META_PAGE_TOKEN"), env.get("META_PAGE_ID"), env.get("META_IG_ID")
    if not (pt and pid):
        return linha(None, "Meta", "(rode ferramentas/meta_conectar.py)")
    try:
        pag = httpx.get(f"{G}/{pid}", timeout=30, params={"fields": "name", "access_token": pt}).json()
        linha("name" in pag, "Pagina do Facebook", f"'{pag.get('name')}'" if "name" in pag else str(pag.get("error", {}).get("message", pag))[:120])
        if iid:
            ig = httpx.get(f"{G}/{iid}", timeout=30, params={"fields": "username", "access_token": pt}).json()
            linha("username" in ig, "Instagram", f"@{ig.get('username')}" if "username" in ig else str(ig.get("error", {}).get("message", ig))[:120])
        if env.get("META_APP_ID") and env.get("META_APP_SECRET"):
            d = httpx.get(f"{G}/debug_token", timeout=30, params={"input_token": pt, "access_token": f"{env['META_APP_ID']}|{env['META_APP_SECRET']}"}).json().get("data", {})
            perm = set(d.get("scopes", []))
            faltam = {"pages_manage_posts", "instagram_basic", "instagram_content_publish"} - perm
            linha(bool(d.get("is_valid")), "Token da Pagina valido", "(nao expira)" if not d.get("expires_at") else f"(expira {datetime.fromtimestamp(d['expires_at']):%d/%m/%Y})")
            linha(not faltam, "Permissoes", "completas" if not faltam else "FALTAM: " + ", ".join(sorted(faltam)))
        if escrita:
            png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082")
            up = httpx.post(f"{G}/{pid}/photos", timeout=60, data={"published": "false", "access_token": pt}, files={"source": ("t.png", png, "image/png")}).json()
            ok = "id" in up
            linha(ok, "Escrita na Pagina (foto NAO publicada)", "" if ok else str(up.get("error", {}).get("message", up))[:140])
            if ok:
                dl = httpx.delete(f"{G}/{up['id']}", timeout=30, params={"access_token": pt}).json()
                linha(bool(dl.get("success")), "Foto de teste apagada")
    except httpx.HTTPError as e:
        linha(False, "Meta", f"(rede: {str(e)[:100]})")


def threads() -> None:
    print("\nThreads")
    t = ""
    try:
        t = (DATA / "threads_token.txt").read_text().strip()
    except OSError:
        t = env.get("THREADS_TOKEN") or ""
    if not t:
        return linha(None, "Threads", "(rode ferramentas/threads_conectar.py)")
    try:
        r = httpx.get(f"{GT}/me", timeout=30, params={"fields": "id,username", "access_token": t}).json()
        linha("username" in r, "Conta do Threads", f"@{r.get('username')}" if "username" in r else str(r.get("error", {}).get("message", r))[:120])
    except httpx.HTTPError as e:
        linha(False, "Threads", f"(rede: {str(e)[:100]})")


def youtube() -> None:
    print("\nYouTube")
    cj, tj = DATA / "youtube" / "youtube_client.json", DATA / "youtube" / "youtube_token.json"
    if not (cj.exists() and tj.exists()):
        return linha(None, "YouTube", "(rode ferramentas/youtube_conectar.py)")
    try:
        cli = json.loads(cj.read_text())["installed"]
        tok = json.loads(tj.read_text())
        a = httpx.post(cli.get("token_uri", "https://oauth2.googleapis.com/token"), timeout=30, data={"client_id": cli["client_id"], "client_secret": cli["client_secret"],
                                                                                                         "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).json()
        if "access_token" not in a:
            return linha(False, "Token do YouTube", str(a.get("error_description", a))[:120])
        ch = httpx.get("https://www.googleapis.com/youtube/v3/channels", timeout=30, params={"part": "snippet,statistics", "mine": "true"}, headers={"Authorization": "Bearer " + a["access_token"]}).json()
        it = (ch.get("items") or [None])[0]
        linha(bool(it), "Canal", f"'{it['snippet']['title']}' ({it['statistics'].get('subscriberCount', '?')} inscritos)" if it else str(ch.get("error", {}).get("message", ch))[:120])
    except Exception as e:  # noqa: BLE001
        linha(False, "YouTube", f"({str(e)[:100]})")


if __name__ == "__main__":
    if not ENV.exists():
        print(f"sem .env em {ENV}")
        sys.exit(1)
    meta("--escrita" in sys.argv)
    threads()
    youtube()
    print(f"\n{'Tudo certo.' if not problemas else f'{problemas} problema(s) acima.'} (Nada foi publicado.)\n")
    sys.exit(1 if problemas else 0)
