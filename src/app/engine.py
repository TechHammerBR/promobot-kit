"""Motor de regras: decide se uma oferta deve ser publicada."""
import re
import unicodedata
from datetime import timedelta
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Offer, now
from app.schemas import RawOffer


def product_key(url: str) -> str:
    """Identidade do produto (independe de preço/título): MLB do ML, ASIN da Amazon, senão host+path."""
    m = re.search(r"MLB-?(\d{6,})", url, re.I)
    if m:
        return f"MLB{m.group(1)}"
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    if m:
        return f"AMZ{m.group(1)}"
    m = re.search(r"aliexpress\.[a-z.]+/item/(\d+)", url)
    if m:
        return f"ALI{m.group(1)}"
    p = urlparse(url)
    return f"{p.netloc.lower()}{p.path.rstrip('/')}"[:64]


# títulos do AliExpress vêm em inglês
TECH_EN = ("ssd", "nvme", "graphics card", "gpu", "keyboard", "mouse", "headset", "gamepad", "controller", "ddr4",
           "ddr5", "ram", "processor", "cpu", "motherboard", "usb hub", "monitor", "cooler", "pc case", "power supply",
           "earbuds", "smartphone", "tablet", "webcam", "microphone", "laptop", "notebook", "gaming", "router")


# palavras de tecnologia que também existem na cozinha/casa ("Mini Processador Manual 3 Lâminas" saiu no grupo em 13/10)
NAO_TECH = ("processador manual", "processador de alimentos", "mini processador", "multiprocessador", "lâmina", "lamina", "aço inox",
            "liquidificador", "triturador", "picador", "mixer", "cozinha", "panela", "fritadeira", "air fryer", "cafeteira",
            "ventilador de teto", "ventilador de mesa", "ventilador de coluna", "mouse pad de mesa de jantar", "controle de portão",
            "memória afetiva", "placa decorativa", "placa de carro", "fonte de água", "fonte para gato", "bebedouro")


def is_tech(title: str) -> bool:
    t = title.lower()
    if any(k in t for k in NAO_TECH):
        return False
    return (any(k.strip() and k.strip() in t for k in settings.priority_keywords.split(","))
            or any(re.search(rf"\b{re.escape(k)}\b", t) for k in TECH_EN))


def _sem_acento(x: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", x) if unicodedata.category(ch) != "Mn")


def is_lar(title: str) -> bool:
    """Produto de casa (cozinha, eletrodoméstico, limpeza, cama/mesa/banho, móveis, ferramentas)?"""
    t = f" {_sem_acento(title.lower())} "  # sem acento nos dois lados: "racao" e "ração" valem igual
    return any(k.strip() and re.search(rf"(?<![\w]){re.escape(_sem_acento(k.strip()))}(?![\w])", t)
               for k in (settings.lar_keywords + "," + settings.lar_basicos).split(","))


# palavras que denunciam produto de tecnologia mesmo quando o título tem palavra de casa ("Mixer" de áudio, 14/10)
SINAL_TECH = re.compile(r"(?<!\w)(jogos|gamer|gaming|games?|pc|ps4|ps5|xbox|usb|rgb|microfone|mic|xlr|streaming|podcast|"
                        r"hdmi|notebook|monitor|teclado|mouse|headset|fone|smartphone|celular|tablet)(?!\w)", re.I)


BASICO_LAR = re.compile(r"chinelo|sand[aá]lia|camiseta|legging|short|meia|cueca|pijama|shampoo|xampu|condicionador|sabonete|desodorante|creme dental|escova de dente|"
                        r"protetor solar|hidratante|perfume|esmalte|absorvente|fralda|lenço umedecido|squeeze|coqueteleira|mochila|necessaire|lancheira|garrafa|"
                        r"saco de lixo|pano|esponja|balde|caderno|caneta|ração|brinquedo|escova de cabelo|barbeador|toalha|len[cç]ol|organizador|pote", re.I)
CARO_LAR = re.compile(r"geladeira|refrigerador|freezer|fog[aã]o|cooktop|coifa|lava[- ]lou[cç]as|m[aá]quina de lavar|lavadora|secadora|ar[- ]condicionado|split|"
                      r"vaso sanit|caixa acoplada|sof[aá]|guarda-roupa|colch[aã]o|rack|estante|furadeira|parafusadeira|serra|lixadeira|micro-?ondas|forno el[eé]trico", re.I)


PACOTE_LAR = re.compile(r"\bkit\b|\bpack\b|\b\d+ ?(un|unid|unidades|pe[çc]as)\b|\b\d+ ?(kg|l|litros)\b|ra[çc][ãa]o|fralda|detergente|amaciante|papel higi|lava[- ]roupas", re.I)


def canal_de(title: str) -> str:
    """Para qual canal a oferta vai: tecnologia (grupo TechHammer) ou casa (comunidade Meu lar, minha oferta)."""
    if settings.lar_enabled and not is_tech(title) and not SINAL_TECH.search(title) and is_lar(title):
        return "lar"
    return "tech"


def cupom_proibido(url: str) -> bool:
    """Loja cujo programa de afiliados proíbe cupom que não veio da rede (KaBuM, Samsung)."""
    host = urlparse(str(url)).netloc.lower()
    return any(h.strip() and h.strip() in host for h in settings.no_outside_coupon_hosts.split(","))


def queda_expressiva(session: Session, key: str, title: str, price: float | None) -> bool:
    """Já publicado dentro de REPEAT_DAYS: só pode repetir se o preço novo for >= REPEAT_MIN_DROP (30%) menor que o da última vez."""
    since = now() - timedelta(days=settings.repeat_days)
    ultimo = session.scalars(select(Offer.price).where(
        or_(Offer.product_key == key, func.lower(func.substr(Offer.title, 1, 35)) == title[:35].lower()),
        Offer.status == "posted", Offer.posted_at >= since).order_by(Offer.posted_at.desc()).limit(1)).first()
    return bool(ultimo and price and price <= ultimo * (1 - settings.repeat_min_drop))


def evaluate(offer: RawOffer, session: Session, key: str, canal: str = "tech") -> str | None:
    """Retorna o motivo da rejeição, ou None se aprovada."""
    if cupom_proibido(str(offer.url)) and (offer.coupon or re.search(r"\bcupo(m|ns)\b", offer.title, re.I)):
        return "cupom não autorizado pela loja (regra do programa de afiliados)"
    if offer.price <= 0 and not offer.coupon:
        return "preço inválido"
    title = offer.title.lower()
    for word in filter(None, (w.strip().lower() for w in settings.banned_words.split(","))):
        if word in title:
            return f"palavra proibida: {word}"
    if "aliexpress." in str(offer.url):  # golpe de ficha técnica x preço, usado, amostra, marca desconhecida (alicheck.py)
        from app.alicheck import verificar
        suspeita = verificar(offer.title, offer.price, offer.old_price, offer.vendas, offer.nota)
        if suspeita:
            return f"AliExpress: {suspeita}"
    # foco do canal: tecnologia >= MIN_DISCOUNT_PCT; outras categorias só "oferta absurda"
    # AliExpress: busca já é só de tecnologia e a IA judge_ali confere na publicação
    minimum = settings.min_discount_pct if is_tech(offer.title) or offer.source == "aliexpress" else settings.absurd_discount_pct
    if canal == "lar":
        minimum = settings.lar_min_discount_pct
    # Pelando não informa o preço antigo: a temperatura (votos da comunidade) já filtrou
    curated = offer.source in ("pelando", "promobit", "gatry", "canais") and not offer.old_price and (is_tech(offer.title) or canal == "lar")
    if offer.source == "shopee" and not offer.old_price and canal == "lar" and (offer.vendas or 0) >= 2000 and (offer.nota or 0) >= 4.7:
        curated = True  # casa: item de loja oficial/indicada com muitíssima venda
    if offer.source == "shopee" and not offer.old_price and is_tech(offer.title) and (offer.vendas or 0) >= 1000 and (offer.nota or 0) >= 4.7:
        curated = True  # loja oficial/indicada já filtrada no coletor + muita venda e nota alta: vale mesmo sem preço antigo
    if not offer.coupon and offer.source not in ("pelando", "canais") and not curated and offer.discount_pct < minimum:
        return f"desconto {offer.discount_pct}% < {minimum}%"
    # sem repetir: produto já publicado nos últimos N dias, ou já esperando na fila
    since = now() - timedelta(days=settings.repeat_days)
    if session.scalar(select(Offer.id).where(Offer.product_key == key, Offer.status.in_(("new", "pending")))):
        return "duplicada"  # já esperando na fila
    if session.scalar(select(Offer.id).where(Offer.product_key == key, Offer.status == "posted", Offer.posted_at >= since)):
        if not queda_expressiva(session, key, offer.title, offer.price):
            return "duplicada"
    return None


HARD_CORE = re.compile(r"rtx|gtx|geforce|radeon|\brx ?\d{3,4}|placa de v[ií]deo|ryzen|core i[3579]|\bi[3579]-\d|processador|placa[- ]m[ãa]e|mem[óo]ria ram|\bddr[45]\b|\bssd\b|nvme|monitor", re.I)


def score(offer: RawOffer, monetized: bool) -> float:
    # prioriza desconto alto e links que geram comissão
    tech = is_tech(offer.title)
    heat = min((offer.temp or 0) / 8, 30)  # oferta muito votada pela comunidade sobe na fila
    base = offer.discount_pct + (15 if monetized else 0) + (10 if offer.coupon else 0) + (settings.priority_bonus if tech else 0) + heat
    if tech and HARD_CORE.search(offer.title):  # o que os grupos grandes vendem mais: hardware de núcleo (23/10)
        base += 15
        if (offer.price or 0) >= 800 and offer.discount_pct >= 15:
            base += 10  # ticket alto com desconto de verdade
    if not tech and canal_de(offer.title) == "lar":  # grupo de CASA: coisa do dia a dia barata sobe; eletrodoméstico/obra caro desce (dono, 16/10)
        p = offer.price or 0
        base += 12 if p <= 60 else 18 if p <= 120 else 16 if p <= 250 else 8 if p < 600 else -2 if p < 1500 else -20  # 23/10: concorrentes têm 34% <= R$ 60 e 20% > R$ 250
        if PACOTE_LAR.search(offer.title):
            base += 10  # supermercado/limpeza em kit ou pacote vende bem nos grupos grandes
        if BASICO_LAR.search(offer.title):
            base += 15
        if CARO_LAR.search(offer.title) and offer.discount_pct < 50:
            base -= 20
    return base
