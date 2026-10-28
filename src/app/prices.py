"""Tabela de preços da loja (carrossel) — editável pelo WhatsApp do dono, sem precisar do Claude.

Preços em data/prices.json. Comandos (conversa consigo mesmo):
  `ctl preco limpeza notebook 180`  -> altera o valor e gera a PRÉVIA da tabela (data/service_post)
  `ctl tabela`                      -> só gera a prévia com os valores atuais
  `ctl aprovar`                     -> publica (Instagram + Página) — mesmo fluxo do post de serviço
O dono fixa o post novo no perfil à mão (a API não permite fixar).
"""
import json
import re
import shutil
import unicodedata

from PIL import ImageDraw  # noqa: F401 (usado via _base)

from app.config import DATA_DIR
from app.content import PENDING, _base, _cta_slide, _jpeg, _send_owner, _text_slide
from app.social_art import MUTED, TEXT, _font

W = 1080
FILE = DATA_DIR / "prices.json"
DEFAULT = {
    "LIMPEZA": [
        ["Notebook", "Limpeza interna + troca de pasta térmica", "R$ 150"],
        ["Desktop", "Limpeza interna + troca de pasta térmica", "R$ 200"],
        ["Desktop Premium", "Limpeza + pasta térmica + thermal pads da GPU", "R$ 300"],
        ["Console", "PS4 • PS5 • Xbox — limpeza + troca de pasta térmica", "R$ 250"],
    ],
    "SOFTWARE E UPGRADE": [
        ["Formatação", "Windows + drivers + programas básicos", "R$ 150"],
        ["Formatação + backup", "Formatação + cópia dos seus arquivos", "R$ 200"],
        ["Otimização", "Remoção de vírus + ajustes de desempenho", "R$ 100"],
        ["Troca de peças", "Instalação da peça + LIMPEZA INCLUSA", "R$ 150"],
        ["Montagem de PC", "Montagem + cable management + testes", "R$ 400"],
    ],
    "CONDIÇÕES": [
        ["Orçamento", "Grátis se fechar o serviço", "R$ 50"],
        ["Atendimento em domicílio", "São Paulo — Zona Sul e região", "+ R$ 50"],
        ["Garantia", "Em todos os serviços", "90 dias"],
        ["Nota fiscal", "Emitimos para todos os serviços", "✓"],
        ["Prazo de entrega", "Prazo garantido e segurança", "até 48h"],
    ],
}
CAPTION = ("💰 Tabela de serviços TechHammer — preço justo e transparente!\n\n"
           "🔧 Limpeza (sempre com troca de pasta térmica), formatação, troca de peças e montagem\n"
           "🚗 Atendemos em domicílio em SP Zona Sul e região\n"
           "✅ Garantia de 90 dias + nota fiscal\n"
           "⏱️ Serviços entregues em até 48h\n\n"
           "📩 Chama no direct ou no WhatsApp pra agendar!\n\n"
           "#manutençãodecomputadores #saopaulo #zonasul #pcgamer #techhammer")


def load() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return DEFAULT


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def _table(title: str, rows: list, note: str | None = None) -> bytes:
    im, d, accent = _base()
    d.text((W / 2, 230), title, font=_font(58), fill=TEXT, anchor="mm")
    d.line((W / 2 - 40, 290, W / 2 + 40, 290), fill=accent, width=4)
    y = 370
    for name, desc, price in rows:
        d.text((90, y), name, font=_font(40), fill=TEXT, anchor="lm")
        d.text((990, y), price, font=_font(42), fill=accent, anchor="rm")
        if desc:
            d.text((90, y + 50), desc, font=_font(28, "regular"), fill=MUTED, anchor="lm")
        y += 150
        d.line((90, y - 45, 990, y - 45), fill=(40, 40, 46), width=2)
    if note:
        d.text((W / 2, 1250), note, font=_font(28, "regular"), fill=MUTED, anchor="mm")
    return _jpeg(im)


def preview() -> str:
    p = load()
    slides = [_text_slide("Tabela de serviços", kicker="TechHammer • São Paulo Zona Sul", big=True, footer="arraste →")]
    for title, rows in p.items():
        slides.append(_table(title, rows, "Valores de mão de obra. Peças à parte." if "UPGRADE" in title else None))
    slides.append(_cta_slide())
    shutil.rmtree(PENDING, ignore_errors=True)
    PENDING.mkdir(parents=True)
    for i, s in enumerate(slides):
        (PENDING / f"{i:02d}.jpg").write_bytes(s)
    (PENDING / "caption.txt").write_text(CAPTION)
    for i, s in enumerate(slides):
        _send_owner("👀 PRÉVIA da tabela de preços" if i == 0 else "", s)
    return ("✅ Prévia da tabela salva em data/service_post. `ctl aprovar` publica (depois fixe no perfil e desafixe a antiga). "
            "`ctl cancelar` descarta.")


def set_price(text: str) -> str:
    """'limpeza notebook 180' -> procura o serviço pelo nome e troca o valor."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(reais)?\s*$", text.strip())
    if not m:
        return "Diga o serviço e o valor. Ex.: `ctl preco limpeza notebook 180`"
    value = m.group(1).replace(".", ",")
    words = [w for w in _norm(text[:m.start()]).replace("limpeza", "").split() if len(w) > 2]
    p = load()
    best, hits = None, 0
    for rows in p.values():
        for row in rows:
            name = _norm(row[0] + " " + row[1])
            h = sum(w in name for w in words)
            if h > hits:
                best, hits = row, h
    if not best:
        names = ", ".join(r[0] for rows in p.values() for r in rows)
        return f"Não achei esse serviço. Opções: {names}"
    old = best[2]
    best[2] = f"{'+ ' if best[2].startswith('+') else ''}R$ {value}"
    FILE.write_text(json.dumps(p, ensure_ascii=False, indent=1))
    return f"💰 {best[0]}: {old} → {best[2]}\n" + preview()
