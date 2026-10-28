"""Limpeza de links e conversão para links de afiliado do dono."""
import hashlib
import json
import re
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.log import log

SHOPEE_API = "https://open-api.affiliate.shopee.com.br/graphql"

# Parâmetros de rastreio/afiliado de terceiros que nunca devem ir para o canal
STRIP_PARAMS = re.compile(
    r"^(tag|ascsubtag|linkcode|linkid|ref|ref_|psc|smid|camp|creative|creativeasin|"
    r"utm_.*|matt_.*|af_.*|aff_.*|affiliate.*|afid|subid.*|sub_id.*|clickid|gclid|fbclid|"
    r"tracking_id|deal_print_id|position|sid|wid|pdp_filters|dib|dib_tag|qid|sr|s|xpid|ufe|"
    r"marketplaceid|m|th|spm|scm|mmp_pid|uls_trackid|share_.*|smtt|lomadee.*|awc|irclickid)$",
    re.I,
)


def is_shopee(url: str) -> bool:
    return "shopee.com.br" in urlparse(url).netloc


def is_aliexpress(url: str) -> bool:
    return "aliexpress." in urlparse(url).netloc


def aliexpress_link(url: str) -> str:
    """Link de afiliado (s.click.aliexpress.com): API oficial se houver chaves; senão, Portals na aba logada do linkgen."""
    from app import aliapi
    if aliapi.configured():
        return aliapi.link(url)
    r = httpx.get(f"{settings.linkgen_url}/ali_link", params={"url": url}, timeout=180)
    data = r.json()
    if r.status_code != 200 or not data.get("link"):
        raise RuntimeError(f"aliexpress link: {data.get('error', r.status_code)}")
    return data["link"]


def is_mercadolivre(url: str) -> bool:
    host = urlparse(url).netloc
    return "mercadolivre.com.br" in host or "mercadolibre.com" in host


def clean_url(url: str) -> str:
    """Remove afiliados/rastreio de terceiros e encurta URLs conhecidas."""
    url = url.replace("&amp;", "&")
    parts = urlparse(url)
    host = parts.netloc.lower()
    if "amazon." in host:
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", parts.path)
        if m:
            return f"https://{host}/dp/{m.group(1)}"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not STRIP_PARAMS.match(k)]
    return urlunparse(parts._replace(query=urlencode(query), fragment=""))


def mercadolivre_page(url: str, tag: str | None = None) -> dict:
    """Visita o produto com o navegador logado: link oficial meli.la + preço/foto atuais.

    Retorna {"link", "price", "old_price", "image", "title", "available"}.
    """
    r = httpx.get(f"{settings.linkgen_url}/link", params={"url": url, **({"tag": tag} if tag else {})}, timeout=120)
    data = r.json()
    if r.status_code != 200 or not data.get("link"):
        raise RuntimeError(f"linkgen: {data.get('error', r.status_code)}")
    return data


def shopee_graphql(query: str) -> dict:
    payload = json.dumps({"query": query}, separators=(",", ":"))
    ts = str(int(time.time()))
    sig = hashlib.sha256(
        f"{settings.shopee_app_id}{ts}{payload}{settings.shopee_secret}".encode()
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={settings.shopee_app_id}, Timestamp={ts}, Signature={sig}",
    }
    r = httpx.post(SHOPEE_API, content=payload, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"Shopee API: {data['errors']}")
    return data["data"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20), reraise=True)
def shopee_link(url: str) -> str | None:
    if not (settings.shopee_app_id and settings.shopee_secret):
        return None
    q = 'mutation{generateShortLink(input:{originUrl:%s,subIds:["promobot"]}){shortLink}}' % json.dumps(url)
    return shopee_graphql(q)["generateShortLink"]["shortLink"]


def to_affiliate(url: str) -> tuple[str, bool]:
    """Retorna (link_final, monetizado). Sempre limpa afiliados de terceiros."""
    url = clean_url(url)
    try:
        if is_shopee(url):
            link = shopee_link(url)
        elif is_mercadolivre(url):
            link = mercadolivre_link(url)
        else:
            return url, False
    except Exception as e:
        log.error("affiliate_failed", url=url, error=str(e))
        link = None
    return (link, True) if link else (url, False)
