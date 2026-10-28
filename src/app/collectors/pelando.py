"""Pelando — ofertas votadas pela comunidade (página pública).

Dois jeitos de achar ofertas (os dados vêm embutidos em JSON na página: título, temperatura = votos, preço, status, loja):
1) Páginas gerais (mais-quentes, recentes, busca/aliexpress): só ofertas bem votadas (PELANDO_MIN_TEMP). Oferta nova ainda
   não juntou votos, então esse caminho enxerga pouco.
2) BUSCA POR PALAVRA de tecnologia (PELANDO_SEARCH_TERMS, rodízio de PELANDO_SEARCH_PER_CYCLE termos por coleta): acha
   centenas de ofertas de tecnologia ativas e aceita temperatura menor (PELANDO_SEARCH_MIN_TEMP), porque a busca já filtra o assunto.
A temperatura vira pontuação (as mais votadas saem primeiro). O Pelando não informa o preço antigo: o voto da comunidade
substitui o filtro de desconto. Link de afiliado só onde existe (AliExpress/ML); das demais lojas é link limpo (bônus de atração).
"""
import html
import re
import time
from datetime import datetime, timedelta, timezone

from app.collectors.base import BlockedError, Collector, LayoutChangedError
from app.config import DATA_DIR, settings
from app.engine import is_lar, is_tech
from app.log import log
from app.schemas import RawOffer

PAGES = ["mais-quentes", "mais-quentes?page=2", "recentes", "recentes?page=2", "recentes?page=3", "recentes?page=4",
         "recentes?page=5", "busca/aliexpress"]
ITEM = re.compile(
    r'"title":\[0,"([^"]*)"\],"temperature":\[0,(-?\d+)\].*?"price":\[0,([\d.]+|null)\].*?'
    r'"status":\[0,"(\w+)"\].*?"createdAt":\[0,"([^"]+)"\].*?"imageSrcset":\[1,\[(.*?)\]\]\].*?'
    r'"kind":\[0,"(\w+)"\],"sourceUrl":\[0,"([^"]*)"')
ALI_ID = re.compile(r"aliexpress\.com/(?:item/|.*?[?&]productIds=)(\d{12,})")
ML_ITEM = re.compile(r"mercadoli[bv]re\.com\.br/")


def parse(page: str) -> list[dict]:
    out = []
    for title, temp, price, status, created, srcset, kind, src in ITEM.findall(html.unescape(page)):
        imgs = re.findall(r'"url":\[0,"([^"]+)"\]', srcset)
        out.append({"title": title, "temp": int(temp), "price": float(price) if price != "null" else 0.0,
                    "status": status, "kind": kind, "url": src, "image": imgs[-1] if imgs else None,
                    "created": datetime.fromisoformat(created.replace("Z", "+00:00"))})
    return out


class PelandoCollector(Collector):
    name = "pelando"
    empty_ok = True
    idx_file = DATA_DIR / "pelando_search_idx"

    @classmethod
    def enabled(cls) -> bool:
        return settings.pelando_enabled

    def _to_offer(self, d: dict, search: bool) -> RawOffer | None:
        min_temp = settings.pelando_search_min_temp if search else settings.pelando_min_temp
        if d["kind"] != "promotion" or d["status"] != "active" or not d["price"] or d["temp"] < min_temp:
            return None
        m = ALI_ID.search(d["url"])
        if m:
            url, store = f"https://pt.aliexpress.com/item/{m.group(1)}.html", "AliExpress"
        elif ML_ITEM.search(d["url"]):
            url, store = d["url"].split("#")[0], "Mercado Livre"
        elif d["url"].startswith("http") and (
                (is_tech(d["title"]) and (search or d["temp"] >= settings.pelando_bonus_min_temp))
                or (not search and d["temp"] >= settings.pelando_bonus_any_temp and d["price"] >= 30)
                or (settings.lar_enabled and is_lar(d["title"]) and not is_tech(d["title"])
                    and (search or d["temp"] >= settings.lar_pelando_min_temp))):
            url, store = d["url"].split("#")[0], None  # bônus: oferta votada de outra loja (fora de tech só se bombando; a IA ainda julga)
        else:
            return None
        return RawOffer(source=self.name, title=d["title"], url=url, price=d["price"], image_url=d["image"], store=store, temp=d["temp"])

    def _next_terms(self) -> list[str]:
        terms = [t.strip() for t in settings.pelando_search_terms.split(",") if t.strip()]
        if not terms or settings.pelando_search_per_cycle <= 0:
            return []
        n = min(settings.pelando_search_per_cycle, len(terms))
        try:
            i = int(self.idx_file.read_text()) % len(terms)
        except (OSError, ValueError):
            i = 0
        try:
            self.idx_file.write_text(str((i + n) % len(terms)))
        except OSError:
            pass
        escolhidos = [terms[(i + k) % len(terms)] for k in range(n)]
        if settings.lar_enabled:  # grupo de casa: rodízio próprio, além dos termos de tecnologia
            casa = [t.strip() for t in (settings.lar_pelando_terms + "," + settings.lar_busca_pelando_basicos).split(",") if t.strip()]
            f = DATA_DIR / "pelando_lar_idx"
            try:
                j = int(f.read_text()) % len(casa)
            except (OSError, ValueError):
                j = 0
            m = min(settings.lar_pelando_por_ciclo, len(casa))
            try:
                f.write_text(str((j + m) % len(casa)))
            except OSError:
                pass
            escolhidos += [casa[(j + k) % len(casa)] for k in range(m)]
        return escolhidos

    def collect(self) -> list[RawOffer]:
        since = datetime.now(timezone.utc) - timedelta(hours=settings.pelando_max_age_h)
        seen, offers, parsed = set(), [], 0

        def add(d: dict, search: bool) -> None:
            if d["created"] < since:
                return
            o = self._to_offer(d, search)
            if o is None or str(o.url) in seen:
                return
            seen.add(str(o.url))
            offers.append(o)

        for path in PAGES:
            items = parse(self.get(f"https://www.pelando.com.br/{path}").text)
            parsed += len(items)
            for d in items:
                add(d, search=False)
        if not parsed:
            raise LayoutChangedError("pelando: 0 itens nas páginas (layout mudou?)")
        found_by_search = 0
        for term in self._next_terms():
            time.sleep(0.8)
            try:
                items = parse(self.get("https://www.pelando.com.br/busca/" + term.replace(" ", "-")).text)
            except BlockedError:
                log.warning("pelando_search_blocked", term=term)
                break  # descansa até a próxima coleta; mantém o que já achou
            except Exception as e:  # noqa: BLE001
                log.warning("pelando_search_failed", term=term, error=str(e)[:100])
                continue
            before = len(offers)
            for d in items:
                add(d, search=True)
            found_by_search += len(offers) - before
        log.info("pelando_search", novas=found_by_search)
        return offers  # vazio é normal (empty_ok)
