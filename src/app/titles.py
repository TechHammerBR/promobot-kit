"""Título, marca e "produto parecido" SEM IA (robô leve do Wyse, 13/10/2026 — pedido do dono).

- limpar(): título curto e legível a partir do título de anúncio (o do AliExpress vem como sopa de palavras-chave).
- mal_traduzido(): título de tradução automática (tudo minúsculo, sem pontuação) — não dá para consertar por regra.
- marca(): marca conhecida citada como FABRICANTE do produto (não vale "para Intel", "compatível com Xiaomi").
- parecidos(): o mesmo produto anunciado por outro vendedor/loja (ex.: 3 anúncios do GameSir Nova Lite no mesmo dia).
"""
import re
import unicodedata

ENCHIMENTO = ("original", "lançamento", "envio imediato", "pronta entrega", "frete grátis", "promoção", "oferta", "100%", "garantia",
              "com nf", "nota fiscal", "lacrado", "brinde", "de alta qualidade", "alta qualidade", "novo modelo", "hot", "new",
              "2024", "2025", "2026", "2027")
_ENCHE = re.compile(r"(?<![\w%])(?:" + "|".join(re.escape(w) for w in sorted(ENCHIMENTO, key=len, reverse=True)) + r")(?![\w%])", re.I)
_NOVO_INICIO = re.compile(r"^\s*(?:novo|nova|new)\b[\s:,-]*", re.I)  # "Nova" no meio pode ser modelo (GameSir Nova Lite)
_PREFIXO = re.compile(r"^\s*([\[(])([^\])]{0,60})([\])])\s*")
_CAUDA = re.compile(r"[,;]?\s+(?:compat[ií]ve(?:l|is)\b|pode suportar\b|adequad[oa] para\b|ideal para\b|aplic[aá]vel\b)", re.I)
_CONECTORES = {"de", "da", "do", "das", "dos", "com", "para", "e", "em", "a", "o", "sem", "por", "no", "na", "ao", "ou"}
_CAP = r"\d+(?:[.,]\d+)?\s?(?:gb|tb)"
_FREQ = r"\d+\s?mhz"
_SERIE_CAP = re.compile(rf"{_CAP}(?:\s*[/ ]\s*{_CAP}){{2,}}", re.I)  # 3+ capacidades = variações do anúncio
_SERIE_FREQ = re.compile(rf"{_FREQ}(?:\s*[/ ]\s*{_FREQ})+", re.I)
_SIGLAS = {"amd": "AMD", "ddr3": "DDR3", "ddr4": "DDR4", "ddr5": "DDR5", "rgb": "RGB", "argb": "ARGB", "usb": "USB", "ssd": "SSD",
           "nvme": "NVMe", "psu": "PSU", "atx": "ATX", "pc": "PC", "led": "LED", "hdmi": "HDMI", "cpu": "CPU", "gpu": "GPU",
           "ram": "RAM", "4k": "4K", "2k": "2K", "8k": "8K", "sata": "SATA", "tws": "TWS", "anc": "ANC", "pwm": "PWM", "hd": "HD",
           "wifi": "Wi-Fi", "ips": "IPS", "oled": "OLED"}

# Marcas aceitas nas ofertas vindas da BUSCA do AliExpress: fabricantes conhecidos no mercado (lojas oficiais, assistência, reviews).
# Ficam de fora as genéricas de placa X99/memória/fonte sem procedência (JGINYUE, QIYIDA, SOYO, KOOTION,
# CUSU, METALFISH, Jumpeak...) e fones "Lenovo" de licenciada (muita falsificação). Forma canônica = como sai escrita no post.
MARCAS = ("8BitDo", "JUHOR", "MOUGOL", "MACHINIST", "GameSir", "Flydigi", "QCY", "Baseus", "UGREEN", "Anker", "Soundcore", "Edifier", "KZ", "TRN", "Tangzu", "Moondrop",
          "Truthear", "FIFINE", "EMEET", "Rapoo", "Logitech", "Razer", "Redragon", "Akko", "AULA", "Royal Kludge", "Ajazz",
          "Attack Shark", "Machenike", "Epomaker", "Keychron", "MCHOSE", "Haylou", "Xiaomi", "Redmi", "POCO", "Amazfit", "Realme",
          "OnePlus", "Samsung", "Sony", "JBL", "HyperX", "Corsair", "SteelSeries", "Kingston", "Crucial", "Lexar", "Netac",
          "SanDisk", "Western Digital", "WD", "ADATA", "XPG", "TeamGroup", "Gigabyte", "ASUS", "MSI", "ASRock", "Biostar",
          "DeepCool", "Thermalright", "ID-COOLING", "Cooler Master", "Arctic", "Noctua", "Lian Li", "Jonsbo", "ORICO", "Hagibis",
          "TP-Link", "Mercusys", "Tenda", "Sonoff", "Ulanzi", "SmallRig", "Teclast", "CHUWI", "Motorola", "Huawei", "Honor",
          "Nothing", "CMF", "Sapphire", "PowerColor", "XFX", "Zotac", "Colorful", "Maxsun", "Elgato", "Insta360", "DJI",
          "Creality", "Bambu Lab", "Anycubic", "Raspberry Pi", "Tronsmart", "1MORE", "SoundPEATS", "Oraimo", "Dareu", "Fantech",
          "Motospeed", "VGN", "Darmoshark", "Monka", "Womier", "Skyloong", "KBDfans", "Acer", "Dell", "Philips", "AOC", "Titan Army",
          "KTC", "Koorui", "Sharkoon", "Montech", "Segotep", "Great Wall", "FSP", "Seasonic", "Super Flower", "be quiet", "Thermaltake",
          "NZXT", "Phanteks", "Valkyrie", "PCCooler", "Segway", "Roborock", "Dreame", "Ecovacs", "Kiwi Ears", "Simgot", "7Hz", "Fiio",
          "Hidizs", "Shanling", "Kinera", "Maono", "Boya", "Hollyland", "Rode", "Zhiyun", "Hohem", "Wacom", "Huion", "XP-Pen",
          "Gaomon", "Veikk", "Beelink", "Minisforum", "GMKtec", "AOOSTAR", "Geekom", "Blitzwolf", "Essager", "Toocki", "Vention",
          "Cuktech", "Zmi", "Romoss", "INIU", "Kodak", "Canon", "Epson", "HP", "Brother")
# plataforma (AMD/Intel): só vale como marca quando o anúncio É um processador
_PLATAFORMA = re.compile(r"\b(amd|ryzen|intel)\b", re.I)
_E_PROCESSADOR = re.compile(r"\b(processador(?:es)?|processor|cpu)\b", re.I)
_NAO_PROCESSADOR = re.compile(r"placa[- ]m[ãa]e|motherboard|cooler|ventilador|dissipador|refrigera|mem[oó]ria ram|\bkit\b|conjunto|"
                              r"mini pc|notebook|laptop|tablet", re.I)
_DEPOIS_DE_PARA = re.compile(r"\b(?:para|for|com|with|compat\w+|suport\w+|adequad\w+|fits?)\b[^,;]{0,30}$", re.I)


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


_MARCA_RE = [(m, re.compile(r"(?<![a-z0-9])" + re.escape(_sem_acento(m).lower()).replace(r"\ ", r"[\s-]?").replace(r"\-", r"[\s-]?")
                            + r"(?![a-z0-9])")) for m in sorted(MARCAS, key=len, reverse=True)]


def marca(titulo: str) -> str | None:
    """Marca conhecida que FABRICA o produto do anúncio (None = marca desconhecida/genérico)."""
    t = _sem_acento(titulo).lower()
    for nome, rx in _MARCA_RE:
        for m in rx.finditer(t):
            if not _DEPOIS_DE_PARA.search(t[:m.start()]):
                return nome
    m = _PLATAFORMA.search(t)
    if m and _E_PROCESSADOR.search(t) and not _NAO_PROCESSADOR.search(t) and not _DEPOIS_DE_PARA.search(t[:m.start()]):
        return "AMD" if m.group(1) in ("amd", "ryzen") else "Intel"
    return None


def mal_traduzido(titulo: str) -> bool:
    """Tradução automática crua: 8+ palavras, quase nenhuma maiúscula depois da primeira e nenhuma vírgula."""
    palavras = [w for w in re.findall(r"[^\W\d_]{3,}", titulo)]
    if len(palavras) < 8 or "," in titulo:
        return False
    return sum(1 for w in palavras[1:] if w[0].isupper()) <= 1


def _prefixo(t: str) -> tuple[str, str]:
    """Separa o aviso do agregador no começo ("[Prime]", "(R$ 22,82 +por- / Prime)") já sem o preço repetido."""
    avisos = []
    while True:
        m = _PREFIXO.match(t)
        if not m:
            break
        dentro = re.sub(r"R\$\s*[\d.,]+", " ", m.group(2))
        dentro = re.sub(r"\+?\s*por\s*-", " ", dentro, flags=re.I)
        dentro = " ".join(dentro.replace("/", " / ").split()).strip(" /-+")
        if dentro and not re.fullmatch(r"[A-Z]{2,3}", dentro):  # "[RU]"/"[BR]" = estoque do vendedor, não interessa
            avisos.append(f"[{re.sub(r' / ', '/', dentro)}]")
        t = t[m.end():]
    return " ".join(avisos), t


def _valor(item: str) -> float:
    n = float(re.match(r"[\d.,]+", item).group(0).replace(",", "."))
    return n * 1024 if item.lower().endswith("tb") else n


def _serie(m: re.Match) -> str:
    """Lista de variações ("128GB 240GB 480GB 1TB") vira faixa ("128GB a 1TB")."""
    itens = sorted({x.replace(" ", "").upper() for x in re.findall(rf"{_CAP}|{_FREQ}", m.group(0), re.I)}, key=_valor)
    if len(itens) == 1:
        return itens[0]
    return f"{itens[0]}/{itens[1]}" if len(itens) == 2 else f"{itens[0]} a {itens[-1]}"


def _sem_repetidas(t: str) -> str:
    saida, vistas = [], set()
    for w in t.split():
        chave = re.sub(r"[^a-z0-9]", "", _sem_acento(w).lower())
        chave = chave[:-1] if len(chave) > 4 and chave.endswith("s") else chave  # fone/fones
        if len(chave) >= 3 and chave not in _CONECTORES:
            if chave in vistas:
                while saida and saida[-1].lower() in _CONECTORES:  # "... de ouvido" repetido: leva o "de" junto
                    saida.pop()
                if w[-1] in ",;:" and saida and saida[-1][-1] not in ",;:":
                    saida[-1] += w[-1]
                continue
            vistas.add(chave)
        saida.append(w)
    return " ".join(saida)


def _maiusculas(t: str) -> str:
    def troca(m: re.Match) -> str:
        w = m.group(0)
        return _SIGLAS.get(w, w)
    t = re.sub(r"(?<![\w.-])[a-z0-9]{2,5}(?![\w-])", troca, t)
    t = re.sub(r"(?<![a-z])(\d+)\s?(gb|tb|mhz|hz|w)\b", lambda m: m.group(1) + {"gb": "GB", "tb": "TB", "mhz": "MHz", "hz": "Hz", "w": "W"}[m.group(2).lower()], t, flags=re.I)
    tl = _sem_acento(t).lower()
    for nome, rx in _MARCA_RE:  # marca na grafia certa (Qcy -> QCY, Deepcool -> DeepCool)
        m = rx.search(tl)
        if m and len(nome) == m.end() - m.start() and t[m.start():m.end()] != nome:
            t = t[:m.start()] + nome + t[m.end():]
    return t


def limpar(titulo: str, limite: int = 60) -> str:
    """Título curto e legível, sem inventar nada: só tira/encurta o que já está no anúncio."""
    bruto = " ".join(titulo.replace("|", " ").replace("【", "[").replace("】", "]").replace("​", "").split())
    aviso, t = _prefixo(bruto)
    t = _NOVO_INICIO.sub("", t)
    t = _ENCHE.sub(" ", t)
    t = " ".join(t.split()).strip(" -,.;:/")
    m = _CAUDA.search(t, 18)
    if m:
        t = t[:m.start()]
    t = _SERIE_FREQ.sub(_serie, _SERIE_CAP.sub(_serie, t))
    t = _sem_repetidas(t)
    t = re.sub(r"\s+([,;:])", r"\1", t).strip(" -,.;:/")
    espaco = limite - (len(aviso) + 1 if aviso else 0)
    if len(t) > espaco:
        corte = t[:espaco + 1]
        pausa = max(corte.rfind(", "), corte.rfind(" - "), corte.rfind(": "), corte.rfind("; "))
        if pausa >= 28:  # termina numa pausa natural do anúncio
            t = corte[:pausa]
        else:
            t = corte[:corte.rfind(" ")] if " " in corte[20:] else t[:espaco]
    t = t.rstrip(" -,.;:/(")
    while " " in t and t.rsplit(" ", 1)[-1].lower() in _CONECTORES:  # não termina em preposição
        t = t.rsplit(" ", 1)[0].rstrip(" -,.;:/(")
    if t.count("(") > t.count(")"):
        t = t[:t.rfind("(")].rstrip(" -,.;:/")
    if len(t) < 8:
        return titulo
    t = _maiusculas(t[:1].upper() + t[1:])
    return f"{aviso} {t}" if aviso else t


_PARADAS = _CONECTORES | {"the", "for", "with", "and", "of", "original", "gamer", "gaming", "jogo", "jogos"}


def _tokens(titulo: str) -> list[str]:
    _, t = _prefixo(" ".join(titulo.split()))
    return [w for w in re.findall(r"[a-z0-9]+", _sem_acento(t).lower()) if len(w) >= 2 and w not in _PARADAS]


def parecidos(t1: str, p1: float | None, t2: str, p2: float | None) -> bool:
    """Mesmo produto em outro anúncio: começos de título quase iguais, sem número de modelo/capacidade diferente e preço próximo."""
    a, b = _tokens(t1), _tokens(t2)
    if len(a) < 3 or len(b) < 3:
        return False
    if p1 and p2 and abs(p1 - p2) / max(p1, p2) > 0.30:
        return False
    fa, fb = set(a[:6]), set(b[:6])
    menor = min(len(fa), len(fb))
    if len(fa & fb) < (4 if menor >= 5 else menor):
        return False
    da, db = {w for w in a if any(c.isdigit() for c in w)}, {w for w in b if any(c.isdigit() for c in w)}
    return not (da and db and not (da <= db or db <= da))


_VARIAS_CAP = re.compile(rf"{_CAP}(?:\s*[/, ]\s*{_CAP})+", re.I)
_RAM_MAIS_DISCO = re.compile(r"notebook|laptop|celular|smartphone|tablet|mini pc|console", re.I)


def variacoes(titulo: str) -> list[str]:
    """Capacidades vendidas no MESMO anúncio ("512GB 1TB 2TB 4TB" -> ["512GB", "1TB", "2TB", "4TB"]), da menor para a maior.
    Serve para o post dizer "a partir de": o preço que a loja informa é o da opção mais barata. Vazio se não for o caso
    (aparelhos em que "8GB/256GB" é memória + armazenamento do mesmo produto não contam)."""
    if _RAM_MAIS_DISCO.search(titulo or ""):
        return []
    m = _VARIAS_CAP.search(titulo or "")
    if not m:
        return []
    itens = sorted({x.replace(" ", "").upper() for x in re.findall(_CAP, m.group(0), re.I)}, key=_valor)
    return itens if len(itens) >= 2 else []
