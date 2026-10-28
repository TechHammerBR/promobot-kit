"""AliExpress — ofertas de tecnologia por palavra-chave (rodízio de ALI_KEYWORDS_PER_CYCLE por coleta), em reais.

Caminho normal: API oficial de afiliados (app/aliapi.py), sem navegador. Preço atual/antigo = target_sale_price /
target_original_price (os mesmos valores "dis!BRL!<original>!<atual>!" do pdp_npi que o Portals mostrava).
Reserva (só se faltarem as chaves da API): Ad Center do Portals lido pelo navegador logado (linkgen).
O link de afiliado (s.click.aliexpress.com) é gerado só na hora de publicar (pipeline._ensure_link).
"""
import re
from urllib.parse import unquote

import httpx

from app import aliapi
from app.collectors.base import Collector, LayoutChangedError
from app.config import DATA_DIR, settings
from app.schemas import RawOffer
from app.titles import mal_traduzido, marca

STATE = DATA_DIR / "aliexpress_kw_index"
PRICE = re.compile(r"dis!BRL!([\d.]+)!([\d.]+)!")
VENDAS = re.compile(r"^(?:(\d\.\d)(?=\d))?\s*([\d.,]+[kK]?)\+?\s*sold\s*$", re.M | re.I)
NOTA = re.compile(r"^\s*(\d\.\d)\s*$", re.M)


def _num(s: str) -> int:
    s = s.strip().lower()
    return int(float(s[:-1]) * 1000) if s.endswith("k") else int(re.sub(r"[.,]", "", s))


def _vendas_nota(text: str) -> tuple[int, float | None]:
    """O cartão junta nota e vendas na mesma linha ('4.5152 sold' = nota 4,5 + 152 vendas): separa as duas."""
    m = VENDAS.search(text)
    n = NOTA.search(text)
    if m:
        return _num(m.group(2)), float(m.group(1)) if m.group(1) else (float(n.group(1)) if n else None)
    return 0, float(n.group(1)) if n else None


def _from_api(p: dict) -> RawOffer | None:
    """Produto devolvido pela API -> oferta (None se for pecinha avulsa, sem vendas ou sem preço)."""
    try:
        price = float(p["target_sale_price"])
        old = float(p.get("target_original_price") or 0)
        sold = int(p.get("lastest_volume") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if sold < settings.ali_min_sold or price < settings.ali_min_price:
        return None
    rate = str(p.get("evaluate_rate") or "").strip().rstrip("%")  # "96.9%" de avaliações positivas -> nota 0-5
    try:
        nota = round(float(rate) / 20, 1) if rate else None
    except ValueError:
        nota = None
    return RawOffer(
        source="aliexpress", title=str(p.get("product_title", "")).strip(),
        url=f"https://pt.aliexpress.com/item/{p["product_id"]}.html",
        price=price, old_price=old if old > price else None,
        image_url=p.get("product_main_image_url"), store="AliExpress", vendas=sold, nota=nota,
    )


class AliExpressCollector(Collector):
    name = "aliexpress"
    empty_ok = True  # a API pode não ter nada novo para as palavras da rodada

    @classmethod
    def enabled(cls) -> bool:
        return settings.ali_enabled

    def _next_keywords(self) -> list[str]:
        kws = [k.strip() for k in settings.ali_keywords.split(",") if k.strip()]
        i = int(STATE.read_text()) if STATE.exists() else 0
        n = settings.ali_keywords_per_cycle
        STATE.write_text(str((i + n) % len(kws)))
        return [kws[(i + j) % len(kws)] for j in range(n)]

    def collect(self) -> list[RawOffer]:
        return self._collect_api() if aliapi.configured() else self._collect_portals()

    def _collect_api(self) -> list[RawOffer]:
        offers, seen = [], set()
        for kw in self._next_keywords():
            for p in aliapi.search(kw):
                offer = _from_api(p)
                if offer is None or p["product_id"] in seen:
                    continue
                if settings.ali_known_brands_only and (marca(offer.title) is None or mal_traduzido(offer.title)):
                    continue  # marca desconhecida ou título de tradução automática
                seen.add(p["product_id"])
                offers.append(offer)
        return offers

    def _collect_portals(self) -> list[RawOffer]:
        offers, seen = [], set()
        for kw in self._next_keywords():
            r = httpx.get(f"{settings.linkgen_url}/ali_offers", params={"q": kw}, timeout=300)
            data = r.json()
            if r.status_code != 200 or "error" in data:
                raise RuntimeError(f"aliexpress: {data.get('error', r.status_code)}")
            if "BRL" not in data.get("region", ""):
                raise LayoutChangedError(f"aliexpress: região não ficou Brasil ({data.get('region')})")
            for c in data["cards"]:
                m_id = re.search(r"/item/(\d+)\.html", c["href"])
                m_price = PRICE.search(unquote(c["href"]))
                if not m_id or not m_price or m_id.group(1) in seen:
                    continue
                seen.add(m_id.group(1))
                old, price = float(m_price.group(1)), float(m_price.group(2))
                sold, nota = _vendas_nota(c["text"])
                if sold < settings.ali_min_sold or price < settings.ali_min_price:  # sem vendas / pecinha avulsa
                    continue
                title = c["text"].split("\n")[0].strip()
                offers.append(RawOffer(
                    source=self.name, title=title, url=f"https://pt.aliexpress.com/item/{m_id.group(1)}.html",
                    price=price, old_price=old if old > price else None,
                    image_url=c.get("image"), store="AliExpress", vendas=sold, nota=nota,
                ))
        return offers
