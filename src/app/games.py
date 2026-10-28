"""Carrossel semanal "Promoções da semana em jogos" (pedido do dono 06/10) — Instagram + Página.

Fontes oficiais e públicas: Steam (featuredcategories, cc=br, preço em R$) e Epic Games (jogos GRÁTIS da semana).
Capa + até 9 slides (limite do Instagram = 10). Visual igual às artes de oferta (app/social_art.py).
Sem comissão por enquanto (Steam/Epic não têm afiliado aberto); quando o dono tiver afiliado de loja de jogos
(ex.: Nuuvem/Green Man Gaming) basta trocar o link em GAME_LINK_TEMPLATE.
"""
import io
import json
import math
import re
import textwrap
import time
from datetime import datetime, timedelta, timezone

import httpx
from PIL import Image, ImageDraw

from app.config import DATA_DIR, settings
from app.log import log
from app.social import _api, _upload_hidden
from app.social_art import BG, MUTED, TEXT, _brand, _font, _hex
from app.templates import brl

W, H = 1080, 1350


# ---------------------------------------------------------------- promoções SEM repetir (dono, 08/10: "não repita jogos de uma semana atrás, sempre traga novos destaques")
HISTORICO = DATA_DIR / "games_destaques.json"
DIAS_SEM_REPETIR = 21  # um jogo destacado não volta por 3 semanas (se faltar jogo novo o prazo cai para 14 e depois 7 dias, nunca menos)


def _hist() -> dict:
    try:
        return json.loads(HISTORICO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _appid(g: dict) -> str:
    m = re.search(r"/app/([0-9]+)", g.get("url", ""))
    return m.group(1) if m else g["name"].lower()


def registrar_destaques(games: list[dict], origem: str) -> None:
    """Guarda os jogos de promoção da Steam que ACABARAM de ser postados (carrossel ou Reel) para não voltarem nas próximas semanas."""
    h = _hist()
    hoje = datetime.now(timezone.utc).date().isoformat()
    for g in games:
        if g.get("store") == "Steam" and g.get("price", 0) > 0:
            h[_appid(g)] = {"nome": g["name"], "quando": hoje, "origem": origem}
        elif origem == "gratis":
            h["gratis:" + g["name"].lower()] = {"nome": g["name"], "quando": hoje, "origem": origem}
    corte = (datetime.now(timezone.utc) - timedelta(days=120)).date().isoformat()
    h = {k: v for k, v in h.items() if v.get("quando", "") >= corte}
    HISTORICO.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")


def _recentes(dias: int) -> set:
    corte = (datetime.now(timezone.utc) - timedelta(days=dias)).date().isoformat()
    return {k for k, v in _hist().items() if v.get("quando", "") >= corte}


def _preco(txt: str) -> float:
    t = re.sub(r"[^0-9,]", "", txt or "").replace(",", ".")
    return float(t) if t else 0.0


def _steam_busca(paginas: int = 3) -> list[dict]:
    """Jogos em promoção da Steam pela busca "em promoção" (só jogos, sem free-to-play, ordem de relevância): ~300 candidatos
    com nota e nº de avaliações. A lista "em destaque" da Steam tem só ~8 jogos com desconto e quase não muda de uma semana para outra."""
    from selectolax.parser import HTMLParser
    out = []
    for pg in range(paginas):
        d = httpx.get("https://store.steampowered.com/search/results/", timeout=40, headers={"User-Agent": "Mozilla/5.0"},
                      params={"query": "", "start": pg * 100, "count": 100, "dynamic_data": "", "category1": 998, "specials": 1, "hidef2p": 1,
                              "infinite": 1, "cc": "br", "l": "portuguese"}).json()
        for a in HTMLParser(d.get("results_html", "")).css("a.search_result_row"):
            ids = a.attributes.get("data-ds-appid") or ""
            blk, tit = a.css_first("div.discount_block"), a.css_first("span.title")
            if not ids or "," in ids or blk is None or tit is None:
                continue  # pacote, sem desconto ou linha estranha
            rev = a.css_first("span.search_review_summary")
            m = re.search(r"([0-9]+)% das ([0-9.,]+)", (rev.attributes.get("data-tooltip-html") or "") if rev else "")
            old = blk.css_first("div.discount_original_price")
            out.append({"name": tit.text().strip(), "store": "Steam", "pct": int(blk.attributes.get("data-discount") or 0),
                        "old": _preco(old.text()) if old else 0.0, "price": int(blk.attributes.get("data-price-final") or 0) / 100,
                        "image": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{ids}/capsule_616x353.jpg",
                        "url": f"https://store.steampowered.com/app/{ids}/", "nota": int(m.group(1)) if m else 0,
                        "aval": int(re.sub(r"[^0-9]", "", m.group(2))) if m else 0})
    return out


def _steam_destaques() -> list[dict]:
    """Lista "em destaque" da Steam (poucos jogos): só como reserva se a busca falhar."""
    d = httpx.get("https://store.steampowered.com/api/featuredcategories", params={"cc": "br", "l": "portuguese"}, timeout=30).json()
    out = []
    for it in d.get("specials", {}).get("items", []):
        if it.get("discount_percent", 0) >= 30 and it.get("final_price"):
            out.append({"name": it["name"], "store": "Steam", "pct": it["discount_percent"],
                        "old": it["original_price"] / 100, "price": it["final_price"] / 100,
                        "image": it.get("large_capsule_image") or it["header_image"],
                        "url": f"https://store.steampowered.com/app/{it['id']}/"})
    return out


def steam_deals(n: int = 7, historico: bool = True) -> list[dict]:
    """Os `n` melhores jogos em promoção da Steam que NÃO foram destaque nas últimas semanas (histórico em data/games_destaques.json,
    gravado por registrar_destaques() só depois de postar). Bom = desconto >= 30%, nota >= 80% e >= 500 avaliações; ordem = desconto + popularidade."""
    try:
        cand = _steam_busca()
    except Exception as e:  # noqa: BLE001
        log.warning("steam_busca_falhou", error=str(e)[:150])
        cand = []
    if len(cand) < 12:
        try:
            cand += _steam_destaques()
        except Exception as e:  # noqa: BLE001
            log.warning("steam_destaques_falhou", error=str(e)[:150])
    vistos, bons = set(), []
    for g in cand:
        k = _appid(g)
        if k in vistos or g["pct"] < 30 or g["price"] <= 0 or g.get("nota", 100) < 80 or g.get("aval", 10 ** 6) < 500:
            continue
        vistos.add(k)
        bons.append(g)
    livres = bons
    if historico:
        for dias in (DIAS_SEM_REPETIR, 14, 7):
            excl = _recentes(dias)
            livres = [g for g in bons if _appid(g) not in excl]
            if len(livres) >= n:
                break
        log.info("steam_deals", candidatos=len(bons), novos=len(livres), pedidos=n)
    livres.sort(key=lambda g: -(g["pct"] + 8 * math.log10(g.get("aval", 1000) + 1) + 0.5 * (g.get("nota", 85) - 80)))
    return livres[:n]


def epic_free(quando: datetime | None = None) -> list[dict]:
    """Jogos gratis da Epic validos em `quando` (padrao: agora, com fuso). A API tambem lista os PROXIMOS
    (upcomingPromotionalOffers): com `quando` = quinta 12h30 da para levantar, antes da troca das 12h, o que entra hoje."""
    d = httpx.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
                  params={"locale": "pt-BR", "country": "BR", "allowCountries": "BR"}, timeout=30).json()
    out, nowt = [], quando or datetime.now(timezone.utc)
    for el in d["data"]["Catalog"]["searchStore"]["elements"]:
        promo = el.get("promotions") or {}
        for p in (promo.get("promotionalOffers") or []) + (promo.get("upcomingPromotionalOffers") or []):
            for o in p.get("promotionalOffers", []):
                start = datetime.fromisoformat(o["startDate"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(o["endDate"].replace("Z", "+00:00"))
                if start <= nowt <= end and o.get("discountSetting", {}).get("discountPercentage") == 0:
                    img = next((i["url"] for i in el.get("keyImages", []) if i["type"] in ("OfferImageWide", "DieselStoreFrontWide")),
                               (el.get("keyImages") or [{}])[0].get("url"))
                    slug = (el.get("catalogNs", {}).get("mappings") or [{}])[0].get("pageSlug") or el.get("productSlug")
                    old = el.get("price", {}).get("totalPrice", {}).get("originalPrice", 0) / 100
                    out.append({"name": el["title"], "store": "Epic Games", "pct": 100, "old": old, "price": 0.0,
                                "image": img, "url": f"https://store.epicgames.com/pt-BR/p/{slug}", "until": end})
    return out


def _cover_gratis(count: int, plataformas: list[str]) -> bytes:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand(d, W, 110, accent)
    d.line((W / 2 - 40, 170, W / 2 + 40, 170), fill=accent, width=4)
    d.text((W / 2, 520), "JOGOS", font=_font(120), fill=TEXT, anchor="mm")
    d.text((W / 2, 655), "GRÁTIS", font=_font(150), fill=accent, anchor="mm")
    d.text((W / 2, 790), "DA SEMANA", font=_font(110), fill=TEXT, anchor="mm")
    d.text((W / 2, 930), f"{count} jogos • " + " • ".join(p.title() for p in plataformas[:4]), font=_font(32, "regular"),
           fill=MUTED, anchor="mm")
    d.rounded_rectangle((W / 2 - 230, 1130, W / 2 + 230, 1210), radius=40, outline=accent, width=4)
    d.text((W / 2, 1170), "ARRASTE  →", font=_font(34), fill=TEXT, anchor="mm")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _arte_jogo(url: str | None, nome: str, plataforma: str) -> Image.Image:
    """Arte do jogo; sem imagem (ex.: PS Plus) desenha um cartão com nome e plataforma."""
    for u in (url.split("|") if url else []):  # várias opções separadas por "|": a 1ª que abrir vale
        try:
            r = httpx.get(u, timeout=30, follow_redirects=True)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            pass
    im = Image.new("RGB", (940, 530), (32, 32, 36))
    d = ImageDraw.Draw(im)
    for k, ln in enumerate(textwrap.wrap(nome, 18)[:2]):
        d.text((470, 220 + k * 80), ln, font=_font(64), fill=TEXT, anchor="mm")
    d.text((470, 420), plataforma, font=_font(36, "regular"), fill=MUTED, anchor="mm")
    return im


def _cover(count: int) -> bytes:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand(d, W, 110, accent)
    d.line((W / 2 - 40, 170, W / 2 + 40, 170), fill=accent, width=4)
    d.text((W / 2, 520), "PROMOÇÕES", font=_font(110), fill=TEXT, anchor="mm")
    d.text((W / 2, 650), "DA SEMANA", font=_font(110), fill=TEXT, anchor="mm")
    d.text((W / 2, 790), "EM JOGOS", font=_font(110), fill=accent, anchor="mm")
    d.text((W / 2, 930), f"{count} ofertas selecionadas • Steam • Epic Games", font=_font(34, "regular"), fill=MUTED, anchor="mm")
    d.rounded_rectangle((W / 2 - 230, 1130, W / 2 + 230, 1210), radius=40, outline=accent, width=4)
    d.text((W / 2, 1170), "ARRASTE  →", font=_font(34), fill=TEXT, anchor="mm")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _slide(g: dict, i: int, total: int) -> bytes:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand(d, W, 90, accent)
    art = _arte_jogo(g.get("image"), g["name"], g["store"])
    bw = 940
    art = art.resize((bw, int(art.height * bw / art.width)))
    if art.height > 560:
        art = art.crop((0, (art.height - 560) // 2, bw, (art.height - 560) // 2 + 560))
    mask = Image.new("L", art.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *art.size), radius=36, fill=255)
    top = 190
    im.paste(art, ((W - bw) // 2, top), mask)
    badge = "GRÁTIS" if g["price"] == 0 else f"-{g['pct']}%"
    bf = _font(56)
    tw = d.textlength(badge, font=bf)
    d.rounded_rectangle((90, top + 30, 90 + tw + 60, top + 120), radius=45, fill=accent)
    d.text((90 + 30, top + 75), badge, font=bf, fill=(255, 255, 255), anchor="lm")
    y = top + art.height + 90
    lines = textwrap.wrap(g["name"], 26)[:2]
    for k, ln in enumerate(lines):
        d.text((W / 2, y - (len(lines) - 1) * 32 + k * 64), ln, font=_font(52), fill=TEXT, anchor="mm")
    d.text((W / 2, y + 80), g["store"].upper(), font=_font(30, "regular"), fill=MUTED, anchor="mm")
    if g["old"]:
        old = brl(g['old'])
        of = _font(44, "regular")
        ow = d.textlength(old, font=of)
        d.text((W / 2, y + 180), old, font=of, fill=MUTED, anchor="mm")
        d.line((W / 2 - ow / 2, y + 182, W / 2 + ow / 2, y + 182), fill=MUTED, width=3)
    price = "GRÁTIS" if g["price"] == 0 else brl(g['price'])
    d.text((W / 2, y + 280), price, font=_font(100), fill=TEXT, anchor="mm")
    rodape = g.get("rodape") or "oferta por tempo limitado"
    d.text((W / 2, H - 80), f"{i}/{total}   •   {rodape}", font=_font(28, "regular"), fill=MUTED, anchor="mm")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _caption(games: list[dict]) -> str:
    lines = ["🎮 PROMOÇÕES DA SEMANA EM JOGOS", "⚡ Ofertas por tempo limitado — corre!", ""]
    for g in games:
        p = "GRÁTIS" if g["price"] == 0 else f"{brl(g['price'])} (-{g['pct']}%)"
        lines.append(f"• {g['name']} — {p} na {g['store']}")
    lines += ["", "💾 Salva pra não perder e manda pro amigo que tá sem jogo!",
              "🔧 PC lento pra rodar? A TechHammer faz upgrade e manutenção — chama no direct.",
              __import__("app.templates", fromlist=["x"]).chamada_grupos(False), "",
              "#steam #epicgames #jogosgratis #promoçãodejogos #pcgamer #techhammer"]
    return "\n".join(lines)


def _caption_gratis(games: list[dict]) -> str:
    lines = ["🎮 JOGOS GRÁTIS DA SEMANA", "🆓 Resgate antes que acabe — alguns ficam seus para sempre!", ""]
    for g in games:
        lines.append(f"• {g['name']} — {g['store'].title()}")
    lines += ["", "ℹ️ Epic e Steam: resgatou, é seu. PS Plus, Prime Gaming, Luna e Game Pass: inclusos na assinatura.",
              "💾 Salva e manda pro amigo que vive sem jogo novo!",
              "🔧 PC sofrendo pra rodar? A TechHammer faz upgrade e manutenção — chama no direct.",
              __import__("app.templates", fromlist=["x"]).chamada_grupos(False), "",
              "#jogosgratis #epicgames #psplus #primegaming #gamepass #pcgamer #techhammer"]
    return "\n".join(lines)


def _abre(url: str) -> bool:
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        return r.status_code == 200 and Image.open(io.BytesIO(r.content)).size[0] >= 300
    except Exception:
        return False


def build_gratis(quando=None) -> tuple[list[dict], list[bytes]]:
    from app.game_reels import free_games, steam_lookup
    games, ja = [], _recentes(30)  # dono: jogo já anunciado não volta (PS Plus/Prime/Luna valem o mês inteiro)
    for g in free_games(limit=14, quando=quando):
        if "gratis:" + g["name"].lower() in ja or len(games) >= 9:
            continue
        opcoes = []
        if g.get("image"):
            if "/0x300/" in g["image"]:
                opcoes.append(g["image"].replace("/0x300/", "/0x600/"))  # Pelando: versão maior da mesma imagem
            opcoes.append(g["image"])
        st = steam_lookup(g["name"])
        if st:
            opcoes.append(f"https://cdn.akamai.steamstatic.com/steam/apps/{st['id']}/header.jpg")
        img = next((u for u in opcoes if _abre(u)), None)
        if not img:  # dono: post de jogo sempre com a imagem do jogo
            log.info("gratis_sem_foto", jogo=g["name"])
            continue
        games.append({"name": g["name"], "image": img, "price": 0, "pct": 100, "old": None, "store": g["platform"],
                      "url": g["url"], "rodape": "grátis por tempo limitado"})
    plataformas = list(dict.fromkeys(g["store"] for g in games))
    slides = [_cover_gratis(len(games), plataformas)] + [_slide(g, i + 1, len(games)) for i, g in enumerate(games)]
    return games, slides


def ig_comment(games: list[dict]) -> str:
    """Instagram não deixa link clicável em comentário: só nomes + loja, e chamada pro grupo (lá os links funcionam)."""
    lines = ["🎮 Onde encontrar:"] + [f"• {g['name']} → {g['store']}" for g in games]
    lines += ["", "🔍 É só buscar o nome na loja.",
              "🔗 Links diretos no nosso grupo do WhatsApp e canal do Telegram (link na bio)!"]
    return "\n".join(lines)


def send_groups(games: list[dict], cover: bytes, titulo: str = "PROMOÇÕES DA SEMANA EM JOGOS") -> None:
    """Mesmo post no grupo do WhatsApp e no canal do Telegram, com links CLICÁVEIS."""
    import html
    from app.publisher import send_post
    wa = [f"🎮 *{titulo}*", "⚡ Por tempo limitado!", ""]
    tg = [f"🎮 <b>{titulo}</b>", "⚡ Por tempo limitado!", ""]
    for g in games:
        p = "GRÁTIS" if g["price"] == 0 else f"{brl(g['price'])} (-{g['pct']}%)"
        wa += [f"• *{g['name']}* — {p} na {g['store'].title() if g['price'] == 0 else g['store']}", f"  {g['url']}"]
        tg.append(f'• <a href="{g["url"]}">{html.escape(g["name"])}</a> — {p} na {g["store"]}')
    try:
        from app.templates import invite_lines
        send_post({"whatsapp": "\n".join(wa + invite_lines()), "telegram": "\n".join(tg + invite_lines(channel="telegram"))}, cover)
    except Exception as e:
        log.error("games_groups_failed", error=str(e)[:300])


def build() -> tuple[list[dict], list[bytes]]:
    games = list({g["name"]: g for g in epic_free()[:2] + steam_deals(9)}.values())
    games = games[:9]
    slides = [_cover(len(games))] + [_slide(g, i + 1, len(games)) for i, g in enumerate(games)]
    return games, slides


def post_gratis() -> None:
    """Quinta: carrossel JOGOS GRÁTIS DA SEMANA (substitui o Reel, que exigia vídeo)."""
    post_weekly(gratis=True)


def post_weekly(gratis: bool = False) -> None:
    from app.social import enabled
    if not enabled():
        return
    games, slides = build_gratis() if gratis else build()
    if len(games) < 3:
        log.info("games_skip", reason="poucas ofertas", count=len(games), gratis=gratis)
        return
    caption = _caption_gratis(games) if gratis else _caption(games)
    titulo = "JOGOS GRÁTIS DA SEMANA" if gratis else "PROMOÇÕES DA SEMANA EM JOGOS"
    links = "\n".join(f"{g['name']}: {g['url']}" for g in games)
    ids, urls = zip(*(_upload_hidden(s) for s in slides))
    done = []
    try:
        from app.templates import chamada_grupos
        fb_msg = caption.replace(chamada_grupos(False), chamada_grupos(True)) + "\n\n🔗 Links:\n" + links
        _api("POST", f"{settings.meta_page_id}/feed", message=fb_msg,
                  **{f"attached_media[{n}]": f'{{"media_fbid":"{i}"}}' for n, i in enumerate(ids)})
        done.append("facebook")
    except Exception as e:
        log.error("games_failed", net="facebook", error=str(e)[:300])
    try:
        kids = [_api("POST", f"{settings.meta_ig_id}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
        c = _api("POST", f"{settings.meta_ig_id}/media", media_type="CAROUSEL", caption=caption, children=",".join(kids))
        for _ in range(30):
            if _api("GET", c["id"], fields="status_code").get("status_code") == "FINISHED":
                break
            time.sleep(4)
        m = _api("POST", f"{settings.meta_ig_id}/media_publish", creation_id=c["id"])["id"]
        _api("POST", f"{m}/comments", message=ig_comment(games))
        done.append("instagram")
    except Exception as e:
        log.error("games_failed", net="instagram", error=str(e)[:300])
    from app import threads
    if threads.enabled():
        try:
            txt = f"🎮 {titulo} ⚡\n" + "\n".join(
                f"• {g['name'][:28]}: {g['url']}" for g in games[:6])
            from app.templates import grupos_threads
            txt += "\n\n" + grupos_threads()
            threads.post(txt, list(urls))
            done.append("threads")
        except Exception as e:
            log.error("games_failed", net="threads", error=str(e)[:300])
    send_groups(games, slides[0], titulo)
    if done:
        registrar_destaques(games, "gratis" if gratis else "carrossel")
    log.info("games_weekly", games=len(games), nets=done)
