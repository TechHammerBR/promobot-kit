"""Artes para redes sociais (Stories 1080x1920 e feed 1080x1350) — visual minimalista/premium.

Fundo quase preto, laranja da marca só em detalhes, produto em cartão claro com sombra suave.
Usa a foto JÁ VALIDADA do produto (app/media.py). Sem emojis na imagem (ficam na legenda).
Identidade no .env: BRAND_NAME, ACCENT_COLOR, SOCIAL_CTA.
"""
import io
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import settings
from app.templates import brl

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_LIGHT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf"

BG = (11, 11, 13)
CARD = (244, 244, 246)
TEXT = (245, 245, 247)
MUTED = (140, 140, 150)


def _font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    path = {"bold": FONT_BOLD, "regular": FONT_REGULAR, "light": FONT_LIGHT}[weight]
    for p in (path, FONT_REGULAR):
        try:  # DejaVu tem acentos (ç, ã...); a fonte padrão do Pillow não
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _spaced(text: str) -> str:
    return " ".join(text.upper())


def _hammer(d: ImageDraw.ImageDraw, x: int, y: int, size: int, color: tuple) -> None:
    """Ícone geométrico de martelo (cabeça + cabo), referência discreta ao mascote."""
    u = size / 10
    d.rounded_rectangle((x, y, x + 10 * u, y + 4 * u), radius=int(u), fill=color)  # cabeça
    d.rectangle((x + 4.2 * u, y + 4 * u, x + 5.8 * u, y + 10 * u), fill=color)  # cabo


def _brand(d: ImageDraw.ImageDraw, w: int, y: int, accent: tuple) -> None:
    label = _spaced(settings.brand_name)
    f = _font(30, "bold")
    tw = d.textlength(label, font=f)
    icon = 34
    total = icon + 20 + tw
    x0 = (w - total) / 2
    _hammer(d, int(x0), int(y - icon / 2), icon, accent)
    d.text((x0 + icon + 20, y), label, font=f, fill=TEXT, anchor="lm")


def _product_card(canvas: Image.Image, photo_jpeg: bytes, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    # sombra suave
    shadow = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 10, y0 + 24, x1 - 10, y1 + 24), radius=56, fill=120)
    shadow = shadow.filter(ImageFilter.GaussianBlur(36))
    canvas.paste(Image.new("RGB", canvas.size, (0, 0, 0)), (0, 0), shadow)
    # cartão
    card = Image.new("RGB", (x1 - x0, y1 - y0), CARD)
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *card.size), radius=56, fill=255)
    photo = Image.open(io.BytesIO(photo_jpeg)).convert("RGB")
    pad = 70
    maxw, maxh = card.width - 2 * pad, card.height - 2 * pad - 70  # sobra no topo p/ o selo (-% / EM ALTA) não cobrir o produto
    scale = min(maxw / photo.width, maxh / photo.height)
    if scale > 1:  # foto pequena: amplia (até 2,2x) com um pouco de nitidez
        scale = min(scale, 2.2)
        photo = photo.resize((round(photo.width * scale), round(photo.height * scale)), Image.LANCZOS)
        photo = photo.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))
    else:
        photo.thumbnail((maxw, maxh))
    # fundo branco da foto vira o cinza claro do cartão (sem "caixa" branca)
    if photo.getpixel((0, 0))[0] > 240:
        bg = Image.new("RGB", photo.size, CARD)
        m = photo.convert("L").point(lambda v: 0 if v > 246 else 255).filter(ImageFilter.GaussianBlur(1))
        bg.paste(photo, (0, 0), m)
        photo = bg
    card.paste(photo, ((card.width - photo.width) // 2, (card.height - photo.height) // 2 + 35))
    canvas.paste(card, (x0, y0), mask)


def render_art(o, photo_jpeg: bytes, fmt: str = "story") -> bytes:
    """fmt: 'story' (1080x1920) ou 'feed' (1080x1350)."""
    story = fmt == "story"
    w, h = (1080, 1920) if story else (1080, 1350)
    accent = _hex(settings.accent_color)
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # marca + linha fina de destaque
    top = 120 if story else 80
    _brand(d, w, top, accent)
    d.line((w / 2 - 40, top + 46, w / 2 + 40, top + 46), fill=accent, width=3)

    # produto
    card_top, card_bottom = (230, 1060) if story else (160, 690)
    _product_card(img, photo_jpeg, (100, card_top, w - 100, card_bottom))
    d = ImageDraw.Draw(img)

    # selo de desconto (pílula discreta no canto do cartão)
    pct = round((1 - o.price / o.old_price) * 100) if o.price and o.old_price and o.old_price > o.price else 0
    if pct:
        label = f"-{pct}%"
        f = _font(40, "bold")
        tw = d.textlength(label, font=f)
        px, py = 140, card_top + 40
        d.rounded_rectangle((px, py, px + tw + 48, py + 70), radius=35, fill=accent)
        d.text((px + 24 + tw / 2, py + 35), label, font=f, fill=(255, 255, 255), anchor="mm")

    elif getattr(o, "source", "") == "pelando":  # sem preço antigo: selo "EM ALTA" (oferta bem votada pela comunidade)
        label = "EM ALTA"
        f = _font(36, "bold")
        tw = d.textlength(label, font=f)
        px, py = 140, card_top + 40
        d.rounded_rectangle((px, py, px + tw + 48, py + 64), radius=32, fill=accent)
        d.text((px + 24 + tw / 2, py + 32), label, font=f, fill=(255, 255, 255), anchor="mm")

    # título (fino)
    title = (getattr(o, "post_title", None) or o.title).strip()
    lines = textwrap.wrap(title, width=30)[:3 if story else 2]
    y = card_bottom + (110 if story else 75)
    for line in lines:
        d.text((w // 2, y), line, font=_font(44 if story else 38, "regular"), fill=TEXT, anchor="mm")
        y += 60 if story else 52

    # preço
    y += 40 if story else 26
    if o.old_price and pct:
        old = brl(o.old_price)
        f = _font(36, "light")
        d.text((w // 2, y), old, font=f, fill=MUTED, anchor="mm")
        b = d.textbbox((w // 2, y), old, font=f, anchor="mm")
        d.line((b[0] - 4, (b[1] + b[3]) // 2, b[2] + 4, (b[1] + b[3]) // 2), fill=MUTED, width=3)
        y += 80 if story else 68
    d.text((w // 2, y), brl(o.price), font=_font(104 if story else 86, "bold"), fill=TEXT, anchor="mm")

    # chamada (contorno laranja, minimalista)
    btn_w, btn_h = 640, 104 if story else 92
    bx, by = (w - btn_w) // 2, h - (290 if story else 180)
    d.rounded_rectangle((bx, by, bx + btn_w, by + btn_h), radius=btn_h // 2, outline=accent, width=4)
    d.text((w // 2, by + btn_h // 2), _spaced(settings.social_cta).replace("   ", "  "),
           font=_font(28 if story else 26, "bold"), fill=TEXT, anchor="mm")
    d.text((w // 2, by + btn_h + 50), "Preço e disponibilidade podem variar", font=_font(24, "light"),
           fill=MUTED, anchor="mm")

    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()
