"""IA local (Ollama, qwen3:4b): título curto do post. Se falhar, usa o título original."""
import json

import httpx

from app import gpu
from app.config import settings
from app.log import log

PROMPT = """Você edita posts de um canal brasileiro de promoções.
Produto: "{title}"
Responda SÓ em JSON: {{"titulo": "título curto e chamativo EM PORTUGUÊS DO BRASIL (traduza se vier em outra língua), máx 60 caracteres, mantenha marca e modelo, NÃO inclua preço, sem inventar nada"}}"""


ENCHIMENTO = ("original", "novo", "nova", "lançamento", "envio imediato", "pronta entrega", "frete grátis", "promoção", "oferta",
              "100%", "garantia", "com nf", "nota fiscal", "lacrado", "brinde", "para pc", "de alta qualidade", "alta qualidade",
              "novo modelo", "2024", "2025", "2026", "hot", "new")


def rule_title(title: str, limit: int = 60) -> str:
    """Título curto SEM IA (robô leve): regras em app/titles.py."""
    from app.titles import limpar
    return limpar(title, limit)


def short_title(title: str) -> str:
    if not settings.ai_enabled:
        return rule_title(title)
    try:
        r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=180, json={
            "model": settings.ai_model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0.3, "num_predict": 80, "num_gpu": settings.bot_ai_num_gpu},
            "messages": [{"role": "user", "content": PROMPT.format(title=title)}],
        })
        new = json.loads(r.json()["message"]["content"]).get("titulo", "").strip()
        return new if 8 <= len(new) <= 90 else title
    except Exception as e:
        log.warning("ai_failed", error=str(e)[:200])
        return title


JUDGE_PROMPT = """Você é curador RIGOROSO de um canal brasileiro de promoções focado em TECNOLOGIA.
Fora de tecnologia só entra oferta ABSURDA, e a regra é: na dúvida, RECUSE.
Aprove SÓ se TODOS forem verdade:
1) marca famosa no Brasil (ex.: Nike, Adidas, Samsung, Philips, Mondial, Electrolux, Pampers, Lego, Natura, Tramontina);
2) produto que muita gente deseja ou compra sempre;
3) preço final claramente baixo para esse produto.
Exemplos:
- "Chaleira com assobio genérica" R$ 32 -68% -> false (sem marca famosa)
- "Kit 2 refletor LED 200w" R$ 31 -61% -> false (genérico)
- "Air Fryer Mondial 4L" R$ 199 -60% -> true
- "Tênis Nike Revolution 7" R$ 149 -62% -> true
- "Fralda Pampers Confort Sec G 60un" R$ 49 -65% -> true
Oferta: "{title}" por R$ {price:.2f} (antes R$ {old:.2f}, -{pct}%).
Responda SÓ em JSON: {{"marca_famosa": true/false, "publicar": true/false, "motivo": "até 8 palavras"}}"""


def judge_offer(title: str, price: float, old: float | None, pct: int) -> tuple[bool, str]:
    """IA decide se uma oferta FORA de tecnologia é boa o bastante para o canal. Na dúvida, não publica."""
    if not settings.ai_enabled:
        return False, "IA desligada"
    try:
        r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=180, json={
            "model": settings.ai_model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0, "num_predict": 60, "num_gpu": settings.bot_ai_num_gpu},
            "messages": [{"role": "user", "content": JUDGE_PROMPT.format(title=title, price=price, old=old or price, pct=pct)}],
        })
        d = json.loads(r.json()["message"]["content"])
        return bool(d.get("publicar")) and bool(d.get("marca_famosa")), str(d.get("motivo", ""))[:80]
    except Exception as e:
        log.warning("ai_judge_failed", error=str(e)[:200])
        return False, "IA indisponível"


ALI_JUDGE_PROMPT = """Você é curador de um canal brasileiro de ofertas de TECNOLOGIA (PC, periféricos, games, celular).
Produto do AliExpress: "{title}" por R$ {price:.2f} (antes R$ {old:.2f}, -{pct}%).
Aprove SÓ se for um produto de tecnologia COMPLETO e desejável por quem monta/usa PC ou joga
(ex.: SSD, memória, placa, teclado, mouse, headset, controle, monitor, fone, gabinete, cooler, mini PC, celular).
Recuse: peça avulsa ou consumível (switches, keycaps soltos, cabos/adaptadores simples, parafusos), acessório genérico,
produto fora de tecnologia, kit infantil, decoração, e qualquer coisa estranha ou suspeita.
DESCONFIE de golpe e recuse: ficha técnica irreal para o preço (ex.: notebook i9 32GB 2TB por R$ 1.500; celular 16GB+1TB por R$ 700),
capacidade falsa (SSD/pendrive/cartão de 1-2TB por poucos reais), marca desconhecida ou genérica em item caro, título cheio de
"BIG SALE", "2026", "NEW", "free gift", produto usado, recondicionado ou "tray".
Responda SÓ em JSON: {{"publicar": true/false, "motivo": "até 8 palavras"}}"""


def judge_ali(title: str, price: float, old: float | None, pct: int) -> tuple[bool, str]:
    """Curadoria das ofertas do AliExpress (muito ruído na busca). Na dúvida, não publica."""
    if not settings.ai_enabled:  # robô leve: valem a categoria de tecnologia da API, vendas mínimas e o anti-golpe (alicheck)
        return True, "regras (sem IA)"
    try:
        r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=180, json={
            "model": settings.ai_model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0, "num_predict": 60, "num_gpu": settings.bot_ai_num_gpu},
            "messages": [{"role": "user", "content": ALI_JUDGE_PROMPT.format(title=title, price=price, old=old or price, pct=pct)}],
        })
        d = json.loads(r.json()["message"]["content"])
        return bool(d.get("publicar")), str(d.get("motivo", ""))[:80]
    except Exception as e:
        log.warning("ai_judge_failed", error=str(e)[:200])
        return False, "IA indisponível"
