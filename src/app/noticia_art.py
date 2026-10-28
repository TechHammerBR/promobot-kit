"""Arte das NOVIDADES de tecnologia (14/10/2026): visual de canal de notícias feito só com Pillow (leve para o Wyse).

Capa: fundo escuro com grade de pontos + brilho laranja, ícone grande da editoria, manchete grande (números/siglas em laranja),
fonte e data. Cartões numerados com barra de progresso. Último slide antes da chamada: FONTES (outros sites do mesmo assunto).
Se PEXELS_API_KEY existir, a capa usa uma foto livre da editoria (licença Pexels: uso comercial, sem crédito) com camada escura.
"""
import io
import re

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.config import DATA_DIR, settings
from app.social_art import BG, MUTED, TEXT, _brand, _font, _hex

W, H = 1080, 1350
LAT = 80  # margem lateral
BUSCA_FOTO = {"ia": "artificial intelligence technology", "hardware": "computer hardware motherboard", "seguranca": "cyber security lock",
              "celular": "smartphone technology", "software": "software code screen", "games": "gaming setup controller",
              "outros": "technology abstract"}
ROTULO = {"ia": "INTELIGÊNCIA ARTIFICIAL", "hardware": "HARDWARE", "seguranca": "SEGURANÇA", "celular": "CELULARES",
          "software": "SOFTWARE", "games": "GAMES", "outros": "TECNOLOGIA"}


def _jpeg(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _fundo(accent: tuple, canto: str = "dir") -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    brilho = Image.new("RGB", (W // 4, H // 4), BG)
    d = ImageDraw.Draw(brilho)
    cx = (W // 4) * (0.85 if canto == "dir" else 0.15)
    d.ellipse((cx - 85, -70, cx + 85, 100), fill=tuple(int(c * 0.45) for c in accent))
    brilho = brilho.filter(ImageFilter.GaussianBlur(28)).resize((W, H))
    im = Image.blend(im, brilho, 0.75)
    d = ImageDraw.Draw(im)
    for y in range(60, H, 54):  # grade de pontos discreta
        for x in range(60, W, 54):
            d.rectangle((x, y, x + 1, y + 1), fill=(52, 52, 58))
    return im


def _icone(d: ImageDraw.ImageDraw, ed: str, cx: int, cy: int, s: int, cor: tuple, esp: int = 8) -> None:
    """Ícone geométrico (contorno) da editoria, caixa de lado s centrada em (cx, cy)."""
    x0, y0, x1, y1 = cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2
    if ed == "ia":  # rede neural: 3 camadas de nós ligados
        cols = [[0.2, 0.5, 0.8], [0.0, 0.33, 0.66, 1.0], [0.25, 0.75]]
        pos = [[(x0 + (i * 0.5) * s, y0 + v * s) for v in col] for i, col in enumerate(cols)]
        for a in pos[0]:
            for b in pos[1]:
                d.line((*a, *b), fill=cor, width=3)
        for a in pos[1]:
            for b in pos[2]:
                d.line((*a, *b), fill=cor, width=3)
        for col in pos:
            for (x, y) in col:
                d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=BG, outline=cor, width=esp)
    elif ed == "hardware":  # chip com pinos
        m = s // 6
        d.rounded_rectangle((x0 + m, y0 + m, x1 - m, y1 - m), radius=24, outline=cor, width=esp)
        d.rounded_rectangle((cx - s // 6, cy - s // 6, cx + s // 6, cy + s // 6), radius=10, outline=cor, width=esp)
        for k in range(1, 5):
            t = x0 + m + k * (s - 2 * m) // 5
            d.line((t, y0, t, y0 + m), fill=cor, width=esp)
            d.line((t, y1 - m, t, y1), fill=cor, width=esp)
            u = y0 + m + k * (s - 2 * m) // 5
            d.line((x0, u, x0 + m, u), fill=cor, width=esp)
            d.line((x1 - m, u, x1, u), fill=cor, width=esp)
    elif ed == "seguranca":  # escudo com fechadura
        pts = [(cx, y0), (x1 - 10, y0 + s * 0.18), (x1 - 40, y0 + s * 0.68), (cx, y1), (x0 + 40, y0 + s * 0.68), (x0 + 10, y0 + s * 0.18)]
        d.polygon(pts, outline=cor, width=esp)
        d.ellipse((cx - 36, cy - 62, cx + 36, cy + 10), outline=cor, width=esp)
        d.rounded_rectangle((cx - 50, cy - 10, cx + 50, cy + 70), radius=12, outline=cor, width=esp)
    elif ed == "celular":
        d.rounded_rectangle((cx - s * 0.28, y0, cx + s * 0.28, y1), radius=44, outline=cor, width=esp)
        d.rounded_rectangle((cx - 40, y0 + 22, cx + 40, y0 + 40), radius=9, fill=cor)
        d.ellipse((cx - 18, y1 - 70, cx + 18, y1 - 34), outline=cor, width=6)
    elif ed == "software":  # janela com 3 pontos e linhas
        d.rounded_rectangle((x0, y0 + s * 0.12, x1, y1 - s * 0.12), radius=28, outline=cor, width=esp)
        d.line((x0, y0 + s * 0.3, x1, y0 + s * 0.3), fill=cor, width=esp)
        for k in range(3):
            d.ellipse((x0 + 34 + k * 46, y0 + s * 0.17, x0 + 58 + k * 46, y0 + s * 0.17 + 24), fill=cor)
        for k in range(3):
            d.line((x0 + 50, y0 + s * (0.46 + k * 0.12), x1 - 50 - k * 60, y0 + s * (0.46 + k * 0.12)), fill=cor, width=esp - 2)
    elif ed == "games":  # controle
        d.rounded_rectangle((x0, cy - s * 0.24, x1, cy + s * 0.24), radius=int(s * 0.22), outline=cor, width=esp)
        d.line((x0 + s * 0.22, cy - 36, x0 + s * 0.22, cy + 36), fill=cor, width=esp)
        d.line((x0 + s * 0.22 - 36, cy, x0 + s * 0.22 + 36, cy), fill=cor, width=esp)
        for (dx, dy) in ((0.72, -0.07), (0.82, 0.05)):
            d.ellipse((x0 + s * dx - 20, cy + s * dy - 20, x0 + s * dx + 20, cy + s * dy + 20), outline=cor, width=esp - 2)
    else:  # raio
        d.polygon([(cx + 20, y0), (x0 + s * 0.28, cy + 10), (cx - 6, cy + 10), (cx - 20, y1), (x1 - s * 0.28, cy - 20), (cx + 6, cy - 20)],
                  outline=cor, width=esp)


def _linhas(d: ImageDraw.ImageDraw, texto: str, fonte, largura: int) -> list[str]:
    """Quebra por largura em pixels (não por número de letras)."""
    out, atual = [], ""
    for p in texto.split():
        t = f"{atual} {p}".strip()
        if d.textlength(t, font=fonte) <= largura or not atual:
            atual = t
        else:
            out.append(atual)
            atual = p
    if atual:
        out.append(atual)
    return out


_DESTAQUE = re.compile(r"[0-9]|^[A-Z0-9]{2,}$|^(RTX|GTX|PS5|PS4|IA|GPU|CPU|SSD|AMD|Intel|Nvidia|NVIDIA|Windows|Android|iPhone|Xbox)")


def _titulo_colorido(d, texto: str, x: int, y: int, fonte, cor: tuple, destaque: tuple, largura: int, passo: int) -> int:
    """Escreve a manchete linha a linha; palavras com número/sigla/marca ficam na cor de destaque. Retorna o y final."""
    for ln in _linhas(d, texto, fonte, largura):
        cx = x
        for p in ln.split():
            palavra = re.sub(r"[^A-Za-z0-9]", "", p)
            d.text((cx, y), p, font=fonte, fill=destaque if palavra and _DESTAQUE.search(palavra) else cor)
            cx += d.textlength(p + " ", font=fonte)
        y += passo
    return y


def _foto_editoria(ed: str) -> Image.Image | None:
    chave = getattr(settings, "pexels_api_key", "")
    if not chave:
        return None
    pasta = DATA_DIR / "fotos_editoria"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"{ed}.jpg"
    try:
        if not arq.exists() or arq.stat().st_size < 5000:
            r = httpx.get("https://api.pexels.com/v1/search", headers={"Authorization": chave}, timeout=20,
                          params={"query": BUSCA_FOTO.get(ed, BUSCA_FOTO["outros"]), "orientation": "portrait", "per_page": 5})
            fotos = r.json().get("photos") or []
            if not fotos:
                return None
            arq.write_bytes(httpx.get(fotos[0]["src"]["large2x"], timeout=30).content)
        return Image.open(arq).convert("RGB")
    except Exception:  # noqa: BLE001  (sem foto = capa de ícone, nada quebra)
        return None


def capa(titulo: str, editoria: str, fonte: str, data: str, foto_bytes: bytes | None = None, credito: str = "") -> bytes:
    accent = _hex(settings.accent_color)
    if foto_bytes:
        return _capa_com_foto(titulo, editoria, fonte, data, foto_bytes, credito)
    foto = _foto_editoria(editoria)
    if foto:
        im = ImageOps.fit(foto, (W, H))
        sombra = Image.new("L", (1, H))
        for y in range(H):  # escurece de baixo para cima (texto legível)
            sombra.putpixel((0, y), int(235 * min(1, max(0.25, (y - 150) / 900))))
        im = Image.composite(Image.new("RGB", (W, H), BG), im, sombra.resize((W, H)))
    else:
        im = _fundo(accent)
    d = ImageDraw.Draw(im)
    _brand(d, W, 90, accent)
    if not foto:
        _icone(d, editoria, W // 2, 430, 400, accent)
    chip = ROTULO.get(editoria, "TECNOLOGIA")
    f = _font(30)
    tw = d.textlength(chip, font=f)
    d.rounded_rectangle((LAT, 735, LAT + tw + 56, 795), radius=30, fill=accent)
    d.text((LAT + 28, 765), chip, font=f, fill=(255, 255, 255), anchor="lm")
    d.text((LAT + tw + 90, 765), f"NOVIDADE · {data}", font=_font(28, "regular"), fill=MUTED, anchor="lm")
    tam = 74 if len(titulo) <= 70 else 62 if len(titulo) <= 110 else 54
    _titulo_colorido(d, titulo, LAT, 835, _font(tam), TEXT, accent, W - 2 * LAT, int(tam * 1.22))
    d.text((LAT, H - 80), f"Fonte: {fonte}", font=_font(28, "regular"), fill=MUTED, anchor="lm")
    d.text((W - LAT, H - 80), "ARRASTE  ›››", font=_font(30), fill=accent, anchor="rm")
    return _jpeg(im)


def cartao(n: int, total: int, titulo: str, texto: str, foto_bytes: bytes | None = None) -> bytes:
    """Cartão de texto: só a informação, com palavras-chave em laranja. `titulo` = de onde veio (ex.: "via Canaltech")."""
    accent = _hex(settings.accent_color)
    im = _fundo(accent, "esq")
    if foto_bytes:  # imagem da matéria desfocada e escura no fundo (23/10: dono pediu post mais visual)
        try:
            import io
            from PIL import ImageEnhance, ImageFilter, ImageOps
            fb = ImageOps.fit(Image.open(io.BytesIO(foto_bytes)).convert("RGB"), im.size)
            fb = ImageEnhance.Brightness(fb.filter(ImageFilter.GaussianBlur(14))).enhance(0.22)
            im = Image.blend(fb, im.convert("RGB"), 0.12)
        except Exception:  # noqa: BLE001
            pass
    d = ImageDraw.Draw(im)
    _brand(d, W, 90, accent)
    corpo = _font(58, "regular")
    linhas = _linhas(d, texto, corpo, W - 2 * LAT - 40)
    altura = len(linhas) * 84
    y = max(300, (H - altura) // 2 - 20)  # bloco centralizado na vertical
    d.rounded_rectangle((LAT, y - 70, LAT + 90, y - 62), radius=4, fill=accent)
    d.text((LAT, y - 40), titulo.upper(), font=_font(30), fill=accent, anchor="lm")
    _titulo_colorido(d, texto, LAT, y + 20, corpo, TEXT, accent, W - 2 * LAT - 40, 84)
    for k in range(total):  # barra de progresso
        cor = accent if k < n else (60, 60, 66)
        d.rounded_rectangle((LAT + k * 70, H - 100, LAT + k * 70 + 56, H - 92), radius=4, fill=cor)
    d.text((W - LAT, H - 96), "ARRASTE  ›››", font=_font(26), fill=MUTED, anchor="rm")
    return _jpeg(im)


def fontes(itens: list[tuple[str, str]], data: str) -> bytes:
    """itens = [(site, manchete)]. Último slide de conteúdo: créditos e outros sites que cobriram o assunto."""
    accent = _hex(settings.accent_color)
    im = _fundo(accent, "esq")
    d = ImageDraw.Draw(im)
    _brand(d, W, 90, accent)
    d.text((LAT, 270), "FONTES", font=_font(86), fill=TEXT)
    d.text((LAT, 370), f"Informações publicadas em {data}", font=_font(30, "regular"), fill=MUTED)
    y = 470
    for site, manchete in itens[:4]:
        linhas = _linhas(d, manchete, _font(36, "regular"), W - 2 * LAT - 40)[:3]
        d.rounded_rectangle((LAT, y, LAT + 10, y + 64 + 50 * len(linhas)), radius=5, fill=accent)
        d.text((LAT + 36, y), site, font=_font(44), fill=accent)
        for k, ln in enumerate(linhas):
            d.text((LAT + 36, y + 66 + 50 * k), ln, font=_font(36, "regular"), fill=TEXT)
        y += 64 + 50 * len(linhas) + 50
    d.text((LAT, H - 96), "Os links estão na legenda do post.", font=_font(30, "regular"), fill=MUTED)
    return _jpeg(im)


def _capa_com_foto(titulo: str, editoria: str, fonte: str, data: str, foto_bytes: bytes, credito: str) -> bytes:
    """Foto do assunto em faixa larga no topo (some suave no fundo escuro), chip + manchete embaixo, crédito da imagem."""
    accent = _hex(settings.accent_color)
    im = _fundo(accent)
    foto = ImageOps.fit(Image.open(io.BytesIO(foto_bytes)).convert("RGB"), (W, 640), centering=(0.5, 0.4))
    mascara = Image.new("L", (1, 640), 255)
    for y in range(640):  # esmaece o pé da foto no fundo escuro
        mascara.putpixel((0, y), 255 if y < 470 else int(255 * (640 - y) / 170))
    im.paste(foto, (0, 150), mascara.resize((W, 640)))
    d = ImageDraw.Draw(im)
    _brand(d, W, 90, accent)
    chip = ROTULO.get(editoria, "TECNOLOGIA")
    f = _font(30)
    tw = d.textlength(chip, font=f)
    d.rounded_rectangle((LAT, 735, LAT + tw + 56, 795), radius=30, fill=accent)
    d.text((LAT + 28, 765), chip, font=f, fill=(255, 255, 255), anchor="lm")
    d.text((LAT + tw + 90, 765), f"NOVIDADE · {data}", font=_font(28, "regular"), fill=MUTED, anchor="lm")
    tam = 74 if len(titulo) <= 70 else 62 if len(titulo) <= 110 else 54
    _titulo_colorido(d, titulo, LAT, 835, _font(tam), TEXT, accent, W - 2 * LAT, int(tam * 1.22))
    d.text((LAT, H - 80), f"Imagem: {credito or fonte}  ·  Fonte: {fonte}", font=_font(26, "regular"), fill=MUTED, anchor="lm")
    d.text((W - LAT, H - 80), "ARRASTE  ›››", font=_font(30), fill=accent, anchor="rm")
    return _jpeg(im)
