"""Fotos alternativas direto da página da loja (og:image, JSON-LD, galeria da Amazon).

Usado quando a foto do card do agregador (Pelando/Promobit...) é banner/propaganda: a página do próprio produto costuma ter a
foto limpa de catálogo. Uma visita educada por oferta; se a loja mostrar captcha/bloqueio, desiste (não burla proteção).
"""
import json
import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from app.collectors.base import USER_AGENT
from app.log import log

_LIXO = re.compile(r"logo|sprite|favicon|placeholder|\.svg|icon|banner|avatar|blank|loading", re.I)


def _walk_images(o, out: list[str]) -> None:
    if isinstance(o, dict):
        for k, v in o.items():
            if k.lower() == "image":
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, list):
                    out += [x if isinstance(x, str) else (x.get("url") or "") for x in v if isinstance(x, (str, dict))]
                elif isinstance(v, dict):
                    out.append(v.get("url") or "")
            else:
                _walk_images(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk_images(v, out)


def store_photos(url: str, limit: int = 4) -> list[str]:
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}, timeout=15, follow_redirects=True)
    except httpx.HTTPError:
        return []
    if r.status_code != 200 or "captcha" in r.text[:6000].lower():
        log.info("store_photos_blocked", status=r.status_code, host=str(r.url.host))
        return []
    html, base = r.text, str(r.url)
    tree = HTMLParser(html)
    cands: list[str] = []
    for sel in ('meta[property="og:image"]', 'meta[property="og:image:secure_url"]', 'meta[name="twitter:image"]',
                'link[rel="image_src"]'):
        for n in tree.css(sel):
            v = n.attributes.get("content") or n.attributes.get("href")
            if v:
                cands.append(v)
    for sc in tree.css('script[type="application/ld+json"]'):
        try:
            _walk_images(json.loads(sc.text()), cands)
        except ValueError:
            pass
    if "media-amazon.com" in html:  # Amazon guarda a galeria em JSON dentro do HTML
        cands += re.findall(r'"hiRes":"(https://m\.media-amazon\.com/images/I/[^"]+)"', html)[:3]
        cands += re.findall(r'"large":"(https://m\.media-amazon\.com/images/I/[^"]+)"', html)[:3]
    out: list[str] = []
    for c in cands:
        c = urljoin(base, c.strip())
        if c.startswith("http") and not _LIXO.search(c) and c not in out:
            out.append(c)
    return out[:limit]


def preco_amazon(url: str) -> float | None:
    """Preço atual na página da Amazon ("priceAmount" do bloco de compra). None se não der para ler (bloqueio, layout)."""
    if "amazon.com.br" not in url:
        return None
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}, timeout=15, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or "captcha" in r.text[:6000].lower():
        return None
    m = re.search(r'"priceAmount":([0-9]+(?:\.[0-9]+)?)', r.text)
    return float(m.group(1)) if m else None
