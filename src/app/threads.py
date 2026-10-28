"""Threads @techhammer.br (06/10) — no Threads os LINKS SÃO CLICÁVEIS (diferente do Instagram).

- Ofertas: junto com cada Story (4/dia) sai um post no Threads com a arte de feed + link do produto + link do grupo.
- Jogos: carrossel de jogos também vai pro Threads (ligado em app/games.py).
- Imagem precisa de URL pública: reusa a foto não publicada da Página (app/social._upload_hidden).
- Token de 60 dias: renovado toda semana (refresh) e guardado em data/threads_token.txt (o .env só tem o primeiro).
Limite do Threads: 500 caracteres por post.
"""
import time

import httpx

from app.config import DATA_DIR, settings
from app.log import log

G = "https://graph.threads.net/v1.0"
TOKEN_FILE = DATA_DIR / "threads_token.txt"


def token() -> str:
    try:
        t = TOKEN_FILE.read_text().strip()
        if t:
            return t
    except OSError:
        pass
    return settings.threads_token


def enabled() -> bool:
    return bool(settings.threads_enabled and token())


def _api(method: str, path: str, **data) -> dict:
    data["access_token"] = token()
    r = httpx.request(method, f"{G}/{path}", params=data, timeout=90)
    out = r.json()
    if "error" in out:
        raise RuntimeError(f"threads {path}: {out['error'].get('message')}")
    return out


def _wait(cid: str) -> None:
    for _ in range(20):
        if _api("GET", cid, fields="status").get("status") in ("FINISHED", None):
            return
        time.sleep(3)


MAX_LINKS = 5  # Meta: post com mais de 5 links falha (THREADS_API__LINK_LIMIT_EXCEEDED)


def _caber(text: str) -> str:
    """Texto pronto para o Threads: <= 5 links (os dos grupos sempre ficam) e <= 500 caracteres, sem cortar link no meio."""
    import re

    urls = re.findall(r"https?://\S+", text)
    unicas = list(dict.fromkeys(urls))
    if len(unicas) > MAX_LINKS:
        grupos = [u for u in (settings.group_invite_link, settings.lar_invite_link, settings.telegram_invite_link) if u]
        fixos = [u for u in unicas if any(u.startswith(g) for g in grupos)]
        vagas = max(0, MAX_LINKS - len(fixos))
        ficam = set(fixos)
        for u in unicas:
            if u not in ficam and vagas > 0:
                ficam.add(u)
                vagas -= 1
        for u in unicas:
            if u not in ficam:
                text = text.replace(f": {u}", "").replace(u, "")
    if len(text) > 500:
        corte = text[:500]
        nl = corte.rfind("\n")
        text = corte[:nl] if nl > 250 else corte
        if re.search(r"https?://\S*$", text) and not text.endswith(("/",)) and len(text) == 500:
            text = text[:text.rfind("http")].rstrip()
    return text


def post(text: str, image_urls: list[str] | None = None) -> str:
    """Post de texto, com 1 imagem ou carrossel (2–20 imagens). Retorna o id publicado."""
    text = _caber(text)
    urls = image_urls or []
    if len(urls) >= 2:
        kids = [_api("POST", "me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"] for u in urls[:20]]
        for k in kids:
            _wait(k)
        c = _api("POST", "me/threads", media_type="CAROUSEL", children=",".join(kids), text=text)
    elif urls:
        c = _api("POST", "me/threads", media_type="IMAGE", image_url=urls[0], text=text)
    else:
        c = _api("POST", "me/threads", media_type="TEXT", text=text)
    _wait(c["id"])
    return _api("POST", "me/threads_publish", creation_id=c["id"])["id"]


def offer_text(o) -> str:
    pct = round((1 - o.price / o.old_price) * 100) if o.old_price else 0
    from app.templates import brl
    price = brl(o.price)
    old = brl(o.old_price) if o.old_price else ""
    import random
    from app.social import ENGAGE, HOOKS, HOOKS_HOT
    from app.templates import grupos_threads
    gancho = random.choice(HOOKS if pct else (HOOKS_HOT if getattr(o, "source", "") == "pelando" else HOOKS[:4]))
    engaje = random.choice(ENGAGE)
    titulo = (o.post_title or o.title)
    for n in (120, 100, 80, 60, 40):  # limite do Threads = 500 caracteres: encolhe o título até caber
        lines = [gancho, f"🔥 {titulo[:n]}", f"💰 {('De ' + old + ' por ') if old else ''}{price}{f' (-{pct}%)' if pct else ''}",
                 f"🛒 {o.affiliate_url or o.url}", grupos_threads(), engaje]
        txt = "\n".join(lines)
        if len(txt) <= 495:
            return txt
    return txt[:495]


def refresh() -> None:
    """Renova o token (vale 60 dias; pode renovar depois de 24h de emitido). Agendado 1x/semana."""
    if not token():
        return
    try:
        r = httpx.get("https://graph.threads.net/refresh_access_token",
                      params={"grant_type": "th_refresh_token", "access_token": token()}, timeout=30).json()
        if r.get("access_token"):
            TOKEN_FILE.write_text(r["access_token"])
            TOKEN_FILE.chmod(0o600)
            log.info("threads_token_refreshed", expires_in=r.get("expires_in"))
        else:
            log.error("threads_refresh_failed", error=str(r)[:200])
    except Exception as e:
        log.error("threads_refresh_failed", error=str(e)[:200])
