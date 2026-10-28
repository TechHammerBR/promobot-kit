"""Cupons COM CÓDIGO (ex.: CARRINHOML, SITETODO0310), lidos do Pelando (página pública de cupons de cada loja).

Ideia do dono (03/10): posts de cupom ao longo do dia, como os grupos concorrentes. Posta quando aparecem
códigos novos (intervalo mínimo por loja, só no horário ativo). Expirados são ignorados.
13/10: além do Mercado Livre, SHOPEE (a API de afiliados da Shopee não tem cupom). Cupom da Shopee esgota em horas:
só entra o postado há minutos/horas, o intervalo entre posts é menor e o post leva o link de afiliado do dono.
"""
import re
from datetime import datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

from selectolax.parser import HTMLParser
from sqlalchemy import select

from app.collectors.base import Collector
from app.config import DATA_DIR, settings
from app.db import Coupon, SessionLocal, now
from app.log import log

TZ = ZoneInfo("America/Sao_Paulo")
MAX_IN_POST = 8
LOJAS = {
    "ml": {"nome": "Mercado Livre", "url": "https://www.pelando.com.br/cupons-de-descontos/mercado-livre", "prefixo": "code:",
           "marcador": DATA_DIR / "codes_last_post", "cor_titulo": (45, 50, 119), "cor_selo": (255, 230, 0), "cor_codigo": (52, 131, 250),
           "so_recente": False},
    "shopee": {"nome": "Shopee", "url": "https://www.pelando.com.br/cupons-de-descontos/shopee", "prefixo": "code:shopee:",
               "marcador": DATA_DIR / "codes_last_post_shopee", "cor_titulo": (238, 77, 45), "cor_selo": (255, 214, 201),
               "cor_codigo": (238, 77, 45), "so_recente": True},
}
PELANDO_URL = LOJAS["ml"]["url"]
MARKER = LOJAS["ml"]["marcador"]


class _Fetcher(Collector):  # reaproveita retry/headers/BlockedError do coletor base
    name = "pelando_cupons"

    def collect(self):
        return []


def parse(html: str, loja: str = "ml") -> list[dict]:
    cfg = LOJAS[loja]
    out = []
    for card in HTMLParser(html).css("article.card"):
        code = card.css_first("span.card__code-text")
        title = card.css_first("h2.card__title")
        if not code or not title:
            continue
        if any(s.text(strip=True) == "Expirada" for s in card.css("span")):
            continue
        t = re.sub(r"\s+", " ", title.text(strip=True))
        t = re.sub(rf"^Cupom {cfg['nome']}\s*(?:-|oferece)\s*", "", t, flags=re.I)
        t = re.sub(r"^\[.*?\]\s*", "", t)
        spans = [x.text(strip=True) for x in card.css("span")]
        age = next((x for x in spans if x.startswith("há")), "")
        recente = bool(re.match(r"há\s*\d+\s*(min|h|hs)\b", age))
        fresh = recente or (not cfg["so_recente"] and any("Verificado hoje" in x for x in spans))
        if not fresh:  # postado há mais de 1 dia e não reverificado hoje: provavelmente morto
            continue
        temp = next((int(x[:-1]) for x in spans if re.fullmatch(r"-?\d+°", x)), 0)
        desc = card.css_first("p.card__description")
        out.append({"temp": temp, "code": code.text(strip=True).upper(), "title": t[:1].upper() + t[1:140],
                    "scope": desc.text(strip=True)[:140] if desc else ""})
    return sorted({c["code"]: c for c in out}.values(), key=lambda c: -c["temp"])


def collect_codes(loja: str = "ml") -> int:
    cfg = LOJAS[loja]
    codes = parse(_Fetcher().get(cfg["url"]).text, loja)
    with SessionLocal() as s:
        for c in codes:
            key = f"{cfg['prefixo']}{c['code']}"
            row = s.get(Coupon, key) or Coupon(key=key, store=cfg["nome"], first_seen=now())
            row.code, row.title, row.scope, row.last_seen = c["code"], c["title"], c["scope"], now()
            row.max_discount = c["temp"]  # reaproveitado como "temperatura" (votos) p/ ordenar
            s.merge(row)
        s.commit()
    log.info("codes_collected", count=len(codes), loja=loja)
    return len(codes)


def active_codes(session, loja: str = "ml") -> list[Coupon]:
    return session.scalars(select(Coupon).where(Coupon.code.is_not(None), Coupon.store == LOJAS[loja]["nome"],
                                                Coupon.last_seen >= now() - timedelta(hours=2))
                           .order_by(Coupon.max_discount.desc())).all()


def _link_shopee() -> str | None:
    """Link de afiliado do dono para a central de cupons da Shopee (quem resgata por ele gera comissão na compra)."""
    try:
        from app.affiliate import shopee_link
        return shopee_link("https://shopee.com.br/m/cupom-de-desconto")
    except Exception as e:
        log.warning("shopee_coupon_link_failed", error=str(e)[:120])
        return None


def render(coupons: list[Coupon], channel: str, loja: str = "ml", link: str | None = None) -> str:
    b = (lambda s: f"<b>{s}</b>") if channel == "telegram" else (lambda s: f"*{s}*")
    nome = LOJAS[loja]["nome"].upper()
    lines = [f"🔥 {b('CUPONS ' + nome)}", "Use o código no carrinho, na hora de pagar:", ""]
    for c in coupons[:MAX_IN_POST]:
        lines.append(f"🎟️ {c.title} - {b(c.code)}")
    if link:
        lines += ["", f"🛒 Resgate aqui: {link}"]
    aviso = "⚠️ Sujeito a disponibilidade do lote de cupons: esgota rápido." if loja == "shopee" else "⚠️ Sujeito a disponibilidade do lote de cupons / produtos selecionados."
    lines += ["", aviso]
    from app.templates import invite_lines
    lines += invite_lines(channel=channel)
    if settings.post_hashtag:
        lines += ["", settings.post_hashtag]
    return "\n".join(lines)


def banner(coupons: list[Coupon], loja: str = "ml") -> bytes:
    """Cartões de cupom estilo app da loja (fundo cinza claro, cartão branco, código em destaque)."""
    from PIL import Image, ImageDraw, ImageFont
    cfg = LOJAS[loja]
    items = coupons[:4]
    h = 140 + 210 * len(items)
    img = Image.new("RGB", (1080, h), (237, 237, 237))
    d = ImageDraw.Draw(img)
    def f(size, bold=False):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""), size)
        except OSError:
            return ImageFont.load_default(size=size)
    d.text((60, 50), "CUPONS " + cfg["nome"].upper(), font=f(50, True), fill=cfg["cor_titulo"])
    for i, c in enumerate(items):
        y = 130 + i * 210
        d.rounded_rectangle((50, y, 1030, y + 185), radius=28, fill=(255, 255, 255))
        d.ellipse((85, y + 45, 175, y + 135), fill=cfg["cor_selo"])
        d.text((130, y + 90), "%", font=f(54), fill=cfg["cor_titulo"], anchor="mm")
        title = re.sub(r"^\[.*?\]\s*", "", c.title)
        title = title if len(title) <= 40 else title[:39] + "…"
        d.text((210, y + 40), title, font=f(36), fill=(51, 51, 51))
        d.text((210, y + 100), c.code, font=f(46, True), fill=cfg["cor_codigo"])
    out = BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def _post_loja(loja: str, gap_h: float) -> None:
    from app.publisher import send_post
    cfg = LOJAS[loja]
    try:
        collect_codes(loja)
    except Exception as e:
        log.warning("codes_collect_failed", error=str(e)[:200], loja=loja)
        return
    marcador = cfg["marcador"]
    last = datetime.fromisoformat(marcador.read_text().strip()) if marcador.exists() else datetime(2000, 1, 1, tzinfo=TZ)
    if datetime.now(TZ) - last < timedelta(hours=gap_h):
        return
    with SessionLocal() as s:
        codes = active_codes(s, loja)
        if not any(c.first_seen.astimezone(TZ) > last for c in codes):
            return  # nada novo desde o último post
        link = _link_shopee() if loja == "shopee" else None
        send_post({"telegram": render(codes, "telegram", loja, link), "whatsapp": render(codes, "whatsapp", loja, link)},
                  banner(codes, loja))
        if settings.lar_enabled and settings.lar_whatsapp_group_id:  # concorrentes postam cupom de loja também no grupo de casa (47% dos posts)
            try:
                from app.publisher import _send_whatsapp
                _send_whatsapp(render(codes, "whatsapp", loja, link), banner(codes, loja), to=settings.lar_whatsapp_group_id)
            except Exception as ex:  # noqa: BLE001
                log.warning("cupom_lar_falhou", error=str(ex)[:120])
        marcador.write_text(datetime.now(TZ).isoformat())
        log.info("codes_posted", count=min(len(codes), MAX_IN_POST), loja=loja)


def post_codes_if_new() -> None:
    from app.pipeline import in_active_hours
    from app.publisher import any_channel
    if not any_channel() or not in_active_hours():
        return
    _post_loja("ml", settings.code_post_gap_hours)
    if settings.shopee_coupons_enabled:
        _post_loja("shopee", settings.shopee_code_post_gap_hours)


# cupom que só vale para um tipo de produto/cliente que o robô não consegue conferir -> não é sugerido em oferta de tecnologia
_RESTRITO = re.compile(r"moda|roupa|cal[cç]ado|beleza|perfum|casa\b|m[oó]veis|decora|supermercado|aliment|bebida|pet\b|farm[aá]cia|"
                       r"sa[uú]de|livro|beb[eê]|brinquedo|esporte|automotiv|ferrament|primeira compra|1[ªa] compra|novos? (usu|client)|"
                       r"internacional|full\b|live\b|v[ií]deo|frete", re.I)
_MINIMO = re.compile(r"(?:em|acima de|a partir de|nas compras (?:acima )?de|m[ií]nimo de)\s*R\$\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?", re.I)


def _minimo(titulo: str) -> float | None:
    m = _MINIMO.search(titulo)
    return float(m.group(1).replace(".", "") + "." + (m.group(2) or "0")) if m else None


# 28/10/2026: cupom que o robo nao consegue conferir ou que e de outra categoria/marca nunca e sugerido
_EXTRA_RESTRITO = re.compile(r"carro|moto\b|constru|meli\+|exclusivo|somente (?:pra|para) quem|quem resgatou|saldo|mercado pago|loja ofici|"
                             r"lacta|nivea|olympikus|unilever|maquininha|bpc\b|chegando", re.I)
_CAT_TECH = re.compile(r"\btech\b|inform[aá]tic|eletr[oô]nic|celular|smartphone|\bgam(?:e|er|es)\b|\bpc\b|notebook|hardware", re.I)
_CAT_CASA = re.compile(r"\bcasa\b|m[oó]veis|decora|cozinha|eletrodom[eé]stic|\blar\b", re.I)
_GERAL = re.compile(r"todo (?:o )?site|quase todo|m[uú]ltiplas categorias", re.I)
_PCT = re.compile(r"(\d{1,2})\s?%\s?off", re.I)
_FIXO = re.compile(r"R\$\s?(\d{1,4})\s?(?:off\b|em R\$)", re.I)
_TETO = re.compile(r"(?:limitad[oa]\s*(?:a|à|de)|desconto\s*m[aá]x(?:imo)?|m[aá]x(?:imo)?)\s*R\$\s?(\d{1,4})", re.I)


def _economia(titulo: str, preco: float) -> float:
    """Economia MAXIMA estimada em R$ (percentual limitado ao teto, ou valor fixo). 0 se nao der para entender o texto."""
    teto = _TETO.search(titulo)
    cap = float(teto.group(1)) if teto else None
    pct = _PCT.search(titulo)
    if pct:
        v = preco * int(pct.group(1)) / 100
        return min(v, cap) if cap else v
    fixo = _FIXO.search(titulo)
    return float(fixo.group(1)) if fixo else 0.0


def sugerir(session, url: str, price: float | None, canal: str | None = None) -> dict | None:
    """Cupom ATIVO que pode servir para a oferta: {"code", "title", "nota"}; None se não houver um seguro de sugerir.

    Mercado Livre/Shopee: cupom geral cujo valor mínimo cabe no preço. É uma SUGESTÃO ("tente o cupom"): o robô não consegue confirmar se o anúncio
    participa, por isso o preço do post nunca é alterado. Entre os que servem: 1o o da categoria do canal (Tech/Casa), 2o o de maior economia estimada.
    KaBuM: só cupom publicado pela própria Awin (regra do programa) e só depois da aprovação.
    """
    from urllib.parse import urlparse
    host = urlparse(url or "").netloc.lower()
    if not price:
        return None
    if "kabum.com.br" in host:
        from app import awin
        c = next(iter(awin.cupons(17729)), None)
        return {"code": c["code"], "title": c["title"], "nota": "sujeito a disponibilidade do lote de cupons"} if c else None
    loja = "ml" if "mercadoli" in host else "shopee" if "shopee." in host else None
    if not loja:
        return None
    casa = canal == "lar"
    melhor, melhor_pontos, melhor_eco = None, -1.0, 0.0
    for c in active_codes(session, loja):
        texto = f"{c.title} {c.scope or ''}"
        minimo = _minimo(c.title)
        if minimo is None or price < minimo or _EXTRA_RESTRITO.search(texto):
            continue
        restrito = _RESTRITO.search(texto)
        if restrito and not (casa and _CAT_CASA.search(texto)):
            continue
        eco = _economia(c.title, price)
        pontos = eco
        if casa and _CAT_CASA.search(texto):
            pontos += 1000
        elif not casa and _CAT_TECH.search(texto):
            pontos += 1000
        elif _GERAL.search(texto):
            pontos += 20
        if pontos > melhor_pontos:
            melhor, melhor_pontos, melhor_eco = c, pontos, eco
    if melhor is None:
        return None
    nota = (f"economia de até R$ {melhor_eco:.0f} · " if melhor_eco >= 5 else "") + "itens selecionados, sujeito a disponibilidade do lote de cupons"
    return {"code": melhor.code, "title": melhor.title, "nota": nota}
