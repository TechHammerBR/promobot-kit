"""Validação ANTI-GOLPE das ofertas do AliExpress (pedido do dono, 07/10/2026: "sempre valide a qualidade, configuração e afins").

Caso real: "Laptop Intel i9-9880H 32GB 2TB" por R$ 1.455 (um i9 de verdade com 32GB custa vários mil reais) com banner "BIG SALE".
Camadas (a primeira que reprovar manda): palavras de usado/recondicionado/amostra -> nota e vendas -> ficha técnica x preço por categoria
(notebook, celular, SSD/pendrive/cartão = capacidade falsa, placa de vídeo, processador, memória) -> marca desconhecida em item caro.
Os pisos de preço são deliberadamente BAIXOS (só pegam o que é obviamente irreal; marca conhecida e preço normal passam).
"""
import re

BANIDAS = re.compile(
    r"\b(used|second[- ]?hand|pre[- ]?owned|refurbished|renewed|remanufactured|mining|miner|usad[oa]s?|recondicionad[oa]s?|seminov[oa]s?|"
    r"tray|pulled|scrap|for parts|broken|lot of|random|lucky bag|sacola da sorte|mystery|blind box|replica|clone|counterfeit|unbranded|no brand|engineering sample)\b"
    r"|散片|二手", re.I)
ACESSORIO = re.compile(
    r"\b(case|cover|bag|sleeve|stand|holder|mount|bracket|dock|hub|adapter|adaptor|charger|cable|cord|protector|film|glass|skin|sticker|"
    r"decal|desk|table|bed|backpack|pouch|strap|grip|ring|cooler|fans?|cooling|pads?|radiator|heatsink|paste|riser|enclosure|caddy|reader|keycap|keycaps|"
    r"switch|switches|cleaner|cloth|brush|backplate|water ?block|capa|bolsa|suporte|mochila|película|adaptador|carregador|cabo)\b", re.I)

MARCAS_NOTEBOOK = re.compile(r"lenovo|thinkpad|ideapad|legion|asus|rog|vivobook|zenbook|tuf|acer|aspire|nitro|predator|swift|\bhp\b|omen|victus|"
                             r"pavilion|dell|inspiron|alienware|latitude|msi|gigabyte|aorus|huawei|matebook|honor|magicbook|xiaomi|redmi|samsung|"
                             r"galaxy book|apple|macbook|microsoft|surface|lg gram|chuwi|teclast|machenike|razer|jumper|bmax|ninkear|\bkuu\b", re.I)
MARCAS_CELULAR = re.compile(r"xiaomi|redmi|poco|samsung|galaxy|motorola|\bmoto\b|realme|honor|oneplus|nubia|redmagic|oppo|vivo|iqoo|infinix|tecno|zte|"
                            r"huawei|apple|iphone|pixel|nothing|asus|rog phone|sony|xperia|blackview|ulefone|doogee|oukitel|cubot|umidigi|nokia|hmd|"
                            r"tcl|lenovo", re.I)
MARCAS_TABLET = re.compile(r"samsung|galaxy tab|xiaomi|redmi pad|lenovo|huawei|honor|apple|ipad|oppo|oneplus|realme|teclast|chuwi|blackview|"
                           r"doogee|alldocube|amazon|microsoft|asus|nokia|tcl", re.I)

PISO_GPU = {"4090": 9000, "4080": 5500, "4070": 3000, "4060": 1500, "3090": 4500, "3080": 2800, "3070": 1900, "3060": 1200,
            "2080": 1500, "2070": 1100, "2060": 900, "1660": 550, "1650": 450, "1060": 350, "1050": 250,
            "7900": 4500, "7800": 2800, "7700": 2200, "7600": 1300, "6800": 2000, "6700": 1300, "6600": 900,
            "580": 300, "570": 220, "5700": 600, "b580": 1500, "a770": 1500, "a750": 1100}


PERIFERICO = re.compile(
    r"\b(mouse|mice|keyboard|keycaps?|headset|headphones?|earphones?|earbuds?|speakers?|webcam|microphone|monitor|controller|gamepad|"
    r"joystick|cooler|cooling|fan|charger|adapter|adaptor|cable|dock|hub|stand|bag|case|sleeve|holder|mount|pad|ssd|nvme|hdd|ram|memory|"
    r"gpu|processor|cpu|projector|printer|power bank|battery|screen|display|lcd|motherboard|keypad|usb)\b", re.I)


def _principal(t: str, palavra: str) -> bool:
    """True se `palavra` (regex) é o PRODUTO do anúncio: aparece e não vem depois de 'for/compatible with' nem de outro periférico
    (ex.: 'Gaming Mouse ... for PC Laptop' é um mouse; '14.1 Inch Ultra Thin Laptop ... 2TB SSD' é um notebook)."""
    m = re.search(palavra, t, re.I)
    if not m:
        return False
    antes = t[:m.start()]
    if re.search(r"\b(for|compatible|fits?|with|suitable|supports?)\b[^,]{0,25}$", antes, re.I):
        return False
    return not PERIFERICO.search(antes)


def _capacidades(t: str) -> tuple[float, float]:
    """(RAM em GB, armazenamento em GB) citados no título; maiores valores."""
    ram = disco = 0.0
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(tb|gb)\b", t, re.I):
        val = float(m.group(1).replace(",", ".")) * (1024 if m.group(2).lower() == "tb" else 1)
        ctx = t[max(0, m.start() - 14): m.end() + 14].lower()
        if re.search(r"ssd|hdd|nvme|\brom\b|storage|disk|armazen|m\.2|emmc|ufs", ctx) or val >= 256:
            disco = max(disco, val)
        elif re.search(r"ram|ddr|memory|memória|lpddr", ctx) or val <= 64:
            ram = max(ram, val)
    return ram, disco


def _nivel_cpu(t: str) -> int:
    t = t.lower()
    for n in (9, 7, 5, 3):
        if re.search(rf"\bi{n}\b|\bi{n}-|ryzen\s*{n}\b|ultra\s*{n}\b", t):
            return n
    return 0


def _notebook(t: str, preco: float) -> str | None:
    if not _principal(t, r"\b(laptop|notebook|ultrabook|netbook)\b") or ACESSORIO.search(t):
        return None
    ram, disco = _capacidades(t)
    minimo = max(1100, {9: 4800, 7: 3000, 5: 1900, 3: 1300}.get(_nivel_cpu(t), 0))
    for limite, valor in ((64, 7000), (32, 3200), (24, 2500), (16, 1500)):
        if ram >= limite:
            minimo = max(minimo, valor)
            break
    for limite, valor in ((4096, 5000), (2048, 2500), (1024, 1400)):
        if disco >= limite:
            minimo = max(minimo, valor)
            break
    if re.search(r"\brtx\s*40\d0", t, re.I):
        minimo = max(minimo, 6000)
    elif re.search(r"\brtx\s*[23]0\d0|\bgtx\s*1[0-6]\d0", t, re.I):
        minimo = max(minimo, 3500)
    if preco < minimo:
        return f"notebook com ficha técnica irreal: R$ {preco:.0f} (esperado a partir de R$ {minimo:.0f})"
    if preco >= 700 and not MARCAS_NOTEBOOK.search(t):
        return "notebook de marca desconhecida"
    return None


def _celular(t: str, preco: float) -> str | None:
    if not _principal(t, r"\b(smartphone|cellphone|mobile phone|celular|phone)\b") or ACESSORIO.search(t):
        return None
    ram, disco = _capacidades(t)
    minimo = 250
    for limite, valor in ((16, 1400), (12, 900), (8, 450)):
        if ram >= limite:
            minimo = max(minimo, valor)
            break
    for limite, valor in ((1024, 1500), (512, 900), (256, 450)):
        if disco >= limite:
            minimo = max(minimo, valor)
            break
    if re.search(r"snapdragon\s*8|dimensity\s*9|\b8 gen\b", t, re.I):
        minimo = max(minimo, 1800)
    if preco < minimo:
        return f"celular com ficha técnica irreal: R$ {preco:.0f} (esperado a partir de R$ {minimo:.0f})"
    if preco >= 500 and not MARCAS_CELULAR.search(t):
        return "celular de marca desconhecida"
    return None


def _tablet(t: str, preco: float) -> str | None:
    if not _principal(t, r"\btablet\b") or ACESSORIO.search(t):
        return None
    if preco >= 700 and not MARCAS_TABLET.search(t):
        return "tablet de marca desconhecida"
    return None


def _armazenamento(t: str, preco: float) -> str | None:
    m = re.search(r"\b(ssd|nvme|m\.2|hdd|hard (?:disk|drive)|flash drive|usb drive|pen ?drive|memory card|micro ?sd|tf card|sd card|cfexpress)\b", t, re.I)
    if not m or ACESSORIO.search(t):
        return None
    cap = max(_capacidades(t))
    if cap < 128:
        return None
    k = m.group(1).lower()
    por_tb = 170 if k in ("ssd", "nvme", "m.2") else 100 if k in ("hdd", "hard disk", "hard drive") else 150
    minimo = cap / 1024 * por_tb
    if preco < minimo:
        return f"capacidade irreal: {cap / 1024:.1f}TB por R$ {preco:.0f} (golpe de capacidade falsa)"
    return None


def _placa_video(t: str, preco: float) -> str | None:
    if ACESSORIO.search(t):
        return None
    m = re.search(r"\b(?:rtx|gtx|rx|arc)\s*-?\s*([ab]?\d{3,4})\b", t, re.I)
    minimo = PISO_GPU.get(m.group(1).lower()) if m else None
    if minimo and preco < minimo:
        return f"placa de vídeo com preço irreal: R$ {preco:.0f} (esperado a partir de R$ {minimo:.0f})"
    return None


def _processador(t: str, preco: float) -> str | None:
    if ACESSORIO.search(t) or re.search(r"\b(laptop|notebook|ultrabook|netbook|phone|mini pc|desktop pc|all[- ]in[- ]one)\b", t, re.I):
        return None
    if not re.search(r"\b(processor|cpu|processador)\b", t, re.I):
        return None
    minimo = {9: 900, 7: 600, 5: 280}.get(_nivel_cpu(t))
    if minimo and preco < minimo:
        return f"processador com preço irreal: R$ {preco:.0f} (esperado a partir de R$ {minimo:.0f})"
    return None


def _memoria(t: str, preco: float) -> str | None:
    m = re.search(r"\bddr([345])\b", t, re.I)
    if not m or not re.search(r"\b(ram|memory|memória|dimm|sodimm|so-dimm)\b", t, re.I) or ACESSORIO.search(t):
        return None
    ram, _ = _capacidades(t)
    if ram < 8:
        return None
    minimo = ram * {"5": 11, "4": 6, "3": 4}[m.group(1)]
    if preco < minimo:
        return f"memória RAM com preço irreal: {ram:.0f}GB por R$ {preco:.0f}"
    return None


def verificar(titulo: str, preco: float, antigo: float | None = None, vendas: int | None = None, nota: float | None = None) -> str | None:
    """None = parece legítima; senão o motivo da reprovação (frase curta para o log/diagnóstico)."""
    m = BANIDAS.search(titulo)
    if m:
        return f"usado/recondicionado/amostra ({m.group(0).lower()})"
    if re.search(r"\b(ES|QS)\b", titulo):
        return "amostra de engenharia (ES/QS)"
    if nota is not None and preco >= 150 and nota < 4.5:
        return f"nota baixa ({nota})"
    if vendas is not None:
        if preco >= 1500 and vendas < 100:
            return f"poucas vendas ({vendas}) para item de R$ {preco:.0f}"
        if preco >= 500 and vendas < 30:
            return f"poucas vendas ({vendas}) para item de R$ {preco:.0f}"
    for regra in (_notebook, _celular, _tablet, _armazenamento, _placa_video, _processador, _memoria):
        motivo = regra(titulo, preco)
        if motivo:
            return motivo
    return None
