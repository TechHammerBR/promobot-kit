"""ESTÚDIO: posts de NOVIDADES de tecnologia/IA para o feed, escritos pela IA do PC do dono (14/10/2026).

Divisão (dono: "100% automatizado, sem depender de pedir", "não gastar o PC por muito tempo"):
- Wyse (aqui): lê os sites de notícia, escolhe os assuntos EM ALTA (o mesmo assunto em vários sites), baixa o texto da matéria e
  deixa uma TAREFA em /srv/cache/estudio/pendentes. Quando a resposta volta (resultados/), desenha o carrossel e guarda no
  ESTOQUE; publica nos dias marcados (ESTUDIO_DIAS) tirando do estoque.
- PC do dono (E:\\TechHammer-Estudio\\estudio.ps1, agendado no Windows): quando o PC está ligado, busca as tarefas pelo SSH, roda a
  IA local (Ollama, gemma3:12b na RTX 4080, ~20 s por post) e devolve. Sem tarefa = não usa a placa.
Sem PC por dias: o estoque cobre; acabando, o feed fica só com dicas/jogos (nada quebra).
Teste: `./venv/bin/python -m app.estudio assuntos` (lista o que está em alta) | `planejar` | `receber` | `estoque`.
"""
import html
import io
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from zoneinfo import ZoneInfo

import httpx
from selectolax.parser import HTMLParser

from app.collectors.base import USER_AGENT
from app.config import DATA_DIR, settings
from app.log import log

BASE = Path("/srv/cache/estudio")
PEND, RES, EST = BASE / "pendentes", BASE / "resultados", BASE / "estoque"
USADOS = DATA_DIR / "estudio_usados.json"
FEEDS = {
    "Tecnoblog": "https://tecnoblog.net/feed/",
    "Canaltech": "https://canaltech.com.br/rss/",
    "Olhar Digital": "https://olhardigital.com.br/feed/",
    "TecMundo": "https://rss.tecmundo.com.br/feed",
    "Adrenaline": "https://www.adrenaline.com.br/feed/",
    "Hardware.com.br": "https://www.hardware.com.br/feed/",
    "TechTudo": "https://www.techtudo.com.br/rss/techtudo/",
    "Showmetech": "https://showmetech.com.br/feed/",
    "Tudocelular": "https://www.tudocelular.com/feed/",
    "Meio Bit": "https://meiobit.com/feed/",
    "Mundo Conectado": "https://mundoconectado.com.br/feed",
}
# assuntos que combinam com o perfil (tecnologia, hardware, games, IA, segurança); o resto pesa menos
FOCO = re.compile(r"\bia\b|intelig[eê]ncia artificial|chatgpt|openai|gemini|claude|nvidia|\bamd\b|intel|\brtx\b|placa de v[ií]deo|"
                  r"processador|\bssd\b|windows|linux|playstation|\bps5\b|xbox|nintendo|switch|steam|\bgpu\b|chip|hacker|"
                  r"vazamento|seguran[cç]a|engenharia reversa|emulador|console|notebook|smartphone|iphone|android|samsung|apple|"
r"whatsapp|instagram|tiktok|youtube|netflix|spotify|starlink|tesla|\b5g\b|anatel|wi-?fi|roteador|drone|rob[oô]|"
r"streaming|gta|pok[eé]mon|zelda|fortnite|minecraft|roblox|meta\b|microsoft|google|amazon|xiaomi|motorola|"
r"smartwatch|fone|tablet|monitor|teclado|mouse|kernel|vulnerabilidade|ciberataque|aplicativo|bateria|carregador", re.I)
FORA = re.compile(r"r\$ ?\d|sai por|custa s[oó]|por menos de|pre[cç]o baixo|\bcupom|\boferta|promo[cç][aã]o|desconto|black friday|review:|an[aá]lise:|patrocinado|hor[oó]scopo|"
                  r"\bbbb\b|futebol|novela|loteria|pela metade|menor (pre[cç]o|valor)|est[aá] por|queda de [0-9]+|mercado livre|na amazon|mega-sena|bolsonaro|lula|elei[cç]|\bstf\b|moraes|governo|pol[ií]tic|presidente|deputad|senad|ministro|justi[cç]a eleitoral", re.I)
EDITORIAS = [  # ordem = prioridade do perfil (dono: novidades de tecnologia e IA, não só jogos)
    ("ia", re.compile(r"\bias?\b|intelig[eê]ncia artificial|chatgpt|openai|gemini|claude|copilot|llm|deepseek|agente", re.I)),
    ("hardware", re.compile(r"nvidia|\bamd\b|intel|\brtx\b|\brx ?\d|placa de v[ií]deo|processador|\bcpu\b|\bgpu\b|chip|\bssd\b|"
                            r"mem[oó]ria|\bram\b|placa-m[aã]e|notebook|\bpc\b|computador|tsmc|qualcomm|snapdragon", re.I)),
    ("seguranca", re.compile(r"hacker|vazamento|golpe|seguran[cç]a|ataque|malware|v[ií]rus|senha|ransomware|engenharia reversa|"
                             r"privacidade|falha", re.I)),
    ("celular", re.compile(r"smartphone|celular|iphone|android|samsung|galaxy|xiaomi|motorola|pixel", re.I)),
    ("games", re.compile(r"jogo|game|playstation|\bps5\b|xbox|nintendo|switch|steam|epic|gta|console", re.I)),
    ("software", re.compile(r"windows|linux|macos|microsoft|google|apple|app\b|aplicativo|atualiza[cç][aã]o|navegador", re.I)),
]
PARADAS = set("a o e de da do das dos em no na nos nas um uma para por com que se sua seu como mais ao aos à às é foi vai ser "
              "tem são após sobre entre até sem pelo pela pelos pelas já não the of and to in for on with is new novo nova "
              "agora pode podem veja confira saiba entenda".split())
MODELO = "gemma3:12b"


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _palavras(titulo: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", _sem_acento(titulo)) if w not in PARADAS}


def noticias(horas: int = 48) -> list[dict]:
    corte = datetime.now(timezone.utc) - timedelta(hours=horas)
    out = []
    for fonte, url in FEEDS.items():
        try:
            xml = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True).text
        except httpx.HTTPError as e:
            log.warning("estudio_feed_falhou", fonte=fonte, error=str(e)[:80])
            continue
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
            def tag(t):
                m = re.search(rf"<{t}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>", item, re.S)
                return html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""
            try:
                quando = parsedate_to_datetime(tag("pubDate"))
            except (TypeError, ValueError):
                continue
            if quando.tzinfo is None:  # "-0000" e datas sem fuso: tratar como UTC
                quando = quando.replace(tzinfo=timezone.utc)
            titulo = tag("title")
            if quando < corte or not titulo or FORA.search(titulo):
                continue
            out.append({"fonte": fonte, "titulo": titulo, "url": tag("link"), "resumo": tag("description")[:700],
                        "quando": quando.isoformat()})
    return out


_TENDENCIAS: dict = {"t": 0.0, "termos": []}


def tendencias() -> list[set[str]]:
    """Buscas em alta no Google Brasil (RSS público, atualizado várias vezes ao dia). Cada termo vira um conjunto de palavras."""
    if time.time() - _TENDENCIAS["t"] < 3600 and _TENDENCIAS["termos"]:
        return _TENDENCIAS["termos"]
    termos: list[set[str]] = []
    try:
        xml = httpx.get("https://trends.google.com/trending/rss?geo=BR", headers={"User-Agent": USER_AGENT}, timeout=20).text
        for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
            m = re.search(r"<title>(.*?)</title>", it, re.S)
            if m:
                w = _palavras(html.unescape(m.group(1)))
                if w:
                    termos.append(w)
    except httpx.HTTPError as e:
        log.warning("estudio_tendencias_falhou", error=str(e)[:80])
    _TENDENCIAS.update(t=time.time(), termos=termos)
    return termos


def assuntos(n: int = 6) -> list[dict]:
    """Agrupa notícias parecidas (>= 2 palavras importantes em comum). Em alta = mais SITES diferentes falando + tema do perfil."""
    itens = noticias()
    for it in itens:
        it["p"] = _palavras(it["titulo"])
    grupos: list[list[dict]] = []
    for it in sorted(itens, key=lambda x: x["quando"], reverse=True):
        for g in grupos:
            if len(it["p"] & g[0]["p"]) >= 2:
                g.append(it)
                break
        else:
            grupos.append([it])
    usados = _usados()
    ranking = []
    for g in grupos:
        fontes = {x["fonte"] for x in g}
        foco = sum(bool(FOCO.search(x["titulo"])) for x in g)
        chave = " ".join(sorted(Counter(w for x in g for w in x["p"]).most_common(4)[i][0] for i in range(min(4, len(g[0]["p"])))))
        if not foco or any(len(set(chave.split()) & set(u.split())) >= 3 for u in usados):
            continue
        texto = g[0]["titulo"]  # editoria pelo título principal (o grupo mistura palavras de outras matérias)
        editoria = next((nome for nome, rx in EDITORIAS if rx.search(texto)), "outros")
        recente = any(datetime.fromisoformat(x["quando"]) > datetime.now(timezone.utc) - timedelta(hours=10) for x in g)
        todas = set().union(*(x["p"] for x in g))
        em_alta_google = any(t and t <= todas for t in tendencias())  # termo em alta no Google aparece nas manchetes
        nota = len(fontes) * 3 + foco + (3 if recente else 0) + (8 if em_alta_google else 0)
        ranking.append({"chave": chave, "nota": nota, "fontes": sorted(fontes), "noticias": g[:4], "google": em_alta_google,
                        "editoria": editoria})
    # só entra o que tem 2+ sites falando (ou nota alta): "em alta" de verdade
    ranking = [r for r in ranking if len(r["fontes"]) >= 2 or r["nota"] >= 12]
    escolhidos: list[dict] = []
    while ranking and len(escolhidos) < n:
        por_ed = Counter(x["editoria"] for x in escolhidos)
        melhor = max(ranking, key=lambda r: r["nota"] - 4 * por_ed[r["editoria"]])  # variedade leve, sem perder o que está em alta
        escolhidos.append(melhor)
        ranking.remove(melhor)
    return escolhidos


def _texto_materia(url: str, limite: int = 3500) -> str:
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"}, timeout=20, follow_redirects=True)
    except httpx.HTTPError:
        return ""
    if r.status_code != 200:
        return ""
    arv = HTMLParser(r.text)
    candidatos = [n for n in (arv.css("article") + [arv.css_first("main"), arv.body]) if n is not None]
    corpo = max(candidatos, key=lambda n: sum(len(x.text(strip=True)) for x in n.css("p") if len(x.text(strip=True)) > 60), default=None)
    paras = [_limpa(p.text(separator=" ", strip=True)) for p in (corpo.css("p") if corpo else [])]
    texto = " ".join(p for p in paras if len(p) > 60)
    return texto[:limite]


def _usados() -> list[str]:
    try:
        return json.loads(USADOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _marcar(chave: str) -> None:
    u = (_usados() + [chave])[-200:]
    USADOS.write_text(json.dumps(u, ensure_ascii=False), encoding="utf-8")


PROMPT = """Você escreve para o Instagram da TechHammer, loja de manutenção e montagem de PCs em São Paulo que comenta as
novidades do mundo da tecnologia (hardware, games, IA, segurança). Público: brasileiros que curtem tecnologia, nem todos técnicos.

Assunto em alta: "{tema}"
Textos das matérias (fontes: {fontes}):
---
{materias}
---

Crie um CARROSSEL explicativo sobre esse assunto. Regras OBRIGATÓRIAS:
- Português do Brasil, frases curtas, tom próximo e confiável, sem exagero e sem sensacionalismo.
- Use SOMENTE fatos que estão nos textos acima. NÃO invente números, datas, preços, nomes ou opiniões de especialistas.
  Se um detalhe não estiver nos textos, não coloque.
- Explique o que aconteceu, por que importa e o que muda para quem usa PC, console ou celular.
- Não copie frases inteiras das matérias: reescreva com suas palavras.
- NÃO use emoji no título nem nos slides (emoji só na legenda).
Responda SÓ com JSON neste formato:
{{"titulo": "título da capa, chamativo, até 8 palavras",
  "kicker": "chapéu curto, até 4 palavras (ex.: Inteligência artificial)",
  "slides": [{{"titulo": "até 6 palavras", "texto": "até 28 palavras"}}, ... de 4 a 5 itens],
  "legenda": "legenda de 2 a 3 frases com 1 ou 2 emojis, terminando com uma pergunta para gerar comentários",
  "hashtags": ["#exemplo", ... 4 a 6 hashtags em português]}}"""


def planejar(alvo: int = None) -> int:
    """Cria tarefas para o PC até estoque + pendentes chegarem ao alvo. Retorna quantas criou."""
    for p in (PEND, RES, EST):
        p.mkdir(parents=True, exist_ok=True)
    alvo = alvo or settings.estudio_estoque_alvo
    falta = alvo - len(list(EST.glob("*/meta.json"))) - len(list(PEND.glob("*.json")))
    if falta <= 0:
        return 0
    feitos = 0
    pendentes_chaves = {json.loads(p.read_text(encoding="utf-8"))["chave"] for p in PEND.glob("*.json")}
    for a in assuntos(n=falta + 3):
        if feitos >= falta or a["chave"] in pendentes_chaves:
            continue
        materias = []
        for nt in a["noticias"][:2]:
            t = _texto_materia(nt["url"]) or nt["resumo"]
            if t:
                materias.append(f"[{nt['fonte']}] {nt['titulo']}\n{t}")
        if not materias or sum(len(m) for m in materias) < 600:
            continue
        tid = datetime.now().strftime("%Y%m%d%H%M%S") + f"{feitos}"
        tema = a["noticias"][0]["titulo"]
        tarefa = {"id": tid, "tipo": "noticia", "chave": a["chave"], "tema": tema, "fontes": a["fontes"],
                  "links": [n["url"] for n in a["noticias"][:3]], "modelo": MODELO,
                  "prompt": PROMPT.format(tema=tema, fontes=", ".join(a["fontes"]), materias="\n\n".join(materias))}
        (PEND / f"{tid}.json").write_text(json.dumps(tarefa, ensure_ascii=False), encoding="utf-8")
        feitos += 1
        log.info("estudio_tarefa", id=tid, tema=tema[:80], fontes=a["fontes"])
    return feitos


_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u2B00-\u2BFF]")


def _sem_emoji(t: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI.sub("", t or "")).strip()


def _normalizar(r: dict) -> dict:
    """O modelo às vezes separa título e texto em itens seguidos ({"titulo"}, {"texto"}): junta os pares."""
    if not isinstance(r, dict) or not isinstance(r.get("slides"), list):
        return r
    juntos, pend = [], None
    for s in r["slides"]:
        if not isinstance(s, dict):
            continue
        t, x = _sem_emoji(s.get("titulo")), _sem_emoji(s.get("texto"))
        if t and x:
            juntos.append({"titulo": t, "texto": x})
            pend = None
        elif t:
            pend = t
        elif x and pend:
            juntos.append({"titulo": pend, "texto": x})
            pend = None
    r["slides"] = juntos
    r["titulo"], r["kicker"] = _sem_emoji(r.get("titulo")), _sem_emoji(r.get("kicker"))
    return r


def _trechos(texto: str, n: int = 8) -> set[tuple]:
    w = re.findall(r"\w+", _sem_acento(texto))
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def copiou(r: dict, fontes: str) -> str | None:
    """Trecho de 8+ palavras igual ao das matérias = cópia. Retorna o trecho (para o registro) ou None."""
    base = _trechos(fontes)
    gerado = " ".join([r.get("titulo", "")] + [f"{x['titulo']} {x['texto']}" for x in r.get("slides", [])] + [r.get("legenda", "")])
    igual = _trechos(gerado) & base
    return " ".join(next(iter(igual))) if igual else None


def _valido(r: dict) -> str | None:
    if not isinstance(r, dict) or not r.get("titulo") or not isinstance(r.get("slides"), list):
        return "formato"
    if not 3 <= len(r["slides"]) <= 6:
        return "número de slides"
    for s in r["slides"]:
        if not isinstance(s, dict) or not s.get("titulo") or not s.get("texto") or len(s["texto"]) > 260:
            return "slide inválido"
    if re.search(r"como (uma )?ia|modelo de linguagem|não tenho acesso", json.dumps(r, ensure_ascii=False), re.I):
        return "texto de IA"
    return None


def receber() -> int:
    """Pega as respostas que o PC devolveu, desenha o carrossel e põe no estoque."""
    from app.content import _cta_slide, _text_slide
    from app.templates import chamada_grupos
    n = 0
    for arq in sorted(RES.glob("*.json")):
        try:
            res = json.loads(arq.read_text(encoding="utf-8"))
            tarefa = json.loads((PEND / arq.name).read_text(encoding="utf-8")) if (PEND / arq.name).exists() else res.get("tarefa", {})
            r = res.get("resposta") if isinstance(res.get("resposta"), dict) else json.loads(res.get("resposta") or "{}")
        except (OSError, ValueError) as e:
            log.warning("estudio_resultado_ruim", arquivo=arq.name, error=str(e)[:100])
            arq.unlink(missing_ok=True)
            continue
        r = _normalizar(r)
        motivo = _valido(r)
        if not motivo:
            trecho = copiou(r, tarefa.get("prompt", ""))
            if trecho:
                motivo = f"trecho copiado da matéria: {trecho}"
        if motivo:
            log.warning("estudio_rejeitado", id=arq.stem, motivo=motivo)
            (BASE / "rejeitados").mkdir(exist_ok=True)
            arq.replace(BASE / "rejeitados" / arq.name)  # guarda para diagnóstico
            (PEND / arq.name).unlink(missing_ok=True)  # o planejar cria outra tarefa com outro assunto
            continue
        total = len(r["slides"])
        fontes = ", ".join(tarefa.get("fontes", []))
        slides = [_text_slide(r["titulo"], kicker=r.get("kicker") or "Tecnologia", big=True, footer="arraste →")]
        slides += [_text_slide(s["titulo"], s["texto"], kicker=f"{k + 1}/{total}") for k, s in enumerate(r["slides"])]
        slides.append(_text_slide("Fique por dentro", f"Fontes: {fontes}. Siga a @techhammer.br para mais novidades de tecnologia.",
                                  kicker="TechHammer"))
        slides.append(_cta_slide())
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in (r.get("hashtags") or [])[:6])
        legenda = f"{r.get('legenda', '').strip()}\n\n📰 Fontes: {fontes}\n🔧 TechHammer: manutenção, limpeza e montagem de PCs."
        ig = f"{legenda}\n{chamada_grupos(False)}\n\n{tags} #techhammer"
        fb = f"{legenda}\n🔗 " + "\n🔗 ".join(tarefa.get("links", [])) + f"\n\n{chamada_grupos(True)}"
        pasta = EST / arq.stem
        pasta.mkdir(parents=True, exist_ok=True)
        for i, sl in enumerate(slides):
            (pasta / f"{i:02d}.jpg").write_bytes(sl)
        (pasta / "meta.json").write_text(json.dumps({"tema": tarefa.get("tema", ""), "chave": tarefa.get("chave", ""),
                                                     "ig": ig, "fb": fb, "criado": time.time()}, ensure_ascii=False), encoding="utf-8")
        arq.unlink(missing_ok=True)
        (PEND / arq.name).unlink(missing_ok=True)
        if tarefa.get("chave"):
            _marcar(tarefa["chave"])
        log.info("estudio_estoque", id=arq.stem, tema=tarefa.get("tema", "")[:80])
        n += 1
    return n


ROTULO_EDITORIA = {"ia": "Inteligência artificial", "hardware": "Hardware", "seguranca": "Segurança", "celular": "Celulares",
                   "software": "Software", "games": "Games", "outros": "Tecnologia"}


def _limpa(texto: str) -> str:
    """Tira espaços duplos e o espaço antes de vírgula/ponto que sobra quando o HTML do feed é convertido em texto."""
    texto = re.sub(r"\s+", " ", texto or "").strip()
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    return re.sub(r"\s*(Leia mais|Compare|Confira|O post .* apareceu primeiro.*|The post .*)[.!]?$", "", texto, flags=re.I).strip()


def _frase(texto: str, limite: int) -> str:
    """Só frases INTEIRAS (terminadas em ponto) que cabem no limite; frase cortada no meio fica de fora."""
    out = ""
    for fr in re.split(r"(?<=[.!?])\s+", _limpa(texto)):
        if not re.search(r"[.!?]$", fr) or len(out) + len(fr) + 1 > limite:
            break
        out = f"{out} {fr}".strip()
    return out


HASHTAGS = {"ia": "#inteligenciaartificial #ia #chatgpt", "hardware": "#hardware #pcgamer #computador",
            "seguranca": "#segurancadigital #privacidade #ciberseguranca", "celular": "#smartphone #celular #android #iphone",
            "software": "#software #windows #apps", "games": "#games #gamer #jogos", "outros": "#tecnologia"}


def _data_br(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m")
    except (TypeError, ValueError):
        return datetime.now().strftime("%d/%m")


def _blocos(texto: str, limite: int = 150, maximo: int = 3) -> list[str]:
    """Junta frases inteiras em blocos de até `limite` letras (um bloco por cartão)."""
    blocos, atual = [], ""
    for fr in re.split(r"(?<=[.!?])\s+", _limpa(texto)):
        if not fr:
            continue
        if atual and len(atual) + len(fr) + 1 > limite:
            blocos.append(atual)
            atual = ""
        atual = f"{atual} {fr}".strip()
    if atual:
        blocos.append(atual)
    return [b for b in blocos if len(b) >= 40][:maximo]


_RUIDO = re.compile(r"leia (tamb[eé]m|mais)|veja (tamb[eé]m|mais)|assine|newsletter|cookies|clique|siga (o|a)|compartilh|"
                    r"foto:|imagem:|cr[eé]dito|publicidade|direitos reservados|receba|inscreva|canal do|grupo do|\bcupom\b|"
                    r"afiliad|comiss[aã]o|comprar (pelo|no)|ofertas? (de|do)", re.I)
_FATO = re.compile(r"[0-9]")
_UNID = re.compile(r"R\$|US\$|%|\bGB\b|\bTB\b|\bHz\b|\bMP\b|\bW\b|\bnm\b|\bpolegadas?\b|\bmil\b|milh[oõ]es|bilh[oõ]es", re.I)
_DATA = re.compile(r"janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|\b20[0-9]{2}\b|"
                   r"segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|amanh[aã]|hoje", re.I)


def _meta_descricao(url: str) -> str:
    """Resumo que o próprio site escreve para compartilhamento (og:description / description)."""
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"}, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return ""
        arv = HTMLParser(r.text)
        for sel in ('meta[property="og:description"]', 'meta[name="description"]'):
            m = arv.css_first(sel)
            if m and (m.attributes.get("content") or "").strip():
                return html.unescape(m.attributes["content"]).strip()
    except httpx.HTTPError:
        pass
    return ""


def _imagem_materia(url: str) -> bytes | None:
    """Imagem de compartilhamento (og:image / twitter:image) da matéria; só se for grande e horizontal o bastante para a capa."""
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"}, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return None
        arv = HTMLParser(r.text)
        for sel in ('meta[property="og:image"]', 'meta[name="twitter:image"]'):
            m = arv.css_first(sel)
            link = (m.attributes.get("content") or "").strip() if m else ""
            if not link.startswith("http"):
                continue
            img = httpx.get(link, headers={"User-Agent": USER_AGENT}, timeout=25, follow_redirects=True)
            if img.status_code == 200:
                from PIL import Image
                im = Image.open(io.BytesIO(img.content))
                if im.size[0] >= 700 and im.size[0] >= im.size[1] * 1.1:
                    return img.content
    except Exception:  # noqa: BLE001
        pass
    return None


def _fatos(url: str, ja: list[str], quantos: int = 2) -> list[str]:
    """Frases da matéria com cara de FATO (números, preço, data, marca), na ordem em que aparecem, sem repetir o que já temos."""
    corpo = _texto_materia(url, 6000)
    if not corpo:
        return []
    cand = []
    for pos, fr in enumerate(re.split(r"(?<=[.!?])\s+", _limpa(corpo))):
        if not 60 <= len(fr) <= 220 or not re.search(r"[.!?]$", fr) or _RUIDO.search(fr):
            continue
        nota = 3 * bool(_FATO.search(fr)) + 2 * bool(_UNID.search(fr)) + 2 * bool(_DATA.search(fr)) \
            + min(3, len(re.findall(r"(?<!^)(?<![.!?] )\b[A-Z][A-Za-z0-9]{2,}", fr))) - (1 if pos > 25 else 0)
        cand.append((nota, pos, fr))
    escolhidos: list[tuple[int, int, str]] = []
    vistos = list(ja)
    for nota, pos, fr in sorted(cand, key=lambda c: -c[0]):  # do melhor para o pior; cada escolhido já conta como "dito"
        if len(escolhidos) >= quantos or nota < 3:
            break
        nums = set(re.findall(r"[0-9]+(?:[.,][0-9]+)*", fr))
        if nums and any(nums <= set(re.findall(r"[0-9]+(?:[.,][0-9]+)*", x)) for x in vistos):
            continue  # mesmo fato (mesmos números) com outras palavras
        base = _palavras(fr)
        if any(len(base & _palavras(x)) >= max(4, int(0.6 * len(base))) for x in vistos):
            continue  # frase quase igual a uma que já temos
        escolhidos.append((nota, pos, fr))
        vistos.append(fr)
    return [c[2] for c in sorted(escolhidos, key=lambda c: c[1])]


def montar_simples(a: dict, foto: bool | None = None) -> tuple[list[bytes], str, str] | None:
    """Versão SEM IA (dono, 14/10: "gosto do simples" e "traga mais informações"): capa + resumo do site + FATOS das matérias + fontes.
    Sempre com a fonte citada e os links na legenda. Não depende do PC do dono."""
    from app import noticia_art as art
    from app.content import _cta_slide
    from app.templates import chamada_grupos
    todas = a["noticias"]
    if not todas:
        return None
    capa = re.sub("[\U0001F1E6-\U0001F1FF]", "", todas[0]["titulo"]).strip()  # sem bandeiras de emoji
    mesmas = [todas[0]] + [n for n in todas[1:] if len(_palavras(n["titulo"]) & _palavras(capa)) >= 3]
    data = _data_br(todas[0].get("quando", ""))
    if len(todas[0].get("resumo", "")) < 60:
        todas[0]["resumo"] = _meta_descricao(todas[0]["url"])
    resumo = _frase(todas[0].get("resumo", ""), 600)
    if not resumo and todas[0].get("resumo"):  # uma frase só, comprida/cortada: corta na palavra
        resumo = _limpa(todas[0]["resumo"])[:300].rsplit(" ", 1)[0].rstrip(" ,;:…") + "…"
    cartoes: list[tuple[str, str]] = []
    ja = [capa, resumo]
    pontos: list[tuple[str, str]] = []
    for nt in mesmas[:3]:  # procura MAIS informação nas matérias de cada site
        for fr in _fatos(nt["url"], ja, quantos=2):
            ja.append(fr)
            pontos.append((nt["fonte"], fr))
    cortado = resumo.endswith("…")
    if cortado and len(pontos) >= 2:  # resumo do site vem cortado: os fatos da matéria contam melhor a história
        resumo = ""
    elif resumo and _sem_acento(resumo)[:40] != _sem_acento(capa)[:40]:
        for b in _blocos(resumo, limite=170, maximo=1) or ([resumo] if cortado else []):
            cartoes.append((f"via {todas[0]['fonte']}", b))
    for fonte_, fr in pontos:
        if len(cartoes) < 4:
            cartoes.append((f"via {fonte_}", fr))
    if len(cartoes) < 2:  # um fato sozinho é pouco: não vira post (o robô escolhe outro assunto)
        return None
    img, credito = None, ""
    if settings.estudio_foto_materia if foto is None else foto:
        for nt in mesmas[:3]:  # primeira matéria que tiver imagem boa
            img = _imagem_materia(nt["url"])
            if img:
                credito = nt["fonte"]
                break
    slides = [art.capa(capa, a["editoria"], todas[0]["fonte"], data, img, credito)]
    slides += [art.cartao(k + 1, len(cartoes), t, x, img) for k, (t, x) in enumerate(cartoes)]
    slides.append(art.fontes([(n["fonte"], n["titulo"].strip()[:170]) for n in mesmas], data))
    slides.append(_cta_slide("SEU PC ESTÁ", "EM DIA?", ["Atualização, limpeza e otimização", "Orçamento sem compromisso", "Atendemos na loja e em domicílio"], "CHAMA A GENTE"))
    fontes = ", ".join(sorted({n["fonte"] for n in mesmas}))
    nl = chr(10)
    corpo = f"📰 {capa}{nl}{nl}" + (f"{resumo}{nl}{nl}" if resumo else "")
    if pontos:
        corpo += "📌 Principais pontos:" + nl + nl.join(f"• {x}" for _, x in pontos[:5]) + nl + nl
    legenda = (f"{corpo}👉 Arraste para ver os detalhes e as fontes.{nl}{nl}🗞️ Fontes: {fontes}{nl}"
               f"🔧 TechHammer: manutenção, limpeza e montagem de PCs.")
    tags = f"{HASHTAGS.get(a['editoria'], HASHTAGS['outros'])} #tecnologia #novidades #techhammer"
    ig = f"{legenda}{nl}{chamada_grupos(False)}{nl}{nl}{tags}"
    fb = f"{legenda}{nl}🔗 " + f"{nl}🔗 ".join(n["url"] for n in mesmas[:3]) + f"{nl}{nl}{chamada_grupos(True)}"
    return slides, ig, fb


def _guardar(a: dict, sufixo: str = "s") -> bool:
    """Monta o post simples e põe no ESTOQUE (publicado depois por post_novidade). False se faltar texto."""
    r = montar_simples(a)
    if not r:
        return False
    slides, ig, fb = r
    EST.mkdir(parents=True, exist_ok=True)
    pasta = EST / (datetime.now().strftime("%Y%m%d%H%M%S%f") + sufixo)
    pasta.mkdir(parents=True, exist_ok=True)
    for i, sl in enumerate(slides):
        (pasta / f"{i:02d}.jpg").write_bytes(sl)
    (pasta / "meta.json").write_text(json.dumps({"tema": a["noticias"][0]["titulo"], "chave": a["chave"], "ig": ig, "fb": fb,
                                                 "criado": time.time()}, ensure_ascii=False), encoding="utf-8")
    _marcar(a["chave"])
    log.info("estudio_estoque_simples", tema=a["noticias"][0]["titulo"][:80])
    return True


def repor_simples(alvo: int | None = None) -> int:
    """Estoque sem PC e sem IA: monta direto do feed quando falta post pronto."""
    EST.mkdir(parents=True, exist_ok=True)
    falta = (alvo or settings.estudio_estoque_alvo) - len(list(EST.glob("*/meta.json")))
    feitos = 0
    for a in assuntos(n=max(falta, 0) + 4):
        if feitos >= falta:
            break
        feitos += _guardar(a)
    return feitos


def post_novidade() -> None:
    """Publica o post mais antigo do estoque (novidade velha demais é descartada: notícia perde a graça)."""
    from app.content import publish_carousel
    from app.social import enabled
    if not enabled():
        return
    if settings.estudio_simples:
        repor_simples()
    else:
        receber()
    for meta in sorted(EST.glob("*/meta.json")):
        m = json.loads(meta.read_text(encoding="utf-8"))
        if time.time() - m["criado"] > settings.estudio_validade_dias * 86400:
            log.info("estudio_vencido", tema=m["tema"][:80])
            _apagar(meta.parent)
            continue
        slides = [p.read_bytes() for p in sorted(meta.parent.glob("*.jpg"))]
        done = publish_carousel(slides, m["ig"], fb_caption=m["fb"])
        log.info("estudio_publicado", tema=m["tema"][:80], nets=done)
        if done:
            _apagar(meta.parent)
        return
    log.info("estudio_sem_estoque")


def _apagar(pasta: Path) -> None:
    for f in pasta.glob("*"):
        f.unlink(missing_ok=True)
    pasta.rmdir()


def ciclo() -> None:
    """De hora em hora: recebe o que o PC devolveu e repõe as tarefas (leve: só leitura de RSS quando falta estoque)."""
    try:
        if settings.estudio_simples:
            repor_simples()
            return
        receber()
        planejar()
    except Exception as e:  # noqa: BLE001
        log.error("estudio_ciclo_falhou", error=str(e)[:200])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "assuntos"
    if cmd == "assuntos":
        for a in assuntos():
            print(a["editoria"], a["nota"], a["fontes"], "|", a["noticias"][0]["titulo"])
    elif cmd == "previa":  # monta SEM publicar e SEM mexer no estoque: imagens em /srv/cache/aprovados/novidade-simples
        import io

        from PIL import Image
        saida = Path("/srv/cache/aprovados/novidade-simples")
        saida.mkdir(parents=True, exist_ok=True)
        for k, a in enumerate(assuntos(n=4)):
            r = montar_simples(a)
            if not r:
                continue
            slides, ig, fb = r
            cols = min(4, len(slides))
            linhas = (len(slides) + cols - 1) // cols
            folha = Image.new("RGB", (cols * 540, linhas * 675), "white")
            for n, sl in enumerate(slides):
                folha.paste(Image.open(io.BytesIO(sl)).convert("RGB").resize((540, 675)), ((n % cols) * 540, (n // cols) * 675))
                (saida / f"post{k + 1}-{n + 1}.jpg").write_bytes(sl)
            folha.save(saida / f"post{k + 1}.jpg", quality=90)
            (saida / f"post{k + 1}.txt").write_text(ig, encoding="utf-8")
            print("--- post", k + 1, a["editoria"], len(slides), "slides |", a["noticias"][0]["titulo"][:90])
    elif cmd == "publicar":  # publicar "<trecho do título>": publica esse item do estoque agora (usado por agendamento do systemd)
        from app.content import publish_carousel
        for meta in sorted(EST.glob("*/meta.json")):
            m = json.loads(meta.read_text(encoding="utf-8"))
            if sys.argv[2].lower() in m["tema"].lower():
                slides = [f.read_bytes() for f in sorted(meta.parent.glob("*.jpg"))]
                done = publish_carousel(slides, m["ig"], fb_caption=m["fb"])
                log.info("estudio_publicado", tema=m["tema"][:80], nets=done)
                print("publicado em:", done)
                if done:
                    _apagar(meta.parent)
                break
        else:
            print("não achei no estoque")
    elif cmd == "guardar":  # guardar "<trecho do título>" ...: põe no estoque os assuntos (na ordem dada)
        todos = assuntos(n=80)
        for trecho in sys.argv[2:]:
            a = next((x for x in todos if any(trecho.lower() in n["titulo"].lower() for n in x["noticias"])), None)
            print(trecho, "->", "guardado" if a and _guardar(a) else "não achei/sem texto")
    elif cmd == "planejar":
        print("tarefas criadas:", planejar())
    elif cmd == "receber":
        print("no estoque:", receber())
    elif cmd == "estoque":
        for m in sorted(EST.glob("*/meta.json")):
            print(m.parent.name, json.loads(m.read_text(encoding="utf-8"))["tema"][:90])
        print("pendentes:", len(list(PEND.glob("*.json"))))
