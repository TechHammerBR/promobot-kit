"""Canais públicos de promoção do Telegram como FONTE (pedido do dono, 13/10/2026).

Lê a página pública `t.me/s/<canal>` (sem login, sem conta), tira título, preço, cupom, foto e link de cada mensagem recente.
O link vem encurtado e com o afiliado do dono do canal: abrimos o encurtador só para descobrir o PRODUTO e guardamos o endereço
limpo da loja (sem nenhum parâmetro). Mercado Livre fica de fora (o meli.la leva à vitrine do afiliado, não ao produto).
Nada é copiado do texto do canal além do nome do produto, preço e cupom; o post sai no nosso formato.
"""
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

from app.collectors.base import BlockedError, Collector
from app.config import DATA_DIR, settings
from app.engine import is_tech
from app.log import log
from app.schemas import RawOffer

VISTOS = DATA_DIR / "canais_vistos.json"
PRECO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?")
CUPOM = re.compile(r"cupom:?\s+[`*]?([A-Z0-9][A-Z0-9_-]{3,19})\b")
IGNORAR_LINK = re.compile(r"t\.me/|telegram\.|whatsapp|wa\.me|youtu|instagram|amazonprime|/prime\b|bit\.ly|adrena\.click|linkmc\.click|"
                          r"meli\.la|mercadoli[vb]re|pcdofafa\.com\.br", re.I)
SO_CUPOM = re.compile(r"^\W*(novo\s+)?cupo(m|ns)\b", re.I)
LOJAS = ("amazon.com.br", "kabum.com.br", "terabyteshop.com.br", "pichau.com.br", "magazineluiza.com.br", "magazinevoce.com.br",
         "shopee.com.br", "aliexpress.com", "casasbahia.com.br", "americanas.com.br", "samsung.com", "girafa.com.br",
         "fastshop.com.br", "carrefour.com.br", "nuuvem.com", "store.playstation.com", "xbox.com", "nintendo.com")


def _texto(no) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", no.html)))


def _limpa(linha: str) -> str:
    """Tira emojis/símbolos das pontas e enfeites de markdown."""
    return re.sub(r"^[^\w\[(]+|[^\w\])\"'%!+]+$", "", linha.replace("*", "").replace("_", " ")).strip()


def extrair(texto: str) -> dict | None:
    """{"title", "price", "coupon"} de uma mensagem de oferta; None se não for oferta de um produto com preço."""
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]
    if not linhas or SO_CUPOM.search(linhas[0]):
        return None
    i = next((k for k, l in enumerate(linhas) if PRECO.search(l)), None)
    if i is None:
        return None
    m = PRECO.search(linhas[i])
    preco = float(m.group(1).replace(".", "") + "." + (m.group(2) or "0"))
    antes = re.split(r"\s+(?:por|-|–|—)\s*$", linhas[i][:m.start()].rstrip())[0]
    titulo = _limpa(antes)
    if len(titulo) < 12 or re.fullmatch(r"(?i)(valor|por|preço|apenas|só|de)\W*", titulo or "x"):  # preço numa linha só dele
        titulo = next((_limpa(l) for l in reversed(linhas[:i]) if "http" not in l and len(_limpa(l)) >= 12), "")
    if len(titulo) < 12 or preco <= 0:
        return None
    c = CUPOM.search(texto)
    return {"title": titulo[:200], "price": preco, "coupon": c.group(1) if c else None}


def loja_limpa(url: str) -> str | None:
    """Endereço do PRODUTO na loja, sem parâmetro nenhum (some o afiliado de quem postou); None se não for página de produto."""
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("m.")
    if not any(host == l or host.endswith("." + l) for l in LOJAS):
        return None
    if "amazon." in host:
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", p.path)
        return f"https://www.amazon.com.br/dp/{m.group(1)}" if m else None
    if "aliexpress." in host:
        m = re.search(r"/item/(\d{12,})", p.path)
        return f"https://pt.aliexpress.com/item/{m.group(1)}.html" if m else None
    if "shopee." in host and not re.search(r"/product/\d+/\d+|-i\.\d+\.\d+", p.path):
        return None  # carteira de cupons, live, página de campanha
    if "kabum." in host and "/produto/" not in p.path:
        return None
    if len(p.path) < 8:
        return None
    return f"https://{p.netloc.lower()}{p.path}"


def mensagens(pagina: str) -> list[dict]:
    out = []
    for m in HTMLParser(pagina).css(".tgme_widget_message"):
        corpo, hora = m.css_first(".tgme_widget_message_text"), m.css_first("time.time")
        if not corpo or not hora or not m.attributes.get("data-post"):
            continue
        foto = m.css_first(".tgme_widget_message_photo_wrap")
        img = re.search(r"url\('([^']+)'\)", foto.attributes.get("style", "")) if foto else None
        links = [a.attributes.get("href", "") for a in corpo.css("a")]
        try:
            quando = datetime.fromisoformat(hora.attributes.get("datetime", ""))
        except ValueError:
            continue
        out.append({"id": m.attributes["data-post"], "text": _texto(corpo), "when": quando, "image": img.group(1) if img else None,
                    "links": [l for l in links if l.startswith("http") and not IGNORAR_LINK.search(l)]})
    return out


class CanaisCollector(Collector):
    name = "canais"
    empty_ok = True  # canal sem oferta nova de tecnologia na rodada não é erro

    @classmethod
    def enabled(cls) -> bool:
        return bool(settings.tg_channels.strip())

    def _resolver(self, link: str) -> str | None:
        direto = loja_limpa(link)
        if direto:
            return direto
        try:
            r = self.client.get(link)
        except httpx.HTTPError:
            return None
        return loja_limpa(str(r.url))

    def collect(self) -> list[RawOffer]:
        # SÓ EMERGÊNCIA (dono, 13/10: "não quero usar eles sempre como base"): lê os canais apenas quando a fila própria está quase vazia
        from sqlalchemy import func, select
        from app.db import Offer, SessionLocal
        with SessionLocal() as s:
            fila = s.scalar(select(func.count()).select_from(Offer).where(Offer.status.in_(("new", "pending")))) or 0
        if fila >= settings.tg_emergency_queue:
            return []
        log.info("canais_emergencia", fila=fila)
        try:
            vistos: dict = json.loads(VISTOS.read_text())
        except (OSError, ValueError):
            vistos = {}
        agora = datetime.now(timezone.utc)
        limite = agora - timedelta(hours=settings.tg_max_age_h)
        offers, abertos, bloqueados = [], 0, 0
        for canal in [c.strip() for c in settings.tg_channels.split(",") if c.strip()]:
            try:
                pagina = self.get(f"https://t.me/s/{canal}").text
            except BlockedError:
                bloqueados += 1
                continue
            except httpx.HTTPError as e:
                log.warning("canal_falhou", canal=canal, error=str(e)[:80])
                continue
            for msg in mensagens(pagina):
                if msg["id"] in vistos or msg["when"] < limite:
                    continue
                vistos[msg["id"]] = int(agora.timestamp())
                d = extrair(msg["text"])
                if not d or not msg["links"] or not msg["image"] or not is_tech(d["title"]):
                    continue
                if abertos >= settings.tg_max_links_per_cycle:
                    del vistos[msg["id"]]  # fica para a próxima rodada
                    continue
                abertos += 1
                url = self._resolver(msg["links"][0])
                time.sleep(1)
                if not url:
                    continue
                try:
                    offers.append(RawOffer(source=self.name, title=d["title"], url=url, price=d["price"], coupon=d["coupon"],
                                           image_url=msg["image"], store=None, temp=settings.tg_temp))
                except ValueError:
                    continue
            time.sleep(1)
        corte = int((agora - timedelta(days=3)).timestamp())
        VISTOS.write_text(json.dumps({k: v for k, v in vistos.items() if v >= corte}))
        if bloqueados and not offers:
            raise BlockedError(f"canais: Telegram recusou {bloqueados} canal(is)")
        return offers
