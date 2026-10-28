"""Cupons gerais do Mercado Livre (página /cupons, lida pelo navegador logado — serviço linkgen).

Regra do dono: só cupons GERAIS. Cupons de uma loja específica ("Em produtos de <loja>") são descartados.
Os cupons do ML não têm código: cada pessoa ativa na própria conta em mercadolivre.com.br/cupons.
O post sempre mostra as regras completas (desconto, onde vale, compra mínima, limite, validade).
"""
import re
from datetime import timedelta

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import Coupon, SessionLocal, now
from app.log import log

ML_COUPONS_URL = "https://www.mercadolivre.com.br/cupons"


def _money(lines: list[str], label: str) -> float | None:
    """'Compra mínima' / 'R$' / '85'  ->  85.0"""
    for i, line in enumerate(lines):
        if line.startswith(label):
            m = re.search(r"R\$\s*([\d.]+(?:,\d{2})?)", " ".join(lines[i:i + 3]))
            if m:
                return float(m.group(1).replace(".", "").replace(",", "."))
    return None


def parse_card(text: str) -> dict | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None
    scope = next((l for l in lines if l.startswith("Em ")), "")
    if re.match(r"Em produtos de ", scope):  # cupom de loja específica: fora
        return None
    expires = next((l for l in lines if l.startswith("Vence")), None)
    return {
        "title": lines[0],
        "scope": scope or "Em todo o site",
        "min_purchase": 0.0 if any("Sem compra mínima" in l for l in lines) else _money(lines, "Compra mínima"),
        "max_discount": _money(lines, "Limite de"),
        "expires_text": expires,
    }


def collect_coupons() -> int:
    if not settings.linkgen_enabled:  # sem navegador (robô leve): os cupons gerais do ML ficam de fora
        return 0
    r = httpx.get(f"{settings.linkgen_url}/coupons", params={"url": ML_COUPONS_URL, "scrolls": 8}, timeout=300)
    cards = r.json().get("coupons", [])
    general = [c for c in (parse_card(x["text"]) for x in cards) if c]
    with SessionLocal() as s:
        for c in general:
            key = f"ml:{c['title']}|{c['min_purchase']}|{c['max_discount']}"[:120]
            row = s.get(Coupon, key) or Coupon(key=key, store="Mercado Livre", first_seen=now())
            row.title, row.scope = c["title"], c["scope"]
            row.min_purchase, row.max_discount, row.expires_text = c["min_purchase"], c["max_discount"], c["expires_text"]
            row.last_seen = now()
            s.merge(row)
        s.commit()
    log.info("coupons_collected", cards=len(cards), general=len(general))
    return len(general)


def active_coupons(session) -> list[Coupon]:
    """Cupons vistos na última coleta (o ML tira da página os que acabaram)."""
    return session.scalars(
        select(Coupon).where(Coupon.last_seen >= now() - timedelta(hours=settings.coupon_refresh_hours * 2))
        .order_by(Coupon.title)
    ).all()


def brl(v: float) -> str:
    return "R$ " + (f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")).removesuffix(",00")


def render_coupon_post(coupons: list[Coupon], channel: str = "whatsapp") -> str:
    b = (lambda s: f"<b>{s}</b>") if channel == "telegram" else (lambda s: f"*{s}*")
    lines = [f"🎟️ {b('CUPONS DO MERCADO LIVRE')}", "Ative na sua conta: mercadolivre.com.br/cupons", ""]
    for c in coupons:
        rules = [c.scope]
        rules.append("sem compra mínima" if not c.min_purchase else f"compra mínima {brl(c.min_purchase)}")
        if c.max_discount:
            rules.append(f"desconto máx. {brl(c.max_discount)}")
        if c.expires_text:
            rules.append(c.expires_text.lower())
        lines += [f"✅ {b(c.title)}", f"   ↳ {' · '.join(rules)}", ""]
    lines += ["⚠️ Cupons sujeitos a disponibilidade e regras do Mercado Livre."]
    from app.templates import invite_lines
    lines += invite_lines(channel=channel)
    if settings.post_hashtag:
        lines.append(settings.post_hashtag)
    return "\n".join(lines)


def coupon_banner(count: int) -> bytes:
    """Arte do post de cupons (regra do dono: todo post tem foto). Amarelo ML, 1080x1080."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1080, 1080), (255, 230, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((70, 230, 1010, 850), radius=48, fill=(255, 255, 255))
    for x in range(110, 990, 44):  # picote do "ticket"
        d.ellipse((x, 535, x + 16, 551), fill=(255, 230, 0))
    font = lambda size: ImageFont.load_default(size=size)
    center = lambda y, text, size, color: d.text((540, y), text, font=font(size), fill=color, anchor="mm")
    center(130, "MERCADO LIVRE", 64, (45, 50, 119))
    center(380, "CUPONS", 150, (45, 50, 119))
    center(480, "DO DIA", 90, (52, 131, 250))
    center(650, f"{count} cupons gerais", 64, (51, 51, 51))
    center(740, "regras completas no post", 46, (110, 110, 110))
    center(960, "mercadolivre.com.br/cupons", 50, (45, 50, 119))
    out = BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def _marker():
    from app.config import DATA_DIR
    return DATA_DIR / "coupons_last_post"


def _today() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()


def coupons_posted_today() -> bool:
    m = _marker()
    return m.exists() and m.read_text().strip() == _today()


def post_coupons() -> None:
    """Post diário de cupons gerais (horário COUPON_POST_HOUR)."""
    from app.publisher import any_channel, send_post

    if not any_channel():
        return
    try:
        collect_coupons()
    except Exception as e:
        log.warning("coupons_refresh_failed", error=str(e)[:200])
    with SessionLocal() as s:
        coupons = active_coupons(s)
        if not coupons:
            log.info("coupons_none")
            return
        send_post({"telegram": render_coupon_post(coupons, "telegram"), "whatsapp": render_coupon_post(coupons, "whatsapp")},
                  coupon_banner(len(coupons)))
    _marker().write_text(_today())
    log.info("coupons_posted", count=len(coupons))
