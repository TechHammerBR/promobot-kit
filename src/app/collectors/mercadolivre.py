"""Mercado Livre — página pública de ofertas (principal, monetizável)."""
import re
import time

import httpx
from selectolax.parser import HTMLParser

from app.collectors.base import BlockedError, Collector, LayoutChangedError
from app.config import settings
from app.log import log
from app.schemas import RawOffer

PAGES = 3  # ~48 ofertas por página
NAVEGADOR_A_CADA_MIN = 60  # pelo navegador (linkgen): uma coleta por hora
PAGINAS_NAVEGADOR = [(None, 1), ("MLB1648", 1), ("MLB1144", 1)]  # geral, informática, games (23/10: caiu de 5 para 3 páginas; ML pôs captcha no navegador)
#                    ("MLB1246", 1), ("MLB1430", 1)]  # CASA/dia a dia: beleza, roupas/calçados (poucas páginas: o ML pôs tela anti-robô em 17/10)
_ultima_navegacao = 0.0


def _html_navegador(url: str) -> str:
    """HTML já renderizado de uma página do ML aberta no navegador do dono (aba única). Verificação/erro -> BlockedError (sem tentar contornar)."""
    base = settings.linkgen_url
    match = "mercadolivre.com.br/ofertas"
    j = httpx.get(f"{base}/tab_goto", params={"match": match, "url": url, "wait": 3500}, timeout=100).json()
    if "error" in j:
        raise BlockedError(f"mercadolivre: navegador: {str(j['error'])[:80]}")
    if "account-verification" in j.get("url", "") or "suspicious" in j.get("url", ""):
        raise BlockedError(f"mercadolivre: verificacao anti-robo no navegador em {url}")
    r = httpx.get(f"{base}/tab_eval", params={"match": match, "js": "document.documentElement.outerHTML"}, timeout=60).json()
    html = r.get("result") or ""
    if "suspicious-traffic" in html[:3000] or "account-verification" in html[:3000]:
        raise BlockedError(f"mercadolivre: verificacao anti-robo no navegador em {url}")
    return html
# Foco do dono: computador/periféricos. Categorias de ofertas (2 páginas cada) + ofertas gerais (página 1).
CATEGORIES = {"MLB1648": 2, "MLB1144": 2, "MLB1051": 1, "MLB1000": 1}  # informática, games, celulares, eletrônicos


def _money(node) -> float | None:
    if node is None:
        return None
    frac = node.css_first(".andes-money-amount__fraction")
    if frac is None:
        return None
    cents = node.css_first(".andes-money-amount__cents")
    value = frac.text(strip=True).replace(".", "")
    return float(f"{value}.{cents.text(strip=True) if cents else '00'}")


class MercadoLivreCollector(Collector):
    @classmethod
    def enabled(cls) -> bool:
        from app.collectors.base import ml_paused
        return not ml_paused() or settings.ml_bonus_mode

    name = "mercadolivre"
    empty_ok = True  # fora da janela de 1 h do navegador a coleta é vazia de propósito

    def collect(self) -> list[RawOffer]:
        global _ultima_navegacao
        offers = []
        via_navegador = settings.linkgen_enabled
        if via_navegador:
            if time.time() - _ultima_navegacao < NAVEGADOR_A_CADA_MIN * 60:
                return []
            _ultima_navegacao = time.time()
        pages = PAGINAS_NAVEGADOR if via_navegador else [(None, 1)] + [(c, p) for c, n in CATEGORIES.items() for p in range(1, n + 1)]
        for cat, page in pages:
            q = ([f"category={cat}"] if cat else []) + ([f"page={page}"] if page > 1 else [])
            url = "https://www.mercadolivre.com.br/ofertas" + ("?" + "&".join(q) if q else "")
            tree = HTMLParser(_html_navegador(url) if via_navegador else self.get(url).text)
            cards = tree.css("div.poly-card")
            if not cards and cat is None:
                raise LayoutChangedError("mercadolivre: nenhum div.poly-card na página de ofertas")
            for card in cards:
                link = card.css_first("a.poly-component__title")
                price = _money(card.css_first(".poly-price__current"))
                if link is None or price is None:
                    continue
                img = card.css_first("img.poly-component__picture")
                href = link.attributes.get("href", "")
                offers.append(RawOffer(
                    source=self.name,
                    title=link.text(strip=True),
                    url=re.sub(r"#.*$", "", href),
                    price=price,
                    old_price=_money(card.css_first("s.andes-money-amount--previous")),
                    image_url=((img.attributes.get("src") if (img.attributes.get("src") or "").startswith("http") else img.attributes.get("data-src")) if img else None),
                    store="Mercado Livre",
                ))
        return offers
