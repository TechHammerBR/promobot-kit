import hashlib
import re

from pydantic import BaseModel, HttpUrl


class RawOffer(BaseModel):
    """Formato padrão que todo collector deve devolver."""
    source: str
    title: str
    url: HttpUrl
    price: float  # 0 = oferta só de cupom (sem preço fixo)
    old_price: float | None = None
    coupon: str | None = None
    image_url: str | None = None
    store: str | None = None
    affiliate_url: str | None = None  # quando a fonte já entrega o link de afiliado (ex.: Shopee API)
    temp: int | None = None  # votos da comunidade (Pelando): as mais quentes saem primeiro
    vendas: int | None = None  # AliExpress: unidades vendidas (cartão do Portals)
    nota: float | None = None  # AliExpress: avaliação média (0-5)

    @property
    def discount_pct(self) -> int:
        if not self.price or not self.old_price or self.old_price <= self.price:
            return 0
        return round((1 - self.price / self.old_price) * 100)

    @property
    def fingerprint(self) -> str:
        # mesmo produto + mesmo preço = mesma oferta
        norm = re.sub(r"\W+", " ", self.title.lower()).strip()
        return hashlib.sha256(f"{norm}|{self.price:.2f}".encode()).hexdigest()
