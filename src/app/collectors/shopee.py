"""Shopee — API oficial de Afiliados (GraphQL). O site bloqueia leitura direta; a API já devolve o link com comissão (offerLink).

13/10/2026 (chaves do dono no .env): busca por palavras de TECNOLOGIA em rodízio. Filtro de qualidade (dono: nada de marca duvidosa):
marca conhecida (app/titles.MARCAS) OU loja oficial (Shopee Mall), nota e vendas mínimas. O desconto mínimo é o do engine.
"""
import json

from app.affiliate import shopee_graphql
from app.collectors.base import BlockedError, Collector
from app.config import DATA_DIR, settings
from app.log import log
from app.schemas import RawOffer
from app.titles import marca

STATE = DATA_DIR / "shopee_kw_idx"
QUERY = """{productOfferV2(keyword:%s, sortType:2, page:1, limit:%d){
  nodes{ productName itemId priceMin priceDiscountRate imageUrl offerLink productLink shopName shopType sales ratingStar }
}}"""


def _from_api(n: dict, minimo: float | None = None) -> RawOffer | None:
    try:
        price = float(n.get("priceMin") or 0)
        rate = int(n.get("priceDiscountRate") or 0)
        nota = float(n.get("ratingStar") or 0)
        vendas = int(n.get("sales") or 0)
    except (TypeError, ValueError):
        return None
    titulo = (n.get("productName") or "").strip()
    oficial = 1 in (n.get("shopType") or [])  # 1 = Shopee Mall (loja oficial da marca)
    if price < (settings.shopee_min_price if minimo is None else minimo) or nota < settings.shopee_min_rating or vendas < settings.shopee_min_sold:
        return None
    if not n.get("offerLink") or not n.get("productLink") or not n.get("imageUrl"):
        return None
    preferida = 2 in (n.get("shopType") or [])  # 2 = loja indicada pela Shopee
    # loja comum com marca famosa e preço de banana = falsificado (Logitech G304 a R$ 45, memória HyperX -86%)
    if minimo is not None:  # busca do grupo de CASA: coisa do dia a dia raramente tem marca famosa; basta loja oficial/indicada pela Shopee com nota e vendas boas
        if not (oficial or preferida) or nota < 4.7 or vendas < 300 or rate > settings.shopee_max_discount:
            return None
    elif not (oficial or (preferida and marca(titulo) and not settings.shopee_mall_only)) or rate > settings.shopee_max_discount:
        return None
    old = round(price / (1 - rate / 100), 2) if 0 < rate < 95 else None
    return RawOffer(source="shopee", title=titulo, url=n["productLink"], price=price, old_price=old, image_url=n["imageUrl"],
                    store="Shopee", affiliate_url=n["offerLink"], vendas=vendas, nota=nota)


class ShopeeCollector(Collector):
    name = "shopee"
    empty_ok = True  # as palavras da rodada podem não ter nada com desconto/marca

    @classmethod
    def enabled(cls) -> bool:
        return bool(settings.shopee_app_id and settings.shopee_secret)

    @staticmethod
    def _rodizio(lista: str, estado, n: int) -> list[str]:
        kws = [k.strip() for k in lista.split(",") if k.strip()]
        if not kws or n <= 0:
            return []
        try:
            i = int(estado.read_text()) % len(kws)
        except (OSError, ValueError):
            i = 0
        n = min(n, len(kws))
        estado.write_text(str((i + n) % len(kws)))
        return [kws[(i + j) % len(kws)] for j in range(n)]

    def _next_keywords(self) -> list[tuple[str, float | None]]:
        kws = [(k, None) for k in self._rodizio(settings.shopee_keywords, STATE, settings.shopee_keywords_per_cycle)]
        try:  # produtos quentes do dia (modelos que os canais grandes estão postando); busca na Shopee com o NOSSO link
            from app import trending
            kws += [(k, None) for k in trending.proximas(settings.shopee_trending_per_cycle)]
        except Exception as ex:  # noqa: BLE001
            log.warning("trending_falhou", error=str(ex)[:120])
        if settings.lar_enabled:  # grupo de casa tem a sua própria vez (não disputa com tecnologia) e aceita item barato
            kws += [(k, settings.lar_min_price) for k in
                    self._rodizio(settings.lar_shopee_keywords + "," + settings.lar_busca_shopee_basicos, DATA_DIR / "shopee_lar_idx", settings.lar_shopee_por_ciclo)]
        return kws

    def collect(self) -> list[RawOffer]:
        offers, seen = [], set()
        for kw, minimo in self._next_keywords():
            try:
                data = shopee_graphql(QUERY % (json.dumps(kw), settings.shopee_limit))
            except RuntimeError as e:  # erro devolvido pela API (limite de chamadas, chave inválida...)
                if "10030" in str(e) or "rate limit" in str(e).lower():
                    raise BlockedError(f"shopee: limite da API ({str(e)[:120]})")
                log.warning("shopee_api_erro", keyword=kw, error=str(e)[:200])
                continue
            for n in (data.get("productOfferV2") or {}).get("nodes") or []:
                o = _from_api(n, minimo)
                if o and n.get("itemId") not in seen:
                    seen.add(n.get("itemId"))
                    offers.append(o)
        return offers
