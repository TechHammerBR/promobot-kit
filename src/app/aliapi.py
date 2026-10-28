"""AliExpress — API oficial de afiliados (Open Platform, categoria "Affiliates API").

Substitui o navegador logado no Portals: busca produtos por palavra e gera o link s.click, tudo por HTTP.
Credenciais no .env: ALI_APP_KEY, ALI_APP_SECRET e ALI_TRACKING_ID (o "default" existe em toda conta).
Assinatura: HMAC-SHA256 (chave = app secret) sobre "nome+valor" de todos os parâmetros em ordem alfabética, em hexadecimal maiúsculo.
Limite do app: 1000 chamadas/min (usamos algumas dezenas por hora). "hotproduct.query" só libera com o app aprovado.
"""
import hashlib
import hmac
import time

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

GATEWAY = "https://api-sg.aliexpress.com/sync"
VAZIO = 405  # resp_code de "The result is empty"


def configured() -> bool:
    return bool(settings.ali_app_key and settings.ali_app_secret)


def sign(params: dict[str, str], secret: str) -> str:
    base = "".join(k + params[k] for k in sorted(params))
    return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


@retry(retry=retry_if_exception_type(httpx.TransportError),
       stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20), reraise=True)
def call(method: str, **params: str) -> dict:
    """Chama um método e devolve o `result` (ou {} se a busca veio vazia)."""
    q = {"app_key": settings.ali_app_key, "timestamp": str(int(time.time() * 1000)), "sign_method": "sha256",
         "method": method, "v": "2.0", **{k: str(v) for k, v in params.items()}}
    q["sign"] = sign(q, settings.ali_app_secret)
    data = httpx.get(GATEWAY, params=q, timeout=30).json()
    err = data.get("error_response")
    if err:
        code = str(err.get("code", ""))
        if "Limit" in code or "Frequency" in code:  # ApiCallLimit / AppCallLimited: espera, não insiste
            from app.collectors.base import BlockedError  # aqui dentro: evita importação circular com os coletores
            raise BlockedError(f"aliexpress api: {code}")
        raise RuntimeError(f"aliexpress api: {code} {str(err.get('msg', ''))[:120]}")
    resp = data.get(method.replace(".", "_") + "_response", {}).get("resp_result", {})
    code = resp.get("resp_code")
    if code == VAZIO:
        return {}
    if code != 200:
        raise RuntimeError(f"aliexpress api: {code} {str(resp.get('resp_msg', ''))[:120]}")
    return resp.get("result") or {}


def search(keyword: str, page: int = 1, page_size: int = 50) -> list[dict]:
    """Produtos de uma palavra-chave, mais vendidos primeiro, preço em reais para entrega no Brasil."""
    extra = {"category_ids": settings.ali_category_ids} if settings.ali_category_ids else {}
    result = call("aliexpress.affiliate.product.query", keywords=keyword, target_currency="BRL", target_language="PT",
                  ship_to_country="BR", sort="LAST_VOLUME_DESC", page_no=page, page_size=page_size,
                  tracking_id=settings.ali_tracking_id, **extra)
    return (result.get("products") or {}).get("product") or []


def link(url: str) -> str:
    """Link curto de afiliado (https://s.click.aliexpress.com/e/_xxxx) para a página de um produto."""
    result = call("aliexpress.affiliate.link.generate", promotion_link_type="0", source_values=url.split("?")[0],
                  tracking_id=settings.ali_tracking_id)
    links = (result.get("promotion_links") or {}).get("promotion_link") or []
    short = links[0].get("promotion_link") if links else None
    if not short:
        raise RuntimeError(f"aliexpress api: link não gerado para {url[:80]}")
    return short


def images(url: str) -> list[str]:
    """Outras fotos do mesmo anúncio (até 6), para quando a principal é propaganda. Lista vazia se não houver/der erro."""
    pid = url.split("/item/")[-1].split(".")[0]
    if not pid.isdigit():
        return []
    result = call("aliexpress.affiliate.productdetail.get", product_ids=pid, target_currency="BRL", target_language="PT",
                  country="BR", tracking_id=settings.ali_tracking_id)
    prods = (result.get("products") or {}).get("product") or []
    if not prods:
        return []
    principal = prods[0].get("product_main_image_url")
    return [u for u in ((prods[0].get("product_small_image_urls") or {}).get("string") or []) if u != principal]
