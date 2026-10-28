"""Redes da Meta (06/10): Página TechHammer (Facebook) + Instagram @techhammer.br via Graph API.

- Stories (somem em 24h): SOCIAL_STORY_TIMES, a oferta de maior desconto já publicada nas últimas horas e ainda
  não usada nas redes. Instagram + Story da Página.
- Feed: 1 "oferta do dia" em SOCIAL_FEED_TIME. Legenda com OFERTA LIMITADA + link do produto, e o link também
  no 1º comentário (a API não permite fixar comentário; o 1º comentário fica logo abaixo do post).
- Instagram exige a imagem numa URL pública: a arte sobe antes como foto NÃO publicada da Página e usamos a URL dela.
Token da Página é permanente (META_PAGE_TOKEN). Usado: data/social_state.json (ids já usados).
"""
import json
import time
from datetime import timedelta

import httpx
from sqlalchemy import select

from app.config import DATA_DIR, settings
from app.db import Offer, SessionLocal, now
from app.log import log
from app.media import product_jpeg
from app.social_art import render_art

G = "https://graph.facebook.com/v21.0"
STATE = DATA_DIR / "social_state.json"
TAGS = "#ofertas #promoção #tecnologia #descontos #techhammer"


def enabled() -> bool:
    return bool(settings.social_enabled and settings.meta_page_token and settings.meta_page_id)


def _api(method: str, path: str, **data) -> dict:
    files = data.pop("files", None)
    data["access_token"] = settings.meta_page_token
    r = httpx.request(method, f"{G}/{path}", data=data if method == "POST" else None,
                      params=data if method == "GET" else None, files=files, timeout=90)
    out = r.json()
    if "error" in out:
        raise RuntimeError(f"meta {path}: {out['error'].get('message')}")
    return out


def _used() -> set[int]:
    try:
        d = json.loads(STATE.read_text())
    except (OSError, ValueError):
        d = {}
    cut = (now() - timedelta(days=settings.repeat_days)).isoformat()
    return {int(k) for k, v in d.items() if v >= cut}


def _mark(offer_id: int) -> None:
    try:
        d = json.loads(STATE.read_text())
    except (OSError, ValueError):
        d = {}
    d[str(offer_id)] = now().isoformat()
    STATE.write_text(json.dumps(d))


def _pequena(jpeg: bytes, lado: int = 480) -> bool:
    import io

    from PIL import Image
    try:
        w, h = Image.open(io.BytesIO(jpeg)).size
    except Exception:  # noqa: BLE001
        return False
    return min(w, h) < lado


def _pick(hours: int) -> tuple[Offer, bytes] | None:
    """A mais interessante (maior score) entre as publicadas nas últimas `hours` horas, ainda não usada nas redes.

    Vale oferta com desconto real (preço antigo) OU qualquer oferta de tecnologia acima de R$ 30 mesmo sem preço antigo
    (as do Pelando ganham o selo EM ALTA) — sem isso as redes ficavam vazias com o Mercado Livre pausado."""
    from app.engine import is_tech
    used = _used()

    def elegivel(o: Offer) -> bool:
        if o.id in used or not o.price:
            return False
        if o.old_price and o.old_price > o.price:
            return True
        return o.price >= 30 and is_tech(o.title)  # sem preço antigo: vale qualquer oferta de tecnologia (as de maior score saem primeiro)

    with SessionLocal() as s:
        rows = s.scalars(select(Offer).where(Offer.status == "posted", Offer.canal == "tech",  # perfil TechHammer: só tecnologia
                                            Offer.posted_at >= now() - timedelta(hours=hours))).all()
        # mais interessante (score) primeiro; AliExpress perde 12 pontos (as fotos dele costumam ser propaganda)
        rows = sorted((o for o in rows if elegivel(o)), key=lambda o: -((o.score or 0) - (12 if "aliexpress" in o.url else 0)))
        for o in rows:
            photo = product_jpeg(o.image_url)
            if photo and _pequena(photo):  # foto do card pequena: tenta a da página da loja (maior)
                from app.media import validate_photo
                from app.storephoto import store_photos
                for alt in store_photos(o.url)[:3]:
                    cand = product_jpeg(alt)
                    if cand and not _pequena(cand) and validate_photo(cand, o.title)[0]:
                        photo = cand
                        break
            if photo:
                s.expunge(o)
                return o, photo
    return None


HOOKS = ["⚡ OFERTA LIMITADA — pode acabar a qualquer momento!", "🚨 CORRE! Preço desses some rápido",
         "😱 Esse preço tá certo mesmo?!", "🔥 Achado do dia pra quem curte tecnologia",
         "💸 Economia real: olha esse desconto"]
HOOKS_HOT = ["🔥 EM ALTA: a comunidade está votando nessa oferta!", "🚨 Oferta QUENTE do dia — corre!",
             "⚡ Achado bombando agora, olha esse preço"]
ENGAGE = ["💬 Marca aquele amigo que precisa disso!", "💾 Salva pra não perder e manda pra quem vai curtir!",
          "👇 Comenta: compraria por esse preço?", "📤 Compartilha com quem tá montando PC!"]


def _caption(o: Offer, ig: bool) -> str:
    pct = round((1 - o.price / o.old_price) * 100) if o.old_price and o.old_price > o.price else 0
    link = o.affiliate_url or o.url
    import random
    from app.templates import brl
    preco = f"💰 De {brl(o.old_price)} por {brl(o.price)} (-{pct}%)" if pct else f"💰 Por apenas {brl(o.price)}"
    lines = [random.choice(HOOKS if pct else (HOOKS_HOT if getattr(o, "source", "") == "pelando" else HOOKS[:4])), "",
             f"🔥 {o.post_title or o.title}",
             preco, "",
             f"🛒 Link do produto: {link}"]
    if ig:
        lines.append("(link também no 1º comentário 👇)")
    from app.templates import chamada_grupos
    lines += ["", random.choice(ENGAGE), chamada_grupos(clicavel=not ig), "", TAGS]
    return "\n".join(lines)


def _upload_hidden(art: bytes) -> tuple[str, str]:
    """Sobe a arte como foto não publicada da Página -> (photo_id, url pública p/ o Instagram)."""
    r = _api("POST", f"{settings.meta_page_id}/photos", published="false",
             files={"source": ("arte.jpg", art, "image/jpeg")})
    url = _api("GET", r["id"], fields="images")["images"][0]["source"]
    return r["id"], url


def _ig_publish(url: str, caption: str | None, story: bool) -> str:
    data = {"image_url": url}
    if story:
        data["media_type"] = "STORIES"
    else:
        data["caption"] = caption
    c = _api("POST", f"{settings.meta_ig_id}/media", **data)
    for _ in range(20):
        if _api("GET", c["id"], fields="status_code").get("status_code") == "FINISHED":
            break
        time.sleep(3)
    return _api("POST", f"{settings.meta_ig_id}/media_publish", creation_id=c["id"])["id"]


def post_story() -> None:
    if not enabled():
        return
    pick = _pick(hours=24)  # a melhor do dia ainda não usada
    if not pick:
        log.info("social_story_skip", reason="sem oferta nova")
        return
    o, photo = pick
    art = render_art(o, photo, "story")
    photo_id, url = _upload_hidden(art)
    done = []
    if settings.meta_ig_id:
        try:
            _ig_publish(url, None, story=True)
            done.append("instagram")
        except Exception as e:
            log.error("social_story_failed", net="instagram", error=str(e)[:300])
    try:
        _api("POST", f"{settings.meta_page_id}/photo_stories", photo_id=photo_id)
        done.append("facebook")
    except Exception as e:
        log.error("social_story_failed", net="facebook", error=str(e)[:300])
    from app import threads
    if threads.enabled():
        try:
            _, furl = _upload_hidden(render_art(o, photo, "feed"))
            threads.post(threads.offer_text(o), [furl])
            done.append("threads")
        except Exception as e:
            log.error("social_story_failed", net="threads", error=str(e)[:300])
    if done:
        _mark(o.id)
    log.info("social_story", offer_id=o.id, nets=done)


def post_feed() -> None:
    if not enabled():
        return
    pick = _pick(hours=24)
    if not pick:
        log.info("social_feed_skip", reason="sem oferta nova")
        return
    o, photo = pick
    art = render_art(o, photo, "feed")
    link = o.affiliate_url or o.url
    done = []
    try:
        fb = _api("POST", f"{settings.meta_page_id}/photos", caption=_caption(o, ig=False),
                  files={"source": ("arte.jpg", art, "image/jpeg")})
        _api("POST", f"{fb['post_id']}/comments", message=f"🛒 Link do produto (oferta limitada): {link}")
        done.append("facebook")
    except Exception as e:
        log.error("social_feed_failed", net="facebook", error=str(e)[:300])
    if settings.meta_ig_id:
        try:
            _, url = _upload_hidden(art)
            media = _ig_publish(url, _caption(o, ig=True), story=False)
            _api("POST", f"{media}/comments", message=f"🛒 Link do produto: {link}")
            done.append("instagram")
        except Exception as e:
            log.error("social_feed_failed", net="instagram", error=str(e)[:300])
    from app import threads
    if threads.enabled():
        try:
            _, turl = _upload_hidden(art)
            threads.post(threads.offer_text(o), [turl])
            done.append("threads")
        except Exception as e:
            log.error("social_feed_failed", net="threads", error=str(e)[:300])
    if done:
        _mark(o.id)
    log.info("social_feed", offer_id=o.id, nets=done)
