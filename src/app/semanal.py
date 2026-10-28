"""Carrosséis semanais com DADOS PRÓPRIOS do robô (14/10/2026, pedido do dono; sem IA, cabem no Wyse):

- TOP 5 OFERTAS DA SEMANA (sábado): as 5 maiores quedas de preço postadas no grupo de tecnologia nos últimos 7 dias.
- RADAR DE PREÇOS (sexta): o melhor achado da semana em cada categoria de hardware (SSD, placa de vídeo, memória...), com o
  histórico de preço do robô quando houver ("menor preço em N dias").

Slides no padrão das artes de oferta (social_art.render_art, 1080x1350) com o número/categoria por cima; capa e chamada final
no padrão dos educativos. Publica no Instagram, Facebook e Threads (content.publish_carousel). Teste sem publicar:
`./venv/bin/python -m app.semanal previa top5|radar` -> imagens em /srv/cache/semanal.
"""
import io
import re
import sys
from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.db import Offer, SessionLocal, now
from app.log import log
from app.media import product_jpeg
from app.social_art import _font, render_art
from app.templates import brl, chamada_grupos
from app.titles import variacoes

PREVIA = Path("/srv/cache/semanal")
CATEGORIAS = [
    ("SSD", r"\bssd\b|\bnvme\b"),
    ("Placa de vídeo", r"placa de v[ií]deo|\brtx ?\d|\bgtx ?\d|\bradeon\b|\brx ?\d{4}"),
    ("Memória RAM", r"\bmem[óo]ria\b"),
    ("Processador", r"\bprocessador\b|\bryzen [3579]\b|\bcore i[3579]\b|\bcore ultra\b"),
    ("Placa-mãe", r"placa[- ]m[ãa]e|motherboard"),
    ("Monitor", r"\bmonitor\b"),
    ("Fonte", r"\bfonte\b|\bpsu\b"),
    ("Periféricos", r"\bmouse\b|\bteclado\b|\bheadset\b"),
]
NAO_HARDWARE = re.compile(r"suporte|cabo|adaptador|case para|capa|caixa|enclosure|dock|hub|pelicula|película|limpador|"
                          r"radiador|dissipador|armadura|cooler|fone|kit de", re.I)


def _tipo(titulo: str) -> str | None:
    """Categoria pelo COMEÇO do título (o que o produto É), não por palavras soltas da ficha técnica."""
    cabeca = " ".join(titulo.split()[:5])
    if NAO_HARDWARE.search(cabeca):
        return None
    return next((nome for nome, rx in CATEGORIAS if re.search(rx, cabeca, re.I)), None)


def _ali(o: Offer) -> bool:
    return o.source == "aliexpress" or "aliexpress." in (o.url or "")


def _confiavel(o: Offer) -> bool:
    from app.titles import marca
    return not _ali(o) or marca(o.title) is not None


def _preco(o: Offer) -> str:
    """AliExpress com várias capacidades: o preço é o da opção mais barata."""
    v = variacoes(o.title) if "aliexpress." in (o.url or "") else []
    return f"a partir de {brl(o.price)} ({v[0]})" if v else brl(o.price)


def _pct(o: Offer) -> int:
    return round((1 - o.price / o.old_price) * 100) if o.price and o.old_price and o.old_price > o.price else 0


def _semana(min_preco: float = 50) -> list[Offer]:
    """Ofertas de tecnologia postadas nos últimos 7 dias, com desconto real, a melhor oferta por produto."""
    with SessionLocal() as s:
        rows = s.scalars(select(Offer).where(Offer.status == "posted", Offer.canal == "tech",
                                             Offer.posted_at >= now() - timedelta(days=7))).all()
        for o in rows:
            s.expunge(o)
    melhor: dict[str, Offer] = {}
    for o in rows:
        if o.price < min_preco or _pct(o) < 15:
            continue
        k = o.product_key or o.title[:40].lower()
        if k not in melhor or _pct(o) > _pct(melhor[k]):
            melhor[k] = o
    return sorted(melhor.values(), key=lambda o: (-_pct(o), -(o.score or 0)))


def _selo(arte: bytes, texto: str) -> bytes:
    """Etiqueta no alto da arte da oferta (ex.: "#1" ou "SSD")."""
    im = Image.open(io.BytesIO(arte)).convert("RGB")
    d = ImageDraw.Draw(im)
    f = _font(40)
    tw = d.textlength(texto, font=f)
    x, y = im.width - 140 - tw - 48, 200
    d.rounded_rectangle((x, y, x + tw + 48, y + 70), radius=35, fill=(245, 245, 247))
    d.text((x + 24 + tw / 2, y + 35), texto, font=f, fill=(11, 11, 13), anchor="mm")
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92)
    return out.getvalue()


def _slides_ofertas(itens: list[tuple[Offer, str]]) -> list[tuple[Offer, bytes]]:
    out = []
    for o, selo in itens:
        foto = product_jpeg(o.image_url)
        if not foto:
            continue
        out.append((o, _selo(render_art(o, foto, "feed"), selo)))
    return out


def _capa(linha1: str, linha2: str, kicker: str) -> bytes:
    from app.content import _text_slide
    return _text_slide(f"{linha1} {linha2}", kicker=kicker, big=True, footer="arraste →")


def _final() -> bytes:
    from app.content import _text_slide
    return _text_slide("Ofertas assim todo dia, de graça", "Entre nos nossos grupos de tecnologia e de casa: o link está na bio.",
                       kicker="Não perca a próxima", footer="@techhammer.br")


def _publicar(nome: str, slides: list[bytes], legenda_ig: str, legenda_fb: str, comentario: str) -> list[str]:
    from app.content import publish_carousel
    done = publish_carousel(slides, legenda_ig, first_comment=comentario, fb_caption=legenda_fb)
    log.info("semanal_posted", tipo=nome, slides=len(slides), nets=done)
    return done


# ------------------------------------------------------------------ TOP 5
def montar_top5() -> tuple[list[bytes], str, str, str] | None:
    escolhidas, marcas = [], set()
    from app.titles import marca
    for o in sorted(_semana(), key=lambda o: -(o.score or 0)):
        if _ali(o):  # o "preço antigo" do AliExpress é inflado (-70%% em tudo): não entra no ranking de desconto
            continue
        m = marca(o.title) or o.title.split()[0].lower()
        if m in marcas:  # variedade: uma por marca
            continue
        marcas.add(m)
        escolhidas.append(o)
        if len(escolhidas) == 7:  # sobra para foto que não abrir
            break
    com_foto = [(o, f) for o in escolhidas if (f := product_jpeg(o.image_url))][:5]
    if len(com_foto) < 3:
        return None
    feitas = [(o, _selo(render_art(o, f, "feed"), f"#{i + 1}")) for i, (o, f) in enumerate(com_foto)]
    linhas = [f"#{i + 1} {o.post_title or o.title[:60]} — {_preco(o)} (-{_pct(o)}%)" for i, (o, _) in enumerate(feitas)]
    base = ["🏆 TOP 5 OFERTAS DA SEMANA", "As ofertas que mais se destacaram no nosso grupo nos últimos 7 dias:", "", *linhas, "",
            "⚠️ Preços da semana: podem ter mudado. Confira no link antes de comprar."]
    links = [f"#{i + 1}: {o.affiliate_url or o.url}" for i, (o, _) in enumerate(feitas)]
    ig = "\n".join(base + ["", chamada_grupos(False), "", "#ofertas #promoção #pcgamer #hardware #techhammer"])
    fb = "\n".join(base + ["", "🔗 Links:", *links, "", chamada_grupos(True)])
    comentario = "🔗 Os links de cada oferta estão no nosso grupo do WhatsApp e no Telegram — link na bio!"
    slides = [_capa("TOP 5", "OFERTAS DA SEMANA", "Os destaques do nosso grupo")] + [a for _, a in feitas] + [_final()]
    return slides, ig, fb, comentario


def post_top5() -> None:
    from app.social import enabled
    if not enabled():
        return
    m = montar_top5()
    if not m:
        log.info("semanal_skip", tipo="top5", motivo="poucas ofertas com desconto real")
        return
    _publicar("top5", *m)


# ------------------------------------------------------------------ RADAR
def montar_radar() -> tuple[list[bytes], str, str, str] | None:
    from app import pricehist
    semana, itens = _semana(min_preco=40), []
    for nome, _rx in CATEGORIAS:
        cands = [o for o in semana if _tipo(o.title) == nome and _confiavel(o)]
        cands.sort(key=lambda o: (_ali(o), -_pct(o)))  # loja nacional primeiro; AliExpress só se a categoria não tiver outra
        if cands:
            itens.append((cands[0], nome))
    feitas = _slides_ofertas(itens)
    if len(feitas) < 3:
        return None
    linhas = []
    with SessionLocal() as s:
        for o, _ in feitas:
            situacao, dias = pricehist.analisar(s, o.product_key, o.price)
            extra = f" • menor preço em {dias} dias" if situacao == "queda" and dias >= 7 else ""
            cat = next(n for oo, n in itens if oo is o)
            linhas.append(f"• {cat}: {o.post_title or o.title[:55]} — {_preco(o)} (-{_pct(o)}%){extra}")
    base = ["📡 RADAR DE PREÇOS DA SEMANA", "O melhor achado de cada categoria pra quem vai montar ou fazer upgrade no PC:", "", *linhas, "",
            "⚠️ Preços da semana: podem ter mudado. Confira no link antes de comprar."]
    links = [f"• {next(n for oo, n in itens if oo is o)}: {o.affiliate_url or o.url}" for o, _ in feitas]
    ig = "\n".join(base + ["", "🔧 Vai montar ou fazer upgrade? A TechHammer monta e instala pra você — chama no direct.",
                           chamada_grupos(False), "", "#hardware #pcgamer #upgrade #montagemdepc #techhammer"])
    fb = "\n".join(base + ["", "🔗 Links:", *links, "", chamada_grupos(True)])
    comentario = "🔗 Os links de cada peça estão no nosso grupo do WhatsApp e no Telegram — link na bio!"
    slides = [_capa("RADAR", "DE PREÇOS", "O melhor de cada categoria")] + [a for _, a in feitas] + [_final()]
    return slides, ig, fb, comentario


def post_radar() -> None:
    from app.social import enabled
    if not enabled():
        return
    m = montar_radar()
    if not m:
        log.info("semanal_skip", tipo="radar", motivo="poucas categorias com oferta")
        return
    _publicar("radar", *m)


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "previa":
    m = montar_top5() if sys.argv[2] == "top5" else montar_radar()
    if not m:
        print("sem ofertas suficientes")
        raise SystemExit(0)
    PREVIA.mkdir(parents=True, exist_ok=True)
    slides, ig, fb, com = m
    grade = Image.new("RGB", (4 * 270, ((len(slides) + 3) // 4) * 338), "white")
    for i, sl in enumerate(slides):
        grade.paste(Image.open(io.BytesIO(sl)).resize((270, 338)), ((i % 4) * 270, (i // 4) * 338))
    grade.save(PREVIA / f"{sys.argv[2]}.jpg", quality=80)
    print(ig)
    print("----- facebook -----")
    print(fb)
