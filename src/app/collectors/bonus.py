"""Fontes bônus (atração): agregadores usados para DESCOBRIR ofertas.

Sempre publicamos o link direto da loja (limpo de afiliados de terceiros),
nunca o link do agregador.
"""
import json
import re
import time

from selectolax.parser import HTMLParser

import httpx

from app.collectors.base import BlockedError, Collector, LayoutChangedError
from app.config import DATA_DIR
from app.schemas import RawOffer

STORE_URL = re.compile(
    r"https?://(?:www\.)?(?:amazon\.com\.br|produto\.mercadolivre\.com\.br|mercadolivre\.com\.br|shopee\.com\.br|"
    r"kabum\.com\.br|magazineluiza\.com\.br|pt\.aliexpress\.com|aliexpress\.com|casasbahia\.com\.br|"
    r"pichau\.com\.br|terabyteshop\.com\.br|netshoes\.com\.br|americanas\.com\.br|carrefour\.com\.br)"
    r"[^\"'<>\s\\]*"
)


class PromobitCollector(Collector):
    name = "promobit"
    empty_ok = True  # com a memória de ofertas já vistas (promobit_seen.json) é normal não haver nada novo numa rodada
    max_redirects = 6  # páginas de redirecionamento abertas por ciclo (gentil com o site: excesso dá HTTP 429)
    pages = ["https://www.promobit.com.br/", "https://www.promobit.com.br/promocoes/informatica/",
             "https://www.promobit.com.br/promocoes/games/", "https://www.promobit.com.br/promocoes/"]
    seen_file = DATA_DIR / "promobit_seen.json"

    def _page_offers(self, url: str) -> list[dict]:
        html = self.get(url).text
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            raise LayoutChangedError("promobit: __NEXT_DATA__ ausente")
        found = []

        def walk(o):
            if isinstance(o, dict):
                if "offerId" in o and "offerTitle" in o:
                    found.append(o)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(json.loads(m.group(1)))
        return found

    def _load_seen(self) -> dict:
        try:
            d = json.loads(self.seen_file.read_text())
        except (OSError, ValueError):
            d = {}
        cutoff = time.time() - 36 * 3600
        return {k: v for k, v in d.items() if k == "_bloqueado_ate" or v > cutoff}

    def collect(self) -> list[RawOffer]:
        found, ids = [], set()
        for i, url in enumerate(self.pages):
            try:
                items = self._page_offers(url)
            except (BlockedError, LayoutChangedError, httpx.HTTPError):
                if i == 0:
                    raise
                continue
            for o in items:
                if o["offerId"] not in ids:
                    ids.add(o["offerId"])
                    found.append(o)
            time.sleep(1.0)
        seen = self._load_seen()
        if seen.get("_bloqueado_ate", 0) > time.time():  # levou 429 há pouco: descansa antes de abrir redirecionamentos
            return []
        candidates = []
        for o in found:
            if str(o["offerId"]) in seen or o.get("offerStatusName") not in (None, "", "APPROVED", "TOP_OFFER"):
                continue
            price = float(o.get("offerPrice") or 0)
            old = float(o.get("offerOldPrice") or 0) or None
            coupon = o.get("offerCoupon") or None
            if price <= 0.05:  # oferta só de cupom
                price, old = 0.0, None
            # só vale abrir o redirect se a oferta tem chance de passar no filtro
            if not coupon and not (old and price and old > price):
                continue
            candidates.append((o, price, old, coupon))
        candidates.sort(key=lambda c: -(1 - c[1] / c[2] if c[2] and c[1] else 0))  # maiores descontos primeiro
        offers = []
        for o, price, old, coupon in candidates[: self.max_redirects]:
            time.sleep(4.0)
            seen[str(o["offerId"])] = time.time()
            try:
                page = self.get(f"https://www.promobit.com.br/Redirect/to/{o['offerId']}/").text
            except BlockedError:
                seen["_bloqueado_ate"] = time.time() + 3 * 3600  # 3 h de descanso (30 min não bastava: voltava a dar 429)
                break
            store_url = STORE_URL.search(page)
            if not store_url:
                continue
            photo = o.get("offerPhoto") or ""
            if photo.startswith("/"):  # o JSON traz só o caminho; a imagem fica no CDN i.promobit.com.br
                photo = "https://i.promobit.com.br" + photo
            offers.append(RawOffer(
                source=self.name,
                title=o["offerTitle"].strip(),
                url=store_url.group(0),
                price=price,
                old_price=old,
                coupon=coupon,
                image_url=photo if photo.startswith("http") else None,
                store=o.get("storeName"),
            ))
        try:
            self.seen_file.write_text(json.dumps(seen))
        except OSError:
            pass
        return offers


class GatryCollector(Collector):
    name = "gatry"

    def collect(self) -> list[RawOffer]:
        tree = HTMLParser(self.get("https://gatry.com/").text)
        offers = []
        for art in tree.css("article"):
            a = art.css_first("h3 a")
            if a is None:
                continue
            href = a.attributes.get("href", "")
            if not STORE_URL.match(href):
                continue
            text = art.text(separator=" ", strip=True)
            prices = [float(p.replace(".", "").replace(",", ".")) for p in re.findall(r"R\$\s*([\d.]+,\d{2})", text)]
            if not prices:
                continue
            img = art.css_first("img")
            src = img.attributes.get("src") if img else None
            coupon = re.search(r"(?:cupom|código)[:\s]+([A-Z0-9]{4,20})\b", text, re.I)
            offers.append(RawOffer(
                source=self.name,
                title=a.text(strip=True),
                url=href,
                price=min(prices),
                old_price=max(prices) if len(prices) > 1 and max(prices) > min(prices) else None,
                coupon=coupon.group(1) if coupon else None,
                image_url=src if src and src.startswith("http") else None,
            ))
        if not offers and tree.css_first("h3 a") is None:
            raise LayoutChangedError("gatry: nenhum h3 a encontrado")
        return offers
