"""Texto dos posts (padrão dos canais de referência do dono: GPCR Promo, GalgoPromo, Ofertas Adrenaline).

🔥📱 Título curto

💰 Por: R$ 99,90 no PIX  (de R$ 299,90 · -67%)
💳 ou 10x de R$ 10,99 sem juros
🎟️ Cupom: CODIGO

🛒 Link do produto: https://meli.la/...
⚠️ Preço e disponibilidade podem variar.

📲 Entre no nosso grupo de ofertas:
WhatsApp: <link>
Telegram: <link>
#Anuncio

Mesmo conteúdo em dois dialetos: Telegram (HTML) e WhatsApp (*negrito*, ~riscado~).
"""
import html
import re

from app.config import settings

MAX_TITLE = 90

# emoji pelo tipo de produto (primeira palavra-chave que aparecer no título)
CATEGORY_EMOJI = [
    # CASA primeiro (15/10, dono: "stickers do grupo de casa não fazem sentido"): "jogo de toalhas/panelas/copos" não é videogame
    (r"toalha de banho|jogo de toalha|toalhas|roup[aã]o|toalheiro", "🛁"),
    (r"lencol|len[cç]ol|jogo de cama|edredom|cobertor|travesseiro|fronha|colcha|manta\b", "🛏️"),
    (r"jogo (de )?(panela|pote|copo|ta[cç]a|talher|prato|faca|x[ií]cara|americano)|panela|frigideira|pote|copo|ta[cç]a|talher|faqueiro|"
     r"prato|x[ií]cara|caneca|garrafa|marmita|lancheira|t[aá]bua de corte|utens[ií]lio|escorredor|assadeira|forma de", "🍽️"),
    (r"organizador|prateleira|nicho|cabide|sapateira|lixeira|cesto|varal|caixa organizadora|porta.(toalha|tempero|frios)", "🧺"),
    (r"cortina|tapete(?! gamer)|almofada|quadro|decora|vaso|persiana", "🏡"),
    (r"lumin[aá]ria|abajur|l[aâ]mpada|fita de led|arandela", "💡"),
    (r"chuveiro|ducha|torneira|box de banheiro|assento sanit", "🚿"),
    (r"vassoura|mop\b|rodo\b|balde|detergente|sab[aã]o|amaciante|papel higi|papel toalha|esponja|desinfetante", "🧹"),
    (r"celular|smartphone|iphone|galaxy|moto g|redmi|xiaomi", "📱"),
    (r"notebook|laptop|macbook|chromebook", "💻"),
    (r"monitor", "🖥️"),
    (r"smart ?tv|televis|\btv\b|projetor", "📺"),
    (r"fone|headset|earbud|airpods", "🎧"),
    (r"caixa de som|soundbar|speaker", "🔊"),
    (r"console|playstation|ps5|xbox|nintendo|switch|controle|jogo|game", "🎮"),
    (r"smartwatch|rel[oó]gio", "⌚"),
    (r"tablet|ipad|kindle", "📲"),
    (r"ssd|hd externo|pendrive|mem[oó]ria|placa de v[ií]deo|processador|placa.m[ãa]e|gabinete|fonte", "🧩"),
    (r"teclado|mouse|webcam|microfone", "⌨️"),
    (r"c[aâ]mera|drone|gopro", "📷"),
    (r"roteador|wi-?fi|starlink|repetidor", "📡"),
    (r"cadeira", "🪑"),
    (r"air ?fryer|fritadeira|panela|cafeteira|liquidificador|micro-?ondas|geladeira|fog[aã]o", "🍳"),
    (r"aspirador|ventilador|ar.condicionado|lavadora|ferro", "🏠"),
    (r"t[eê]nis|sapato|sand[aá]lia|camis|cal[cç]a|jaqueta|mochila|bolsa", "👟"),
    (r"perfume|shampoo|maquiagem|creme|barbeador|secador", "💄"),
    (r"creatina|whey|suplemento|vitamina", "💪"),
    (r"furadeira|parafusadeira|ferramenta|serra", "🔧"),
    (r"brinquedo|boneca|lego|beb[eê]", "🧸"),
    (r"pneu|carro|automotiv|moto\b", "🚗"),
]


def category_emoji(title: str) -> str:
    t = title.lower()
    return next((e for pat, e in CATEGORY_EMOJI if re.search(pat, t)), "🛍️")


def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def short_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    if len(t) <= MAX_TITLE:
        return t
    cut = t[:MAX_TITLE].rsplit(" ", 1)[0]
    return cut.rstrip(",;:-–") + "…"


def payment_lines(payment: str | None) -> tuple[str, str | None]:
    """(sufixo do preço, linha extra) a partir do texto de pagamento da página do ML."""
    if not payment:
        return "", None  # página não informou: não afirmamos à vista/PIX
    p = re.sub(r"(\d)\s*,\s*(\d)", r"\1,\2", payment)  # "R$ 48 , 33" -> "R$ 48,33"
    p = re.sub(r"\s+", " ", p).strip()
    if "outros meios" in p:  # preço principal é no PIX
        m = re.search(r"R\$ ?[\d.]+(?:,\d{2})?", p)
        return "no PIX", (f"💳 ou {m.group(0)} em outros meios" if m else None)
    m = re.search(r"(?:ou (R\$ ?[\d.]+(?:,\d{2})?) em )?(\d{1,2}x) ?(?:de )?(R\$ ?[\d.]+(?:,\d{2})?) sem juros", p)
    if m:
        total = f"{m.group(1)} em " if m.group(1) else ""
        return "à vista", f"💳 ou {total}{m.group(2)} de {m.group(3)} sem juros"
    return "à vista", None  # ex.: "com Linha de Crédito" (empréstimo) não entra no post


# 28/10/2026: chamada v2 (dono aprovou apos comparar com 8 canais): selo de desconto no titulo, sem repetir o %, linha da loja (confianca). CHAMADA_V2=0 desliga.
_LOJA = {"mercadolivre": "no Mercado Livre", "shopee": "na Shopee", "amazon": "na Amazon", "kabum": "na KaBuM"}
SELO_MIN_PCT = 35


def _chamada_v2() -> bool:
    import os
    return os.getenv("CHAMADA_V2", "1").strip().lower() not in ("0", "false", "nao", "não", "off")


def _linha_loja(o) -> str | None:
    """'Vendido na Shopee' (so quando a fonte e a propria loja; agregadores como Pelando/Promobit e AliExpress, que ja tem aviso proprio, ficam de fora)."""
    loja = _LOJA.get((getattr(o, "source", "") or "").lower())
    return f"🏪 Vendido {loja}" if loja else None


def render(o, channel: str = "telegram", canal: str = "tech") -> str:
    tg = channel == "telegram"
    esc = html.escape if tg else (lambda s: s)
    bold = (lambda s: f"<b>{s}</b>") if tg else (lambda s: f"*{s}*")
    strike = (lambda s: f"<s>{s}</s>") if tg else (lambda s: f"~{s}~")
    mono = (lambda s: f"<code>{s}</code>") if tg else (lambda s: f"*{s}*")

    discount = 0
    situacao = getattr(o, "preco_situacao", None)
    if o.price and o.old_price and o.old_price > o.price and situacao != "estavel":
        discount = round((1 - o.price / o.old_price) * 100)
    hype = "🚨" if discount >= 60 else ("🔥" if discount >= 35 else "⭐")

    title = getattr(o, "post_title", None) or o.title
    v2 = _chamada_v2()
    selo = f"-{discount}% | " if (v2 and discount >= SELO_MIN_PCT) else ""
    lines = [f"{hype}{category_emoji(title)} {bold(esc(selo + short_title(title)))}", ""]
    if o.price and o.price > 0:
        how, extra = payment_lines(getattr(o, "payment", None))
        from app.titles import variacoes
        ali = "aliexpress." in (o.url or "")
        opcoes = variacoes(o.title) if ali else []  # anúncio com várias capacidades: o preço é o da mais barata
        rotulo = "A partir de" if opcoes else "Por"
        price = f"💰 {rotulo}: {bold(brl(o.price))}" + (f" (versão {opcoes[0]})" if opcoes else "") + (f" {how}" if how else "")
        if discount:
            price += f"  ({strike(brl(o.old_price))})" if selo else f"  ({strike(brl(o.old_price))} · -{discount}%)"
        lines.append(price)
        if extra:
            lines.append(esc(extra))
    if situacao == "queda" and getattr(o, "preco_dias", 0) >= 3:
        lines.append(f"📉 Menor preço dos últimos {o.preco_dias} dias (pelo nosso histórico)")
    if "aliexpress." in (o.url or ""):
        lines.append("🌎 Compra internacional (AliExpress) · confira taxas no checkout")
        lines.append("ℹ️ O preço muda conforme a opção escolhida no anúncio (capacidade, cor, kit).")
    from app.engine import cupom_proibido
    if o.coupon and not cupom_proibido(o.url or ""):
        lines.append(f"🎟️ Cupom: {mono(esc(o.coupon))} (sujeito a disponibilidade do lote de cupons)")
    dica = getattr(o, "cupom_dica", None)
    if dica and not o.coupon:
        lines.append(f"🎟️ Tente o cupom {mono(esc(dica['code']))}: {esc(dica['title'])} ({esc(dica['nota'])})")
    lines.append("")
    loja_linha = _linha_loja(o) if v2 else None
    if loja_linha:
        lines.append(loja_linha)
    lines += [f"🛒 Link do produto: {o.affiliate_url or o.url}", "⚠️ Oferta válida enquanto durarem os estoques. Preço pode variar."]
    lines += invite_lines(canal, channel)
    if settings.post_hashtag:
        lines += ["", settings.post_hashtag]
    return "\n".join(lines)


def chamada_grupos(clicavel: bool = True) -> str:
    """Divulgação dos grupos de ofertas nas redes sociais (Instagram não tem link clicável na legenda)."""
    if not clicavel:
        return "📲 Ofertas grátis todo dia nos nossos grupos de TECNOLOGIA e de CASA — link na bio!"
    linhas = ["📲 Ofertas grátis todo dia nos nossos grupos:"]
    if settings.group_invite_link:
        linhas.append(f"💻 Tecnologia: {settings.group_invite_link}")
    if settings.lar_enabled and settings.lar_invite_link:
        linhas.append(f"🏠 Casa: {settings.lar_invite_link}")
    if settings.telegram_invite_link:
        linhas.append(f"📢 Telegram: {settings.telegram_invite_link}")
    return "\n".join(linhas)


def grupos_threads() -> str:
    """Os 3 grupos em 3 linhas curtas (Threads: link clicável no texto, limite de 500 caracteres)."""
    l = ["📲 Ofertas grátis todo dia:"]
    if settings.group_invite_link:
        l.append(f"💻 Tecnologia: {settings.group_invite_link}")
    if settings.lar_enabled and settings.lar_invite_link:
        l.append(f"🏠 Casa: {settings.lar_invite_link}")
    if settings.telegram_invite_link:
        l.append(f"📢 Telegram: {settings.telegram_invite_link}")
    return "\n".join(l)


def invite_lines(canal: str = "tech", channel: str = "whatsapp") -> list[str]:
    """Rodapé com os OUTROS canais (dono, 14/10/2026): quem está no grupo de tecnologia do WhatsApp vê o Telegram e o grupo de
    casa; no Telegram, o grupo do WhatsApp e o de casa; no grupo de casa, o de tecnologia e o Telegram."""
    casa = settings.lar_invite_link if settings.lar_enabled else ""
    itens = []
    if canal == "lar":
        if settings.group_invite_link:
            itens.append(f"💻 Tecnologia (TechHammer): {settings.group_invite_link}")
        if settings.telegram_invite_link:
            itens.append(f"📢 Telegram TechHammer: {settings.telegram_invite_link}")
    else:
        if channel == "telegram" and settings.group_invite_link:
            itens.append(f"💬 Grupo no WhatsApp: {settings.group_invite_link}")
        if channel != "telegram" and settings.telegram_invite_link:
            itens.append(f"📢 Canal no Telegram: {settings.telegram_invite_link}")
        if casa:
            itens.append(f"🏠 Ofertas para casa: {casa}")
    return ["", "📲 Conheça também:", *itens] if itens else []
