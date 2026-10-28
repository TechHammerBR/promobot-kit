"""Status (stories) do WhatsApp, recorrente e automático — sem gastar créditos do Claude.

Alterna dois tipos (STATUS_TIMES, ex.: "12:30,20:00"):
- "grupo": arte de divulgação do grupo (logo TechHammer Ofertas) + convite;
- "oferta": melhor oferta publicada no dia, arte premium de Stories + meli.la + convite.
Desligado por padrão (STATUS_ENABLED=false) até o dono aprovar a prévia.
"""
import base64
import io
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.db import Offer, SessionLocal
from app.log import log
from app.media import product_jpeg
from app.social_art import BG, MUTED, TEXT, _font, _hex, render_art
from app.templates import brl

LOGO = Path(__file__).parent / "assets" / "logo-ofertas.png"


LOGO_CASA = Path(__file__).parent / "assets" / "logo-casa.png"


def invite_block(img: Image.Image, top: int, accent: tuple, link_grupo: str | None = None) -> None:
    """QR Code + link do grupo escritos na arte (funciona mesmo sem a legenda)."""
    import qrcode

    w = img.width
    link_grupo = link_grupo or settings.group_invite_link
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(link_grupo)
    q = qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB").resize((250, 250), Image.NEAREST)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(((w - 290) // 2, top, (w + 290) // 2, top + 290), radius=28, fill=(255, 255, 255))
    img.paste(q, ((w - 250) // 2, top + 20))
    link = link_grupo.replace("https://", "")
    d.text((w // 2, top + 335), link, font=_font(30, "bold"), fill=accent, anchor="mm")


def group_promo_art() -> bytes:
    w, h = 1080, 1920
    accent = _hex(settings.accent_color)
    img = Image.new("RGB", (w, h), BG)
    img.paste(Image.open(LOGO).convert("RGB").resize((760, 760), Image.LANCZOS), (160, 120))
    d = ImageDraw.Draw(img)
    d.text((w // 2, 960), "As melhores promoções", font=_font(58, "light"), fill=TEXT, anchor="mm")
    d.text((w // 2, 1045), "de TECNOLOGIA", font=_font(80, "bold"), fill=TEXT, anchor="mm")
    d.text((w // 2, 1135), "todos os dias, num só lugar", font=_font(44, "light"), fill=MUTED, anchor="mm")
    y = 1235
    for t in ("Celulares • Notebooks • Monitores", "Games • Hardware • Fones"):
        d.text((w // 2, y), t, font=_font(38, "regular"), fill=MUTED, anchor="mm")
        y += 58
    d.text((w // 2, 1505), "ENTRE NO GRUPO GRÁTIS", font=_font(46, "bold"), fill=accent, anchor="mm")
    invite_block(img, 1545, accent)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def group_promo_caption() -> str:
    return ("🔨 Grupo só com promoções de TECNOLOGIA!\n\n"
            "Celular, notebook, monitor, fone, games e hardware com desconto de verdade, "
            "preço conferido e cupons todo dia. 🔥\n\n"
            f"Entra aí, é grátis 👇\n{settings.group_invite_link}")


def casa_promo_art() -> bytes:
    """Divulgação do grupo de casa (Meu Lar, Minha Oferta), mesmo molde da arte do TechHammer."""
    w, h = 1080, 1920
    accent = _hex(settings.accent_color)
    img = Image.new("RGB", (w, h), BG)
    from PIL import ImageFilter
    mask = Image.new("L", (760, 760), 0)  # bordas esfumadas: o fundo do logo some no fundo da arte
    ImageDraw.Draw(mask).ellipse((40, 40, 720, 720), fill=255)
    img.paste(Image.open(LOGO_CASA).convert("RGB").resize((760, 760), Image.LANCZOS), (160, 120), mask.filter(ImageFilter.GaussianBlur(40)))
    d = ImageDraw.Draw(img)
    d.text((w // 2, 960), "As melhores promoções", font=_font(58, "light"), fill=TEXT, anchor="mm")
    d.text((w // 2, 1045), "para a sua CASA", font=_font(80, "bold"), fill=TEXT, anchor="mm")
    d.text((w // 2, 1135), "todos os dias, num só lugar", font=_font(44, "light"), fill=MUTED, anchor="mm")
    y = 1235
    for t in ("Cozinha • Eletrodomésticos • Limpeza", "Cama, mesa e banho • Móveis • Ferramentas"):
        d.text((w // 2, y), t, font=_font(38, "regular"), fill=MUTED, anchor="mm")
        y += 58
    d.text((w // 2, 1505), "ENTRE NO GRUPO GRÁTIS", font=_font(46, "bold"), fill=accent, anchor="mm")
    invite_block(img, 1545, accent, settings.lar_invite_link)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def casa_promo_caption() -> str:
    return ("🏠 Grupo só com promoções para a CASA!\n\n"
            "Air fryer, panelas, eletrodomésticos, limpeza, cama, mesa e banho com desconto de verdade "
            "e preço conferido. 🔥\n\n"
            f"Entra aí, é grátis 👇\n{settings.lar_invite_link}")


def best_offer_today():
    since = datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(hours=24)
    with SessionLocal() as s:
        return s.scalars(select(Offer).where(Offer.status == "posted", Offer.posted_at >= since,
                                             Offer.affiliate_url.isnot(None))
                         .order_by(Offer.score.desc())).first()


def offer_status(o) -> tuple[bytes, str] | None:
    photo = product_jpeg(o.image_url)
    if not photo:
        return None
    cta = settings.social_cta
    settings.social_cta = "LINK NA LEGENDA"  # no Status o link vai na legenda (clicável)
    try:
        art = render_art(o, photo, "story")
    finally:
        settings.social_cta = cta
    title = o.post_title or o.title
    caption = (f"🔥 Oferta do dia: {title}\n💰 {brl(o.price)}\n🛒 {o.affiliate_url}\n\n"
               f"Mais ofertas assim no grupo 👇\n{settings.group_invite_link}")
    return art, caption


def build(kind: str) -> tuple[bytes, str] | None:
    if kind == "oferta":
        o = best_offer_today()
        if o:
            built = offer_status(o)
            if built:
                return built
    return group_promo_art(), group_promo_caption()  # reserva: divulgação do grupo


def post_status(kind: str) -> None:
    if not settings.status_enabled:
        return
    built = build(kind)
    if not built:
        return
    art, caption = built
    r = httpx.post(f"{settings.wa_url}/post-status", timeout=120,
                   json={"text": caption, "image_b64": base64.b64encode(art).decode()})
    if r.status_code == 200:
        log.info("status_posted", kind=kind, audience=r.json().get("audience"))
    else:
        log.error("status_failed", kind=kind, error=r.text[:200])
