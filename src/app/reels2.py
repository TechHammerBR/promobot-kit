"""Reels no estilo do @quantoquevaicustar (referência do dono, 08/10/2026): narração CONTÍNUA com a voz do dono, legendas palavra a palavra,
cortes rápidos de cenas de jogo trocando no ritmo da fala, título e palavras-chave em AMARELO. Dois formatos:
  build_semana(games)  -> UM Reel com todos os jogos grátis da semana
  build_jogo(game)     -> UM Reel por jogo grátis
Fluxo: dados do jogo (Steam) -> roteiro (IA local, só fatos da descrição oficial) -> narração (serviço de voz, texto corrido + tempo das palavras)
-> cenas cortadas nas frases -> trechos do trailer -> legendas ASS -> mixagem com a música."""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from app import gpu
from app.config import settings
from app.game_reels import FRASE_PLAT, steam_lookup
from app.log import log

W, H, FPS = 1080, 1920, 30
FONTES = Path(__file__).parent / "assets" / "fonts"
COOP = {9: "coop", 38: "coop online", 24: "coop em tela dividida", 1: "multijogador", 36: "online competitivo"}
EDICAO = re.compile(r"\b(remaster(?:ed)?|edition|anniversary|definitive|complete|collection|deluxe|goty|ultimate|enhanced)\b", re.I)


def nome_curto(nome: str) -> str:
    """'System Shock 2: 25th Anniversary Remaster' -> 'System Shock 2' (nome falado e mostrado)."""
    n = re.sub(r"[™®©]", "", nome).strip()
    partes = re.split(r"\s*(?::| - | – )\s*", n, maxsplit=1)
    if len(partes) == 2 and (EDICAO.search(partes[1]) or len(partes[1].split()) > 3):
        n = partes[0]
    return re.sub(r"\s+", " ", EDICAO.sub("", n)).strip(" ,-:")


# A Steam "brazilian" às vezes vem em português de PORTUGAL (comboio, carris, equipa...): a IA copiava e a voz ganhava sotaque. Converte para o Brasil.
PTPT = [(r"comboios?", "trem"), (r"carris", "trilhos"), (r"equipas?", "equipe"), (r"ecr[ãa]s?", "tela"), (r"telem[óo]veis?", "celular"), (r"raparigas?", "garotas"),
        (r"mi[úu]dos?", "garotos"), (r"autocarros?", "ônibus"), (r"ficheiros?", "arquivos"), (r"utilizadores?", "usuários"), (r"descarregar", "baixar"),
        (r"arrojad[oa]s?", "ousado"), (r"conceba", "crie"), (r"Este preparado", "Esteja preparado"), (r"\b[Aa]s suas\b", "suas"), (r"\b[Oo]s seus\b", "seus"),
        (r"\b[Aa] sua\b", "sua"), (r"\b[Oo] seu\b", "seu"), (r"\bfixe\b", "legal"), (r"\bgiro\b", "legal"), (r"\brato\b", "mouse"), (r"auton[óo]mos?", "autônomo"),
        (r"cafund[óo]s", "cantos remotos")]


def _br(t: str) -> str:
    for pat, novo in PTPT:
        t = re.sub(pat, novo, t)
    return t


def info_jogo(g: dict) -> dict:
    """Dados para roteiro e cortes: descrição oficial em português, gêneros, modos (coop...), trailers e capa."""
    info = {"nome": nome_curto(g["name"]), "plataforma": g["platform"], "desc": "", "sobre": "", "generos": [], "modos": [], "trailers": [], "capa": g.get("image"), "appid": None}
    it = steam_lookup(g["name"])
    if not it:
        return info
    try:
        d = httpx.get("https://store.steampowered.com/api/appdetails", params={"appids": it["id"], "cc": "br", "l": "brazilian"}, timeout=25).json()[str(it["id"])]["data"]
    except Exception as e:  # noqa: BLE001
        log.warning("reels2_steam", error=str(e)[:100])
        return info
    info["appid"] = it["id"]
    limpa = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()  # noqa: E731
    info["desc"] = _br(limpa(d.get("short_description")))
    info["sobre"] = _br(limpa(d.get("about_the_game")))
    info["generos"] = [x["description"] for x in d.get("genres", [])][:3]
    info["modos"] = [COOP[c["id"]] for c in d.get("categories", []) if c["id"] in COOP]
    filmes = sorted(d.get("movies") or [], key=lambda m: bool(re.search(r"\bjp\b|japan|korea|\bkr\b|chin|\bcn\b|\u3010", m.get("name", ""), re.I)))
    for m in filmes[:3]:
        url = (m.get("mp4") or {}).get("max") or (m.get("mp4") or {}).get("480") or m.get("hls_h264")
        if url:
            info["trailers"].append(url)
    info["capa"] = d.get("header_image") or info["capa"]
    return info


def _fatos(info: dict) -> str:
    return NL.join([f"Jogo: {info['nome']}", f"Gêneros: {', '.join(info['generos']) or 'não informado'}",
                    f"Modos: {', '.join(info['modos']) or 'não informado'}", f"Descrição oficial: {info['desc'][:600] or 'não informada'}",
                    f"Mais detalhes: {info['sobre'][:900]}"])


def _chat(msgs: list[dict], temp: float) -> dict | None:
    """Chama a IA local; tenta de novo se falhar (o Ollama devolve 500 quando duas chamadas pedem o carregamento do modelo ao mesmo tempo
    ou quando a voz acabou de soltar a GPU)."""
    if not settings.ai_enabled:  # Wyse: sem IA local -> texto seguro (sem esperar 80 s por chamada)
        return None
    for tentativa in range(4):
        try:
            r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=180, json={"model": settings.ai_model, "stream": False, "format": "json", "think": False,
                         "messages": msgs, "options": {"temperature": temp, "num_predict": 220, "num_gpu": settings.bot_ai_num_gpu}})
            return json.loads(r.json()["message"]["content"])
        except Exception as e:  # noqa: BLE001
            log.warning("reels2_llm", error=str(e)[:100], tentativa=tentativa + 1)
            time.sleep(8 * (tentativa + 1))
    return None


def _verifica(info: dict, texto: str) -> bool:
    """Segunda passada da IA: o texto afirma algo que NÃO está nos fatos oficiais, ou soa estranho para um brasileiro? True = pode usar."""
    d = _chat([{"role": "system", "content": "Você confere textos de divulgação de jogos para um canal brasileiro. Seja rigoroso. Responda só JSON."},
               {"role": "user", "content": _fatos(info) + NL + NL + f"TEXTO: {texto}" + NL + NL +
                "1) O TEXTO afirma algo que NÃO está nos fatos acima (ações, modos, personagens, violência, quantidades, recursos)? "
                "2) O TEXTO tem palavra ou expressão que um brasileiro NÃO diria falando com um amigo (português de Portugal, regionalismo raro, "
                "tradução literal sem sentido, item específico estranho) ou cita povos, etnias, religiões ou política como inimigos ou alvo? "
                "Responda {\"inventou\": true ou false, \"estranho\": true ou false, \"trecho\": \"o trecho problemático\"}"}], 0.0)
    if d is None:
        return False
    sim = (True, "true", "True")
    if d.get("inventou") in sim or d.get("estranho") in sim:
        log.info("reels2_invencao", jogo=info["nome"], inventou=d.get("inventou"), estranho=d.get("estranho"), trecho=str(d.get("trecho", ""))[:100])
        return False
    return True


def _llm(info: dict, instrucao: str, limite: int) -> str | None:
    """Descrição CURTA pela IA local usando SÓ os fatos oficiais: valida tamanho/caracteres e a CONFERE com uma segunda passada. None = usar o texto seguro."""
    sistema = ("Você escreve falas para Reels de um canal brasileiro de games, em tom animado e natural, como quem conta para um amigo, em português do BRASIL "
               "falado (trem, não comboio; equipe, não equipa; tela, não ecrã) e com palavras simples do dia a dia. "
               "Use SOMENTE os fatos fornecidos (se vierem em inglês, traduza as ideias para português do Brasil). Não invente datas, preços, notas, estúdios, "
               "personagens, recursos nem violência que não esteja escrita. Números por extenso, sem emojis, sem hashtags, sem aspas, só letras do português.")
    for temp in (0.3, 0.15, 0.5):
        d = _chat([{"role": "system", "content": sistema}, {"role": "user", "content": _fatos(info) + NL + NL + instrucao + NL + "Responda só JSON: {\"texto\": \"...\"}"}], temp)
        t = _br(re.sub(r"\s+", " ", str((d or {}).get("texto", "")).replace("\"", "").replace("*", "")).strip())
        if not t or len(t.split()) > limite + 4 or any(ord(c) > 0x2FF and not 0x2010 <= ord(c) <= 0x2027 for c in t) or re.search(r"http|#|@", t):
            continue
        if re.search(r"\d", t) and not re.search(r"\d", _fatos(info)):
            continue
        if _verifica(info, t):
            return t
    return None


CTA_JOGO = ["Corre pra resgatar antes que acabe! O link tá aqui na descrição.", "Salva esse vídeo e resgata antes que acabe! O link tá no perfil.",
            "Manda pro amigo gamer! Os links estão aqui na descrição.", "Quer resgatar? O link do grupo de ofertas tá no perfil."]
CTA_SEMANA = ["Salva e manda pro amigo gamer! Todos os links estão aqui na descrição.", "Marca aquele amigo gamer! O link do grupo de ofertas tá no perfil.",
              "Corre pra resgatar todos eles! Os links estão aqui na descrição."]
INTRO_SEMANA = ["Olha só os jogos de graça dessa semana!", "Esses jogos estão de graça agora, corre pra pegar!", "Jogo grátis é aqui! Anota aí os da semana."]
MOLDES_SEMANA = ["{n}, {d}, {p}.", "Tem também {n}: {d}, {p}!", "{n}! {D}, {p}.", "Olha só, {n}: {d}, {p}.", "E mais um: {n}, {d}, {p}."]


def _semana_do_ano() -> int:
    import datetime as _dt
    return _dt.date.today().isocalendar()[1]


def _frase_padrao(info: dict) -> str:
    """Sem IA: a 1ª frase da descrição OFICIAL (sem o nome do jogo) ou, se não houver, só os gêneros e modos oficiais."""
    d = info.get("desc") or ""
    nome = re.escape(info["nome"])
    m = re.match(rf"^{nome}\s+(?:é|e)\s+(.+?)(?:[.!?]|$)", d, re.I)
    if m and 4 <= len(m.group(1).split()) <= 24 and not re.search(r"\d", m.group(1)):
        return "É " + m.group(1).strip() + "."
    partes = []
    if info["generos"]:
        partes.append("É um jogo de " + " e ".join(g.lower() for g in info["generos"][:2]) + ".")
    if info["modos"]:
        partes.append("Dá pra jogar em " + info["modos"][0] + ".")
    return " ".join(partes)


def _curta(info: dict) -> str:
    t = _llm(info, "Em NO MÁXIMO 9 palavras, em minúsculas e sem ponto final, diga o que é o jogo e o que se faz nele, sem citar o nome. "
             "Use palavras simples do dia a dia. Exemplo de estilo: tiro frenético contra demônios em Marte", 9)
    if t:
        return t.rstrip(".!").lower()
    return ("um jogo de " + " e ".join(g.lower() for g in info["generos"][:2])) if info["generos"] else "um jogo que vale a pena conferir"


def _plat(info: dict) -> str:
    return FRASE_PLAT.get(info["plataforma"], "grátis, " + info["plataforma"].title())


def _unidades(frases: list[tuple[str, int | None, str]]) -> tuple[str, list[str], list[dict]]:
    """frases = [(texto com [[nome]], índice do jogo ou None, tipo)] -> (texto, unidades de legenda, faixas por frase)."""
    texto, unidades, faixas = [], [], []
    for txt, jogo, tipo in frases:
        toks = txt.replace("[[", "").replace("]]", "").split()
        i0 = len(unidades)
        unidades += toks
        faixas.append({"i0": i0, "i1": len(unidades) - 1, "jogo": jogo, "tipo": tipo})
        texto.append(txt)
    return " ".join(texto), unidades, faixas


def roteiro_jogo(info: dict, idx: int = 0) -> tuple[str, list[str], list[dict]]:
    """Reel de UM jogo: gancho (nome + onde resgatar) + 1-2 frases descrevendo + chamada final."""
    n = info["nome"]
    gancho = [f"[[{n}]], {_plat(info)}!", f"Olha só: [[{n}]], {_plat(info)}!"][(idx + _semana_do_ano()) % 2]
    desc = _llm(info, "Escreva 2 frases curtas (no máximo 12 palavras cada, 26 no total) no estilo de narrador de Reels de games: direto, empolgante, falando com você. "
                "Cada frase com UM verbo de ação forte (explorar, lutar, construir, sobreviver, dirigir...) e UMA ideia só, sem lista de itens com várias vírgulas. "
                "Foque no que a pessoa FAZ no jogo e no que o torna único, usando só os fatos acima, com palavras simples do dia a dia: "
                "nada de termos raros ou regionais nem de itens específicos do jogo (cartas, besouros, nomes de armas). "
                "Nunca cite povos, etnias, religiões, nacionalidades ou política (diga só 'inimigos'). "
                "Não repita o nome do jogo e não diga que é grátis. Exemplos de estilo (outros jogos): "
                "'Você luta contra monstros sem parar, com armas devastadoras. Joga sozinho ou em equipe, com mapas cheios de ação!' / "
                "'Você explora um enorme mundo subterrâneo cheio de segredos. Dá pra jogar em coop com até oito jogadores!' / "
                "'Num mundo dominado por máquinas gigantes, você enfrenta ameaças e caça o melhor loot. Quanto mais explora, maior o risco!'", 28) or _frase_padrao(info)
    frases = [(gancho, 0, "gancho")]
    for s in re.split(r"(?<=[.!?])\s+", desc):
        if s.strip():
            frases.append((s.strip(), 0, "desc"))
    frases.append((CTA_JOGO[(idx + _semana_do_ano()) % len(CTA_JOGO)], None, "cta"))
    return _unidades(frases)


def roteiro_semana(infos: list[dict]) -> tuple[str, list[str], list[dict]]:
    """Reel da semana: abertura + UMA frase por jogo (nome, o que é, onde resgatar) + chamada final."""
    frases = [(INTRO_SEMANA[_semana_do_ano() % len(INTRO_SEMANA)], None, "intro")]
    for i, info in enumerate(infos):
        d, p = _curta(info), _plat(info)
        nome = f"[[{info['nome']}]]"
        if i == len(infos) - 1 and len(infos) > 2:
            txt = f"E fechando a lista: {nome}, {d}, {p}!"
        else:
            txt = MOLDES_SEMANA[i % len(MOLDES_SEMANA)].format(n=nome, d=d, D=d[:1].upper() + d[1:], p=p)
        frases.append((txt, i, "jogo"))
    frases.append((CTA_SEMANA[_semana_do_ano() % len(CTA_SEMANA)], None, "cta"))
    return _unidades(frases)


def cortes_jogo(tempos: list[list[float]], dur: float, alvo: float = 1.8, minimo: float = 1.2, maximo: float = 2.8) -> list[tuple[float, float]]:
    """Cenas [ini, fim) de um Reel de um jogo: cortes nos inícios de palavra mais próximos de ~2,3 s (nunca no meio de uma palavra)."""
    inicios = sorted({round(t[0], 3) for t in tempos})
    cortes = [0.0]
    while dur - cortes[-1] > maximo + 0.8:
        a = cortes[-1]
        cand = [t for t in inicios if a + minimo <= t <= a + maximo]
        cortes.append((min(cand, key=lambda t: abs(t - (a + alvo))) if cand else a + alvo) - 0.04)
    return list(zip(cortes, cortes[1:] + [dur + 0.45]))


_fim_de_clausula: dict[int, bool] = {}  # índice da palavra -> a palavra anterior terminou em , : ; . ! ? (preenchido por build_semana)


def cenas_semana(tempos: list[list[float]], faixas: list[dict], dur: float, n_jogos: int) -> list[dict]:
    """Cenas do Reel da semana: cada jogo ocupa SUA frase inteira (a imagem só troca no respiro entre frases); frases longas ganham um corte no meio."""
    marcos = [(f["jogo"], max(0.0, tempos[f["i0"]][0] - 0.10)) for f in faixas if f["tipo"] == "jogo"]
    cta = next((f for f in faixas if f["tipo"] == "cta"), None)
    fim_jogos = max(0.0, tempos[cta["i0"]][0] - 0.10) if cta else dur
    cenas = [{"jogo": 0, "t0": 0.0, "t1": marcos[0][1], "tipo": "intro"}] if marcos and marcos[0][1] > 0.4 else []
    for k, (j, t0) in enumerate(marcos):
        cenas.append({"jogo": j, "t0": t0, "t1": marcos[k + 1][1] if k + 1 < len(marcos) else fim_jogos, "tipo": "jogo"})
    cenas.append({"jogo": n_jogos - 1, "t0": fim_jogos, "t1": dur + 0.45, "tipo": "cta"})
    inicios = sorted({round(t[0], 3) for t in tempos})
    saida = []
    for c in cenas:
        if c["t1"] - c["t0"] > 3.8:  # corta no início de palavra mais perto do meio
            meio = (c["t0"] + c["t1"]) / 2
            clausulas = [tempos[i][0] for i in range(1, len(tempos)) if tempos[i - 1][1] <= tempos[i][0] and tempos[i][0] > 0 and _fim_de_clausula.get(i)]
            cands = [t for t in clausulas if c["t0"] + 1.2 < t < c["t1"] - 1.2] or [t for t in inicios if c["t0"] + 1.2 < t < c["t1"] - 1.2]
            m = min(cands, key=lambda t: abs(t - meio), default=meio) - 0.04
            saida += [{"jogo": c["jogo"], "t0": c["t0"], "t1": m, "tipo": c["tipo"]}, {"jogo": c["jogo"], "t0": m, "t1": c["t1"], "tipo": c["tipo"]}]
        else:
            saida.append(c)
    return saida


def _duracao(p: Path) -> float:
    """Duração em segundos: ffprobe se existir; senão lê Duration do ffmpeg -i (o PC só tem o ffmpeg do imageio)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        t = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p)], capture_output=True, text=True, timeout=30).stderr
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t)
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    except (OSError, subprocess.SubprocessError):
        return 0.0


def baixar_trailer(url: str, dest: Path) -> bool:
    """Baixa o trailer inteiro uma vez (mp4 direto ou HLS) para cortar vários trechos dele."""
    try:
        if ".m3u8" in url:
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", url, "-map", "0:v:0", "-an", "-c", "copy", str(dest)], check=True, timeout=240)
        else:
            with httpx.stream("GET", url, timeout=60, follow_redirects=True) as r, open(dest, "wb") as f:
                for pedaco in r.iter_bytes():
                    f.write(pedaco)
        return dest.exists() and dest.stat().st_size > 200_000 and _duracao(dest) > 5
    except Exception as e:  # noqa: BLE001
        log.warning("reels2_trailer", error=str(e)[:120])
        return False


LEGENDA_PALAVRA = False  # True = uma palavra por vez, grande (estilo @muriloczz)
FG_ALTURA = 1350  # altura do clip no centro (px); 1080 = quase quadrado, mostra mais do trailer
LEGENDA_Y = None  # None = faixa de baixo (1760) ou, no estilo palavra, perto do fim do clip
LEGENDA_TAM = 66


def _layout() -> str:
    fg_w_crop = FG_ALTURA / 1350 * 0.8 * 1.0  # largura do recorte em fração da altura: 0,8 (4:5) para 1350; mais baixo = recorte mais largo
    asp = W / FG_ALTURA
    topo = (H - FG_ALTURA) // 2 - 40
    return (f"[0:v]split[a][b];[a]crop=iw:ih*0.78:0:0,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=7:1,eq=brightness=-0.10:saturation=1.15[bg];"
            f"[b]crop='min(iw,ih*{asp:.3f})':'ih':'(iw-min(iw,ih*{asp:.3f}))/2':0,scale={W}:{FG_ALTURA}[fg];[bg][fg]overlay=0:{topo}[v0];"
            f"[v0]fps={FPS},format=yuv420p,setsar=1[v]")



def corte_trailer(trailer: Path, off: float, dur: float, dest: Path) -> bool:
    """Um trecho do trailer no layout de celular: quadrado central grande + fundo desfocado (estilo do canal de referência)."""
    try:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{off:.2f}", "-i", str(trailer), "-t", f"{dur + 0.3:.2f}", "-filter_complex", _layout(), "-map", "[v]",
                        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS), "-frames:v", str(max(1, round(dur * FPS))), str(dest)], check=True, timeout=240)
        return dest.exists() and dest.stat().st_size > 20_000
    except Exception as e:  # noqa: BLE001
        log.warning("reels2_corte", error=str(e)[:120])
        return False


def _apagado(p: Path) -> bool:
    """Trecho com quadro quase preto ou quase branco (fade/cartela do trailer)? Mede o brilho médio do quadro central, 5 amostras por segundo.
    Preto de vídeo = 16 (faixa limitada) e branco = 235: um quarto das amostras assim já derruba o trecho (o corte tenta outro ponto do trailer)."""
    try:
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(p), "-vf", "crop=864:1080:108:405,fps=5,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                            "-f", "null", "-"], capture_output=True, text=True, timeout=120)
        v = [float(x) for x in re.findall(r"YAVG=([0-9.]+)", r.stdout)]
    except Exception:  # noqa: BLE001
        return False
    if not v:
        return False
    media = sum(v) / len(v)
    return media < 22 or media > 225 or sum(1 for x in v if x <= 19) / len(v) > 0.10 or sum(1 for x in v if x >= 232) / len(v) > 0.25


def offsets(duracao_trailer: float, r: int, total: int, dur: float) -> float:
    """Ponto do trailer para o trecho r de `total`: espalhado entre 5 s e o fim (pula logos e cartela final)."""
    ini, fim = (5.0, duracao_trailer - 5.0) if duracao_trailer > 18 else (0.5, duracao_trailer - 0.5)
    ponto = ini + (fim - ini - dur) * (r + 0.5) / max(1, total)
    return max(0.0, min(ponto, duracao_trailer - dur - 0.3))


# ------------------------------------------------------------------ legendas ASS (palavra a palavra) e títulos em amarelo
BS = chr(92)
NL = chr(10)
AMARELO, BRANCO = "&H000AD6FF", "&H00FFFFFF"  # ASS usa BGR: #FFD60A
CHAVES = re.compile(r"gr[áa]tis|de gra[çc]a|resgat|coop|online|multijogador|jogadores|desconto|incluso|lan[çc]amento|corre", re.I)
ASS_CAB = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,Poppins ExtraBold,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,7,0,5,70,70,0,1
Style: Titulo,Anton,110,&H000AD6FF,&H000AD6FF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,8,0,8,50,50,0,1
Style: Plat,Poppins ExtraBold,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,5,0,8,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _t(s: float) -> str:
    cs = int(round(max(0.0, s) * 100))
    h, r = divmod(cs, 360000)
    m, r = divmod(r, 6000)
    seg, c = divmod(r, 100)
    return f"{h}:{m:02d}:{seg:02d}.{c:02d}"


def _cor(txt: str, cor: str) -> str:
    return "{" + BS + "c" + cor + "&}" + txt + "{" + BS + "c" + BRANCO + "&}"


def _indices_de_nome(unidades: list[str], nomes: list[str]) -> set[int]:
    """Posições das palavras que formam o NOME de um jogo (para a legenda não juntar o nome com a descrição)."""
    norm = [re.sub(r"\W", "", u.lower()) for u in unidades]
    dentro: set[int] = set()
    for n in nomes:
        p = [re.sub(r"\W", "", w.lower()) for w in n.split()]
        p = [w for w in p if w]
        for i in range(len(norm) - len(p) + 1):
            if p and norm[i:i + len(p)] == p:
                dentro.update(range(i, i + len(p)))
    return dentro


def grupos_legenda(unidades: list[str], tempos: list[list[float]], max_pal: int = 3, max_chars: int = 24, nomes: list[str] | None = None) -> list[list[int]]:
    """Agrupa palavras de 2-3 em 2-3: quebra em pausa, em QUALQUER pontuação (, : ; . ! ?), na troca nome-do-jogo/descrição ou por tamanho."""
    nome_idx = _indices_de_nome(unidades, nomes or [])
    grupos, atual = [], []
    for i, u in enumerate(unidades):
        if atual:
            gap = tempos[i][0] - tempos[atual[-1]][1]
            pontuou = unidades[atual[-1]][-1:] in ".!?,:;"
            chars = sum(len(unidades[j]) + 1 for j in atual) + len(u)
            muda_nome = (i in nome_idx) != (atual[-1] in nome_idx)
            if len(atual) >= max_pal or gap > 0.30 or pontuou or muda_nome or chars > max_chars:
                grupos.append(atual)
                atual = []
        atual.append(i)
    if atual:
        grupos.append(atual)
    return grupos


def _pal(u: str) -> str:
    u = u.strip(".,;:")
    return u.upper() if LEGENDA_PALAVRA else u


def gerar_ass(unidades: list[str], tempos: list[list[float]], titulos: list[tuple[float, float, str, str]], dest: Path, nome_jogos: list[str]) -> None:
    """Legenda palavra a palavra no centro-baixo (brancas, contorno preto; palavras-chave e nome do jogo em AMARELO) + título do jogo em amarelo no topo."""
    chaves = {re.sub(r"\W", "", w.lower()) for n in nome_jogos for w in n.split() if len(w) > 2}
    linhas = []
    for t0, t1, nome, plat in titulos:
        tam = 128 if len(nome) <= 16 else 100 if len(nome) <= 26 else 80
        lin = -(-len(nome) // {128: 17, 100: 22, 80: 27}[tam])  # linhas que o título ocupa (Anton ~0,45 x tamanho por letra)
        y_plat = int(175 + lin * tam * 1.08 + 25)
        linhas.append(f"Dialogue: 0,{_t(t0)},{_t(t1)},Titulo,,0,0,0,," + "{" + BS + "an8" + BS + "pos(540,175)" + BS + "fs" + str(tam) + "}" + nome.upper())
        linhas.append(f"Dialogue: 0,{_t(t0)},{_t(t1)},Plat,,0,0,0,," + "{" + BS + "an8" + BS + "pos(540," + str(y_plat) + ")}" + plat.upper())
    gr = grupos_legenda(unidades, tempos, max_pal=1 if LEGENDA_PALAVRA else 3, max_chars=20 if LEGENDA_PALAVRA else 24, nomes=nome_jogos)
    eventos = []
    for k, g in enumerate(gr):
        a, b = tempos[g[0]][0], tempos[g[-1]][1] + 0.06
        if k + 1 < len(gr):
            b = min(b, tempos[gr[k + 1][0]][0])
        b = max(b, a + (0.18 if LEGENDA_PALAVRA else 0.28))
        txt = " ".join(_cor(_pal(unidades[i]), AMARELO) if (CHAVES.search(unidades[i]) or re.sub(r"\W", "", unidades[i].lower()) in chaves)
                       else _pal(unidades[i]) for i in g)
        eventos.append(f"Dialogue: 1,{_t(a)},{_t(b)},Legenda,,0,0,0,," + "{" + BS + "pos(540," + str(LEGENDA_Y or (H - (H - FG_ALTURA) // 2 + 40 - 250 if LEGENDA_PALAVRA else 1760)) + ")}" + txt)  # faixa de baixo: longe das legendas queimadas dos trailers (15/10)
    cab = ASS_CAB.replace("Poppins ExtraBold,66,", f"Poppins ExtraBold,{LEGENDA_TAM},").replace(",1,7,0,5,70,70,0,1", ",1," + ("10" if LEGENDA_PALAVRA else "7") + ",0,5,70,70,0,1")
    dest.write_text(cab + NL.join(linhas) + NL + NL.join(eventos) + NL, encoding="utf-8")


# ------------------------------------------------------------------ montagem
def _musica() -> Path | None:
    from app import musica
    return musica.escolher(30.0)[0]  # rodízio: não repete as últimas faixas (o início segue fixo em 20 s por causa do cálculo de volume)


MUSICA_REL_DB = -17.0  # a música (nivelada em LUFS) fica ~17 dB abaixo da voz. Antes: volume FIXO; trilhas fortes (-8 LUFS) chegavam a +3 dB ACIMA da voz (medido em 08/10)


def _lufs(path: Path, ss: float = 0.0, t: float | None = None) -> float | None:
    cmd = ["ffmpeg", "-hide_banner", "-nostats"] + (["-ss", f"{ss}"] if ss else []) + (["-t", f"{t:.1f}"] if t else []) + ["-i", str(path), "-af", "ebur128", "-f", "null", "-"]
    try:
        txt = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stderr
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r"I: +(-?[0-9.]+) LUFS", txt[txt.rfind("Summary"):])
    return float(m.group(1)) if m else None


def _ganho_musica(musica: Path, narr: Path, total: float) -> float:
    """Ganho (dB) que põe ESTA trilha MUSICA_REL_DB abaixo da voz: cada trilha tem uma loudness (de -8 a -12,6 LUFS) e o volume fixo deixava as fortes altas demais."""
    v, t = _lufs(narr), _lufs(musica, 20, total + 2)
    if v is None or t is None:
        return -26.0
    return max(-40.0, min(0.0, v + MUSICA_REL_DB - t))


def _esc(p) -> str:
    """Caminho dentro de um filtro do ffmpeg: no Windows a letra do disco precisa de escape; no Linux nada muda."""
    return str(p).replace(chr(92), "/").replace(":", chr(92) + ":")


def mixar(base: Path, ass: Path, narr: Path, total: float, out: Path, polir: bool = False) -> bytes:
    """Vídeo base + legendas ASS queimadas + narração com a música baixa (abaixa mais quando fala) -> pronto para o Instagram.
    Áudio e vídeo saem de comandos SEPARADOS: no mesmo ffmpeg os filtros de áudio voltavam no tempo ("Non-monotonic DTS") e
    pedaços da fala sumiam (08/10). A narração é completada com silêncio até `total` para a música terminar com o fade."""
    m = _musica()
    pasta = out.parent
    wav, vid = pasta / "mix.wav", pasta / "video.mp4"
    ent = ["-ss", "20", "-i", str(m)] if m else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    fmt = "aresample=44100,aformat=channel_layouts=stereo"
    ganho = _ganho_musica(m, narr, total) if m else 0.0
    voz_cadeia = ("highpass=f=80,acompressor=threshold=0.08:ratio=2.5:attack=8:release=140:makeup=2,equalizer=f=220:t=q:w=1.0:g=-1.5,"
                  "equalizer=f=3000:t=q:w=1.0:g=2.0,treble=g=1.0:f=8000,deesser=i=0.12:m=0.5:f=0.5,") if polir else ""
    ganho_mu = ganho - 3.0 if polir else ganho
    duck = ("sidechaincompress=threshold=0.03:ratio=6:attack=15:release=450" if polir else "sidechaincompress=threshold=0.05:ratio=4:attack=20:release=350")
    f = [f"[0:a]{fmt},afade=t=in:d=0.5,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5,equalizer=f=1800:t=q:w=0.8:g=-3,volume={ganho_mu:.2f}dB[mu]",
         f"[1:a]{fmt},{voz_cadeia}apad=whole_dur={total:.2f},asplit[v1][v2]",
         f"[mu][v1]{duck}[duck]",
         f"[duck][v2]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:LRA=9:TP=-1.5,aresample=48000,atrim=0:{total:.2f}[a]"]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ent, "-i", str(narr), "-filter_complex", ";".join(f), "-map", "[a]", "-t", f"{total:.2f}",
                    "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(wav)], check=True, timeout=900)
    if polir:  # loudnorm de uma passada fica ~3 dB abaixo do alvo em vídeo curto: mede e corrige até -14 LUFS (padrão dos Reels) com limitador de pico
        atual = _lufs(wav)
        if atual is not None and abs(atual + 14.0) > 0.7:
            ajustado = wav.with_name("mix14.wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-af", f"volume={-14.0 - atual:.2f}dB,alimiter=limit=0.89:level=disabled",
                            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(ajustado)], check=True, timeout=300)
            wav = ajustado
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(base), "-vf", f"ass='{_esc(ass)}':fontsdir='{_esc(FONTES)}'", "-t", f"{total:.2f}", "-an",
                    "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60", "-preset", "veryfast", "-crf", "20",
                    str(vid)], check=True, timeout=900)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(vid), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], check=True, timeout=300)
    return out.read_bytes()


def _videos_das_cenas(tmp: Path, infos: list[dict], cenas: list[dict]) -> list[Path]:
    """Um arquivo de vídeo por cena: trechos DIFERENTES do trailer do jogo (ou a capa em movimento se não houver trailer)."""
    from app.game_reels import _cover_img, _name_card, _segment
    por_jogo: dict[int, list[int]] = {}
    for k, c in enumerate(cenas):
        por_jogo.setdefault(c["jogo"], []).append(k)
    trailers: dict[int, list[Path]] = {}
    for j in por_jogo:
        for n, url in enumerate(infos[j]["trailers"][:3]):  # só o MELHOR trailer (o 1º que baixar): o 2º costuma ser PV/teaser em outro idioma
            p = tmp / f"trailer{j}_{n}.mp4"
            if baixar_trailer(url, p):
                trailers.setdefault(j, []).append(p)
                break
    arquivos: dict[int, Path] = {}
    for j, ks in por_jogo.items():
        for r, k in enumerate(ks):
            dur = (round(cenas[k]["t1"] * FPS) - round(cenas[k]["t0"] * FPS)) / FPS  # exato em quadros
            dest = tmp / f"cena{k:02d}.mp4"
            if trailers.get(j):
                tr = trailers[j][r % len(trailers[j])]
                dtr = _duracao(tr)
                ponto, feito = offsets(dtr, r, len(ks), dur), False
                for desl in (0.0, 1.7, -1.7, 3.4, 6.0, -6.0, 9.0, -9.0):  # cai em fade/cartela? tenta outro ponto do mesmo trailer
                    off = max(0.0, min(ponto + desl, dtr - dur - 0.3))
                    if corte_trailer(tr, off, dur, dest):
                        feito = True
                        if not _apagado(dest):
                            break
                if feito and not _apagado(dest):  # trecho ainda escuro/branco depois de todas as tentativas -> usa a capa em vez de tela preta (15/10)
                    arquivos[k] = dest
                    continue
            img = _cover_img(infos[j]["capa"]) if infos[j].get("capa") else None
            arquivos[k] = _segment(tmp, 100 + k, dur, None, still=img or _name_card(infos[j]["nome"], infos[j]["plataforma"]))
    return [arquivos[k] for k in range(len(cenas))]


def concatenar(tmp: Path, partes: list[Path]) -> Path:
    lst = tmp / "lista.txt"
    lst.write_text("".join(f"file '{p}'" + NL for p in partes))
    out = tmp / "base.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True, timeout=300)
    return out


# ------------------------------------------------------------------ os dois formatos
PASTA_VOZ: Path | None = None  # prévia: guarda a narração limpa (sem música) de cada Reel aqui; a produção deixa None


def _guardar_voz(tmp: Path, nome: str) -> None:
    if PASTA_VOZ is not None:
        PASTA_VOZ.mkdir(parents=True, exist_ok=True)
        (PASTA_VOZ / f"{nome}.wav").write_bytes((tmp / "nar.wav").read_bytes())


def build_jogo(g: dict, idx: int = 0) -> tuple[bytes, dict] | None:
    """UM Reel para UM jogo: gancho + descrição + chamada, narração contínua, cortes a cada ~2 s nos inícios de palavra, legendas e título amarelo."""
    from app import voz
    info = info_jogo(g)
    texto, unidades, faixas = roteiro_jogo(info, idx)
    nar = voz.narrar_texto(texto, unidades)
    if not nar:
        return None
    tempos, dur = nar["tempos"], nar["segundos"]
    total = dur + 0.45
    cenas = [{"jogo": 0, "t0": a, "t1": b, "tipo": "jogo"} for a, b in cortes_jogo(tempos, dur)]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "nar.wav").write_bytes(nar["wav"])
        _guardar_voz(tmp, f"jogo_{idx:02d}_{re.sub('[^a-z0-9]+', '_', g['name'].lower())[:28]}")
        base = concatenar(tmp, _videos_das_cenas(tmp, [info], cenas))
        gerar_ass(unidades, tempos, [(0.0, total, info["nome"], _plat(info))], tmp / "cap.ass", [info["nome"]])
        video = mixar(base, tmp / "cap.ass", tmp / "nar.wav", total, tmp / "out.mp4")
    return video, {"nome": info["nome"], "plataforma": info["plataforma"], "texto": texto, "segundos": round(total, 1), "cenas": len(cenas)}


def build_semana(games: list[dict]) -> tuple[bytes, dict] | None:
    """UM Reel com TODOS os jogos grátis da semana: uma frase por jogo, a imagem só troca no respiro entre frases (nada de fala cortada)."""
    from app import voz
    infos = [info_jogo(g) for g in games]
    texto, unidades, faixas = roteiro_semana(infos)
    nar = voz.narrar_texto(texto, unidades)
    if not nar:
        return None
    tempos, dur = nar["tempos"], nar["segundos"]
    total = dur + 0.45
    _fim_de_clausula.clear()
    _fim_de_clausula.update({i: unidades[i - 1][-1:] in ".!?,:;" for i in range(1, len(unidades))})
    cenas = cenas_semana(tempos, faixas, dur, len(infos))
    rotulo_cta = "LINKS NA DESCRIÇÃO" if "descrição" in texto[-150:] else "LINK NO PERFIL"  # igual ao que a narração fala
    titulos = []
    for j, info in enumerate(infos):
        cs = [c for c in cenas if c["jogo"] == j and c["tipo"] == "jogo"]
        if cs:
            titulos.append((cs[0]["t0"], cs[-1]["t1"], info["nome"], _plat(info)))
    for c in cenas:
        if c["tipo"] == "intro":
            titulos.append((c["t0"], c["t1"], "JOGOS GRÁTIS", "da semana"))
        elif c["tipo"] == "cta":
            titulos.append((c["t0"], c["t1"], rotulo_cta, "grupo de ofertas"))
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "nar.wav").write_bytes(nar["wav"])
        _guardar_voz(tmp, "semana")
        base = concatenar(tmp, _videos_das_cenas(tmp, infos, cenas))
        gerar_ass(unidades, tempos, titulos, tmp / "cap.ass", [i["nome"] for i in infos])
        video = mixar(base, tmp / "cap.ass", tmp / "nar.wav", total, tmp / "out.mp4")
    return video, {"nome": "Todos os jogos grátis da semana", "jogos": [i["nome"] for i in infos], "texto": texto, "segundos": round(total, 1), "cenas": len(cenas)}
