"""Foto do post: baixa, normaliza (JPEG fundo branco) e VALIDA que é foto do produto.

Regra do dono: nenhum post sai sem foto, e a foto tem que ser do produto.
- PNG com transparência aparece PRETO no WhatsApp -> tudo vira JPEG sobre branco.
- Validação em 2 etapas:
  1) rápida: bordas claras e uniformes = foto de catálogo (produto em fundo liso) -> aprovada;
  2) senão, IA de visão local (Ollama, qwen2.5vl:3b) decide se é o produto ou banner/pessoa/vídeo/cena.
"""
import base64
import io
import json
import re

import httpx
from PIL import ImageFilter, Image, ImageStat

from app import gpu
from app.config import settings
from app.log import log


def photo_url(url: str | None) -> str | None:
    """Fotos do ML: miniatura do card (D_Q_NP_2X_) -> resolução cheia (D_NQ_NP_); .webp -> .jpg."""
    if url and "mlstatic.com" in url:
        url = url.replace("/D_Q_NP_2X_", "/D_NQ_NP_").replace("/D_Q_NP_", "/D_NQ_NP_")
        # sufixo de miniatura (-R, -AB, -V..., às vezes seguido do nome do produto: -AB-suporte-gamer.webp) -> original
        url = re.sub(r"-[A-Z]{1,2}(-[a-z0-9-]+)?\.(webp|jpg|png)$", r"-O.\g<2>", url)
        if url.endswith(".webp"):
            url = url[:-5] + ".jpg"
    return url


def product_jpeg(url: str | None) -> bytes | None:
    if not url or "frontend-assets" in url:  # nunca a logo do site
        return None
    try:
        r = httpx.get(photo_url(url), headers={"User-Agent": "Mozilla/5.0"}, timeout=30, follow_redirects=True)
        if r.status_code != 200 or len(r.content) < 3000:
            return None
        img = Image.open(io.BytesIO(r.content))
    except Exception as e:
        log.warning("photo_download_failed", url=url, error=str(e)[:200])
        return None
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    if max(ImageStat.Stat(img.convert("L")).mean) < 12:  # praticamente toda preta: imagem quebrada
        return None
    img.thumbnail((1280, 1280))
    if max(img.size) < FOTO_PEQUENA:  # miniatura de agregador (Pelando manda 300 px): amplia com suavização p/ não chegar serrilhada
        f = 900 / max(img.size)
        img = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


FOTO_PEQUENA = 600  # px no lado maior; abaixo disso a foto chega ruim no grupo


def foto_pequena(url: str | None) -> bool:
    """A foto ORIGINAL do card é miniatura? (o Pelando marca o tamanho no endereço: /0x300/)"""
    return bool(url and re.search(r"media[.]pelando[.]com[.]br/[^/]+/[0-9]*x[1-5]?[0-9]{2}/", url))


def _clean_background(img: Image.Image, mean_min: float = 225, std_max: float = 18) -> bool:
    """Bordas (5% de cada lado) claras e pouco variadas = produto em fundo de catálogo."""
    g = img.convert("L")
    w, h = g.size
    bw, bh = max(2, w // 20), max(2, h // 20)
    strips = [g.crop((0, 0, w, bh)), g.crop((0, h - bh, w, h)), g.crop((0, 0, bw, h)), g.crop((w - bw, 0, w, h))]
    stats = [ImageStat.Stat(s) for s in strips]
    mean = sum(s.mean[0] for s in stats) / 4
    std = sum(s.stddev[0] for s in stats) / 4
    return mean >= mean_min and std <= std_max


VISION_PROMPT = """Classifique esta imagem de anúncio. Produto anunciado: "{title}".
Escolha o tipo que MELHOR descreve a imagem:
- "produto": o produto aparece sozinho, em destaque, ocupando boa parte da imagem (foto de catálogo)
- "pessoa": aparece uma pessoa (segurando, usando ou ao lado do produto)
- "banner": arte de propaganda com textos grandes/frases de marketing
- "cena": ambiente/decoração onde o produto é pequeno ou nem aparece
- "colagem": infográfico/montagem com o produto repetido várias vezes, vários aparelhos, setas, legendas ou tabelas
- "outro": logo, captura de vídeo, tela preta, outro produto
Conte também quantos objetos/aparelhos DIFERENTES aparecem (o produto + acessórios/consoles/celulares ao redor).
"frase_propaganda": true se houver TÍTULO/SLOGAN grande de marketing (ex.: "JOGUE SEM LIMITES", "OFERTA"), ou faixa de
ícones listando recursos. Nome da marca, logotipo, texto impresso no próprio produto/caixa e imagem na tela NÃO contam.
"selo_promocional": true se houver selo/estrela/etiqueta de venda na imagem com palavras como "BIG SALE", "HOT SALE", "SALE", "OFF",
"%", "FREE SHIPPING", "NEW", "GIFT" ou preço/desconto escrito (sinal de anúncio de baixa qualidade ou golpe).
Responda SÓ em JSON: {{"tipo": "produto|pessoa|banner|cena|colagem|outro", "objetos": 1, "frase_propaganda": true/false, "tem_pessoa": true/false, "selo_promocional": true/false}}"""


def validate_photo(jpeg: bytes, title: str, lenient: bool = False, game: bool = False) -> tuple[bool, str]:
    """lenient (AliExpress): aceita foto de produto sozinho com frase de propaganda (quase todas têm)."""
    img = Image.open(io.BytesIO(jpeg))
    if min(img.size) < 200:
        return False, "foto pequena demais"
    if not settings.ai_enabled:  # robô leve (sem IA de visão): medidas da própria imagem (app/photocheck.py)
        from app import photocheck
        ok, motivo, m = photocheck.avaliar(img, tolerante=lenient)
        if not ok and game and photocheck.avaliar_capa(img)[0]:
            return True, "regra: capa de jogo"
        detalhe = f" [borda {m['borda_suja']} letras {m['letras']} objetos {m['medios'] + 1}]" if not ok else ""
        return ok, f"regra: {motivo}{detalhe}"
    if _clean_background(img):
        return True, "fundo de catálogo"
    try:
        small = img.copy()
        small.thumbnail((512, 512))
        buf = io.BytesIO()
        small.save(buf, "JPEG", quality=80)
        r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=240, json={
            "model": settings.vision_model, "stream": False, "format": "json",
            "options": {"temperature": 0, "num_predict": 70, "num_gpu": settings.bot_ai_num_gpu},
            "messages": [{"role": "user", "content": VISION_PROMPT.format(title=title),
                          "images": [base64.b64encode(buf.getvalue()).decode()]}],
        })
        d = json.loads(r.json()["message"]["content"])
        tipo = str(d.get("tipo", "")).lower()
        try:
            objs = int(d.get("objetos", 1))
        except (TypeError, ValueError):
            objs = 1
        # texto na caixa/marca é normal; mas montagem com vários aparelhos (infográfico) não serve (dono, 03/10)
        ok = (tipo == "produto" and not d.get("tem_pessoa") and objs <= 3 and not d.get("selo_promocional")
              and (not d.get("frase_propaganda") or (lenient and objs <= 2)))
        return ok, (f"IA: {tipo} obj={objs}{' +pessoa' if d.get('tem_pessoa') else ''}{' +propaganda' if d.get('frase_propaganda') else ''}"
                    f"{' +selo' if d.get('selo_promocional') else ''}")
    except Exception as e:
        log.warning("vision_failed", error=str(e)[:200])
        return False, "validação indisponível"  # na dúvida, não publica
