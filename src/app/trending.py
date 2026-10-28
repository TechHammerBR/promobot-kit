"""Produtos quentes do dia (23/10/2026, pedido do dono: 'grupo de ofertas mais interessante').

Lê a página PÚBLICA dos canais de promoção do Telegram (t.me/s/<canal>, sem login) só como SINAL DE DEMANDA: pega o modelo do produto no título
(ex.: 'Ryzen 5 7600X3D', 'RTX 5060', 'A520M-A') e o robô busca esse mesmo modelo na Shopee com o NOSSO link de afiliado. Não copia texto, foto nem link de ninguém.
Sem IA, leve (8 requisições por hora). Estado em data/trending_kw.json.
"""
import html
import json
import re
import time

import httpx

from app.config import DATA_DIR, settings
from app.log import log

ARQ = DATA_DIR / "trending_kw.json"
IDX = DATA_DIR / "trending_idx"
VALIDADE_S = 3600
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# modelo = token com letra e número (b550m, 7600x3d, a520m-a) ou rtx/gtx/rx + número
TOKEN = re.compile(r"\b(?=[a-z0-9-]*\d)(?=[a-z0-9-]*[a-z])[a-z0-9-]{4,13}\b", re.I)
GPU = re.compile(r"\b(?:rtx|gtx|rx|arc)\s?\d{3,4}(?:\s?(?:ti|super|xt|gre))?\b", re.I)
RUIDO = re.compile(r"^(\d+(?:gb|tb|mb|mhz|ghz|hz|w|ml|kg|mm|cm|mp|dpi|v|l|x|g|k)|hdr\d*|\d{3,4}p|ddr\d|gen\d|ip\d+|wi-?fi\d*|usb\d*|bluetooth\d*|\d+x\d+|"
                   r"[a-z]*\d{4}$|.*(?:site|full|off|frete|cupom|prime).*)$", re.I)
HARDWARE = re.compile(r"placa|processador|ryzen|core i|ssd|nvme|mem[óo]ria|monitor|gabinete|fonte|cooler|teclado|mouse|headset|notebook|rtx|gtx|radeon|roteador|"
                      r"webcam|microfone|controle|caixa de som|fone|tv |smartphone|galaxy|redmi|poco|iphone", re.I)


def _titulos(canal: str) -> list[str]:
    h = httpx.get(f"https://t.me/s/{canal}", headers=UA, timeout=25, follow_redirects=True).text
    out = []
    for m in re.finditer(r'tgme_widget_message_text[^>]*>(.*?)</div>', h, re.S):
        txt = re.sub(r"<br\s*/?>", "\n", m.group(1))
        txt = html.unescape(re.sub(r"<[^>]+>", "", txt)).strip()
        linha = next((x.strip() for x in txt.splitlines() if len(x.strip()) > 12), "")
        linha = re.sub(r"[^\w\s\-./,+'\"]", " ", linha)  # tira emoji
        if linha:
            out.append(re.sub(r"\s+", " ", linha))
    return out


def _consulta(titulo: str) -> str | None:
    """'Processador AMD Ryzen 5 7600X3D 4.1GHz ...' -> 'amd ryzen 5 7600x3d' (até 4 palavras antes do modelo + o modelo)."""
    if not HARDWARE.search(titulo):
        return None
    palavras = titulo.split()
    alvo = None
    m = GPU.search(titulo)
    if m:
        return re.sub(r"\s+", " ", m.group(0).lower())
    for i, w in enumerate(palavras):
        if TOKEN.fullmatch(w.strip(".,;()")) and not RUIDO.match(w.strip(".,;()")):
            alvo = i
            break
    if alvo is None:
        return None
    ini = max(0, alvo - 3)
    q = " ".join(p.strip(".,;()").lower() for p in palavras[ini:alvo + 1])
    return q if len(q) >= 7 else None


def atualizar() -> list[str]:
    canais = [c.strip() for c in settings.tg_channels.split(",") if c.strip()]
    por_consulta: dict[str, set[str]] = {}
    for c in canais:
        try:
            for t in _titulos(c):
                q = _consulta(t)
                if q:
                    por_consulta.setdefault(q, set()).add(c)
        except Exception as e:  # noqa: BLE001
            log.warning("trending_canal_falhou", canal=c, error=str(e)[:100])
        time.sleep(1.0)
    # modelo em 2+ canais primeiro; depois os de 1 canal
    ordem = sorted(por_consulta.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    lista = [q for q, canais_ in ordem if len(canais_) >= 2][:10] + [q for q, canais_ in ordem if len(canais_) == 1][:6]
    ARQ.write_text(json.dumps({"quando": time.time(), "consultas": lista}, ensure_ascii=False), encoding="utf-8")
    log.info("trending_atualizado", total=len(lista), exemplos=lista[:5])
    return lista


def consultas() -> list[str]:
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        if time.time() - d.get("quando", 0) < VALIDADE_S:
            return d.get("consultas", [])
    except (OSError, ValueError):
        pass
    return atualizar()


def proximas(n: int) -> list[str]:
    """Próximas n consultas em rodízio (cada ciclo de coleta usa as seguintes)."""
    lista = consultas()
    if not lista or n <= 0:
        return []
    try:
        i = int(IDX.read_text()) % len(lista)
    except (OSError, ValueError):
        i = 0
    n = min(n, len(lista))
    IDX.write_text(str((i + n) % len(lista)))
    return [lista[(i + j) % len(lista)] for j in range(n)]
