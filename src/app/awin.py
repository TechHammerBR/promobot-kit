"""Awin (rede de afiliados): link comissionado das lojas em que o dono foi APROVADO (13/10/2026: KaBuM pendente).

- O link de rastreio não precisa de API: https://www.awin1.com/cread.php?awinmid=<loja>&awinaffid=<afiliado>&ued=<destino>.
- Com AWIN_TOKEN no .env o robô (a) descobre sozinho em quais lojas já foi aprovado (programmes?relationship=joined, guardado
  por 6 h em data/awin_aprovadas.json) e (b) pede o link curto (tidd.ly) ao Link Builder. Sem token: só as lojas listadas à mão em
  AWIN_APPROVED_MIDS, com o link longo.
- Loja NÃO aprovada nunca recebe link Awin (link sem aprovação não comissiona e pode gerar advertência).
- REGRAS (ver CLAUDE.md, seção AWIN): cupom só o enviado pela Awin (engine.cupom_proibido); Samsung só aceita promoção vinda da
  própria plataforma -> fica FORA do mapa de lojas daqui de propósito.
"""
import json
import time
from urllib.parse import quote, urlparse

import httpx

from app.config import DATA_DIR, settings
from app.log import log

API = "https://api.awin.com"
CACHE = DATA_DIR / "awin_aprovadas.json"
VALIDADE_S = 6 * 3600


def _lojas() -> dict[str, int]:
    """{"kabum.com.br": 17729} a partir de AWIN_MERCHANTS="kabum.com.br:17729,..."."""
    out = {}
    for par in settings.awin_merchants.split(","):
        host, _, mid = par.strip().partition(":")
        if host and mid.isdigit():
            out[host.lower()] = int(mid)
    return out


def loja_de(url: str) -> int | None:
    host = urlparse(str(url)).netloc.lower()
    return next((mid for h, mid in _lojas().items() if host == h or host.endswith("." + h)), None)


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.awin_token}", "Accept": "application/json"}


def aprovadas(forcar: bool = False) -> set[int]:
    """IDs das lojas em que a conta está aprovada."""
    fixas = {int(x) for x in settings.awin_approved_mids.split(",") if x.strip().isdigit()}
    if not (settings.awin_token and settings.awin_publisher_id):
        return fixas
    try:
        c = json.loads(CACHE.read_text())
        if not forcar and time.time() - c["quando"] < VALIDADE_S:
            return fixas | set(c["ids"])
    except (OSError, ValueError, KeyError):
        c = {"ids": []}
    try:
        r = httpx.get(f"{API}/publishers/{settings.awin_publisher_id}/programmes", params={"relationship": "joined"},
                      headers=_headers(), timeout=30)
        r.raise_for_status()
        ids = [int(p["id"]) for p in r.json() if "id" in p]
        novas = set(ids) - set(c.get("ids", []))
        if novas:
            log.info("awin_lojas_aprovadas", novas=sorted(novas))
        CACHE.write_text(json.dumps({"quando": time.time(), "ids": ids}))
        return fixas | set(ids)
    except Exception as e:  # API fora do ar/token inválido: fica com o que já sabia (nunca inventa aprovação)
        log.warning("awin_api_falhou", error=str(e)[:160])
        return fixas | set(c.get("ids", []))


def aplicavel(url: str) -> bool:
    mid = loja_de(url)
    return bool(mid and settings.awin_publisher_id and mid in aprovadas())


def link(url: str) -> str | None:
    """Link comissionado para a página do produto; None se a loja não é Awin ou a conta ainda não foi aprovada nela."""
    mid = loja_de(url)
    if not (mid and settings.awin_publisher_id and mid in aprovadas()):
        return None
    longo = f"https://www.awin1.com/cread.php?awinmid={mid}&awinaffid={settings.awin_publisher_id}&ued={quote(str(url), safe='')}"
    if not settings.awin_token:
        return longo
    try:
        r = httpx.post(f"{API}/publishers/{settings.awin_publisher_id}/linkbuilder/generate", headers=_headers(), timeout=30,
                       json={"advertiserId": mid, "destinationUrl": str(url), "shorten": True})
        r.raise_for_status()
        d = r.json()
        return d.get("shortUrl") or d.get("url") or longo
    except Exception as e:
        log.warning("awin_link_curto_falhou", error=str(e)[:160])
        return longo


_CUPONS: dict[int, tuple[float, list]] = {}


def cupons(mid: int) -> list[dict]:
    """Cupons (vouchers) ATIVOS que a própria Awin publicou para a loja: [{"code", "title", "url"}]. Vazio se não aprovado/sem token."""
    if not settings.awin_token or mid not in aprovadas():
        return []
    quando, lista = _CUPONS.get(mid, (0, []))
    if time.time() - quando < 3600:
        return lista
    try:
        r = httpx.post(f"{API}/publisher/{settings.awin_publisher_id}/promotions", headers=_headers() | {"Content-Type": "application/json"},
                       timeout=30, json={"filters": {"advertiserIds": [mid], "membership": "joined", "type": "voucher", "status": "active"},
                                         "pagination": {"page": 1, "pageSize": 50}})
        r.raise_for_status()
        lista = [{"code": (p.get("voucher") or {}).get("code"), "title": (p.get("title") or "")[:120], "url": p.get("urlTracking")}
                 for p in r.json().get("data", [])]
        lista = [c for c in lista if c["code"] and not (c["url"] or "").rstrip("/").endswith(c["code"])
                 and "participantes" not in c["title"].lower() and "selecionad" not in c["title"].lower()]
    except Exception as e:
        log.warning("awin_cupons_falhou", error=str(e)[:160])
    _CUPONS[mid] = (time.time(), lista)
    return lista


def situacao() -> dict:
    """Para o `ctl` e para o atalho de gravação do token: o que a API enxerga agora."""
    ap = aprovadas(forcar=True)
    return {"token": bool(settings.awin_token), "afiliado": settings.awin_publisher_id,
            "lojas_do_robo": {h: ("aprovada" if m in ap else "aguardando aprovação") for h, m in _lojas().items()},
            "total_de_lojas_aprovadas_na_conta": len(ap)}
