"""Reels de JOGOS sem narração (06/10, pedido do dono). Formato de celular: trailer INTEIRO no centro + fundo desfocado.

1) "JOGOS GRÁTIS DA SEMANA" (todas as plataformas): Epic, GOG, Steam, Amazon Luna/Prime Gaming, PS Plus, Game Pass —
   fonte Pelando (comunidade BR, só ativos dos últimos 7 dias, preço 0) + Epic (API oficial).
2) "JOGOS EM PROMOÇÃO DA SEMANA" (sem ranking): ofertas da Steam (cc=br) com cortes rápidos de trailer.
Trailer: Steam (busca pelo nome). Sem trailer -> imagem com zoom suave. Trilha sintetizada (sem direitos autorais).
"""
import io
import json
import re
import subprocess
import tempfile
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter

from app.collectors.base import Collector
from app.collectors.pelando import parse
from app.config import settings
from app.log import log
from app.social_art import BG, TEXT, _brand, _font, _hex

W, H, FPS = 1080, 1920, 30
PLAT = [("epicgames", "EPIC GAMES"), ("gog.com", "GOG"), ("steampowered", "STEAM"), ("luna.amazon", "AMAZON LUNA"),
        ("gaming.amazon", "PRIME GAMING"), ("playstation", "PS PLUS"), ("xbox.com", "GAME PASS"), ("nintendo", "NINTENDO")]


class _F(Collector):
    name = "game_reels"


def _platform(url: str) -> str:
    return next((name for key, name in PLAT if key in url), "PC")


def _clean(title: str) -> str:
    t = re.sub(r"^\s*([\(\[][^\)\]]*[\)\]]\s*)+", "", title)
    t = re.sub(r"\s*[-–|]\s*(jogo\s+)?(mobile\s+)?gr[aá]tis.*$", "", t, flags=re.I)
    t = re.sub(r"\s*[-–|]\s*(pc|ps4|ps5|xbox.*|steam|epic.*|gog)\s*$", "", t, flags=re.I)
    t = re.sub(r"^\s*jogo\s+", "", t, flags=re.I)
    return t.strip(" -–|")[:60]


def ps_plus_monthly() -> list[dict]:
    """Jogos mensais do PS Plus pelo blog OFICIAL (título: 'PlayStation Plus Monthly Games for X: A, B, C')."""
    try:
        xml = httpx.get("https://blog.playstation.com/category/ps-plus/feed/", headers={"User-Agent": "Mozilla/5.0"},
                        timeout=30).text
    except Exception:
        return []
    import html as _h
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title = _h.unescape(re.search(r"<title>(.*?)</title>", item, re.S).group(1))
        if "Monthly Games" in title and ":" in title:
            pub = re.search(r"<pubDate>(.*?)</pubDate>", item)
            from email.utils import parsedate_to_datetime
            if pub and datetime.now(timezone.utc) - parsedate_to_datetime(pub.group(1)) > timedelta(days=40):
                return []
            names = [n.strip() for n in re.split(r",| and ", title.split(":", 1)[1]) if n.strip()]
            return [{"name": n, "platform": "PS PLUS", "image": None, "temp": 9999, "url": "https://store.playstation.com"}
                    for n in names[:3]]
    return []


def _chave_nome(n: str) -> str:
    """'F1® 25' e 'F1 25' viram a mesma chave."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"[™®©]", "", n).lower())


def gratis_vistos(dias: int = 28) -> set[str]:
    """Jogos grátis que JÁ saíram em carrossel/Reel nos últimos `dias` (15/10, dono: "não pode repetir os da semana anterior";
    jogos de assinatura como PS Plus/Luna ficam o mês inteiro e voltavam toda semana)."""
    from app.games import _hist
    corte = (datetime.now(timezone.utc) - timedelta(days=dias)).date().isoformat()
    return {_chave_nome(v.get("nome", "")) for k, v in _hist().items() if k.startswith("gratis:") and v.get("quando", "") >= corte}


def free_games(limit: int = 8, quando: datetime | None = None, repetir: bool = False) -> list[dict]:
    """`quando` (opcional, com fuso) = momento de referencia: ve, antes da troca das 12h de quinta, os jogos que a Epic ja anunciou."""
    from app.games import epic_free
    agora = quando or datetime.now(timezone.utc)
    f, since, out = _F(), agora - timedelta(days=21), {}  # assinatura (Prime/Luna/PS Plus) dura ~1 mês; repetidos saem pelo histórico (gratis_vistos)
    try:
        epic = epic_free(quando)  # API oficial = verdade para a Epic (o Pelando demora a encerrar a oferta antiga)
    except Exception as e:
        log.warning("game_reels_epic", error=str(e)[:100])
        epic = None
    for q in ["jogo-gratis", "prime-gaming", "amazon-luna", "game-pass", "gratis-steam", "gratis-gog"]:
        try:
            items = parse(f.get(f"https://www.pelando.com.br/busca/{q}").text)
        except Exception as e:
            log.warning("game_reels_source", q=q, error=str(e)[:100])
            continue
        for i in items:
            if i["status"] != "active" or i["created"] < since or i["price"] or i["temp"] < (150 if agora - i["created"] > timedelta(days=3) else 50):
                continue
            if re.search(r"sticker|avatar|tema |papel de parede|jogue gr[aá]tis|fim de semana|free weekend|teste gr[aá]tis|"
                         r"\bdlc\b|skin|moedas|mobile|android|ios\b|google play|apps? no|para teste|\bteste\b|trial|\bdemo\b", i["title"], re.I):
                continue  # só JOGO para resgatar/manter (ou incluso na assinatura), não brinde/teste/mobile
            name, plat = _clean(i["title"]), _platform(i["url"])
            if re.search(r"prime gaming", i["title"], re.I):  # o resgate fica em luna.amazon.com, mas é o Prime Gaming (PC)
                plat = "PRIME GAMING"
            if plat == "EPIC GAMES" and epic is not None:
                continue
            if name.lower() not in out:
                out[name.lower()] = {"name": name, "platform": plat, "image": i["image"],
                                     "temp": i["temp"], "url": i["url"]}
    for g in epic or []:
        out.setdefault(g["name"].lower(), {"name": g["name"], "platform": "EPIC GAMES", "image": g["image"],
                                           "temp": 5000, "url": g["url"]})
    for g in ps_plus_monthly():
        out.setdefault(g["name"].lower(), g)
    vistos = set() if repetir else gratis_vistos()
    for k in [k for k, g in out.items() if _chave_nome(g["name"]) in vistos]:
        out.pop(k)
    per, res = {}, []
    for g in sorted(out.values(), key=lambda g: -g["temp"]):
        if per.get(g["platform"], 0) < 3:
            per[g["platform"]] = per.get(g["platform"], 0) + 1
            res.append(g)
    # intercala plataformas (não ficar 3 Epic seguidos)
    seen, keyed = {}, []
    for g in res:
        seen[g["platform"]] = seen.get(g["platform"], 0) + 1
        keyed.append((seen[g["platform"]], -g["temp"], g))
    res = [g for *_, g in sorted(keyed, key=lambda k: (k[0], k[1]))]
    return res[:limit]


def steam_lookup(name: str) -> dict | None:
    def buscar(termo: str, prefixo: bool) -> dict | None:
        try:
            r = httpx.get("https://store.steampowered.com/api/storesearch/", params={"term": termo, "cc": "br", "l": "portuguese"},
                          timeout=20).json()
            alvo = re.sub(r"\W", "", termo.lower())
            for it in r.get("items", [])[:5]:
                nome = re.sub(r"\W", "", it["name"].lower())
                if prefixo:
                    if len(alvo) >= 5 and nome.startswith(alvo) and "demo" not in nome:
                        return it
                elif nome[:12] == alvo[:12] or (len(alvo) >= 4 and (alvo in nome or nome in alvo)):
                    return it
        except Exception:
            pass
        return None

    achou = buscar(name, False)
    if achou is None and ":" in name:  # título traduzido pela loja (Epic BR): tenta só o trecho antes do ":"
        achou = buscar(name.split(":", 1)[0].strip(), True)
    return achou


def _duracao_arq(p: Path) -> float:
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                    capture_output=True, text=True, timeout=30).stdout.strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def trailer_clip(appid: int, dest: Path, start: int = 25, dur: float = 4.0) -> bool:
    """Baixa só o trecho [start, start+dur] do trailer (pula a abertura = mais gameplay).
    15/10: o HLS com busca na ENTRADA gerava arquivo quebrado ('Invalid NAL unit size') e o Reel caía no cartão com o nome do jogo.
    Agora: DASH com busca na entrada; trailer curto -> começa mais cedo; último recurso HLS com busca na SAÍDA (lento, mas íntegro)."""
    try:
        d = httpx.get("https://store.steampowered.com/api/appdetails", params={"appids": appid}, timeout=20).json()[str(appid)]["data"]
        filmes = d.get("movies") or []
        filme = next((m for m in filmes if m.get("highlight")), filmes[0] if filmes else None)
        if not filme:
            return False
        tentativas = [(filme.get("dash_h264"), start, True), (filme.get("dash_h264"), 3, True), (filme.get("hls_h264"), 3, False)]
        for url, ini, busca_entrada in tentativas:
            if not url:
                continue
            dest.unlink(missing_ok=True)
            cmd = ["ffmpeg", "-loglevel", "error", "-y"] + (["-ss", str(ini)] if busca_entrada else []) + ["-i", url]
            cmd += ([] if busca_entrada else ["-ss", str(ini)]) + ["-t", f"{dur + 0.5}", "-map", "0:v:0", "-an", "-vf", "scale=1080:-2",
                                                                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            except subprocess.TimeoutExpired:
                continue
            if r.returncode == 0 and dest.exists() and dest.stat().st_size > 50_000 and _duracao_arq(dest) >= dur * 0.8:
                return True
        return False
    except Exception as e:
        log.warning("trailer_failed", appid=appid, error=str(e)[:120])
        return False


def _overlay(top: str, title: str, badge: str, sub: str, rank: str = "") -> Image.Image:
    """Camada transparente: marca, ranking, título, selo de preço e plataforma (fica por cima do vídeo)."""
    accent = _hex(settings.accent_color)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 330), fill=(0, 0, 0, 150))
    _brand(d, W, 95, accent)
    d.text((W / 2, 220), top.upper(), font=_font(54), fill=TEXT, anchor="mm")
    if rank:
        d.ellipse((60, 380, 300, 620), fill=(*accent, 255))
        d.text((180, 500), rank, font=_font(120), fill="white", anchor="mm")
    y = 1330
    for ln in textwrap.wrap(title.upper(), 20)[:2]:
        d.text((W / 2, y), ln, font=_font(72), fill=TEXT, anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
        y += 88
    bf = _font(84)
    bw = d.textlength(badge, font=bf) + 90
    d.rounded_rectangle((W / 2 - bw / 2, y + 30, W / 2 + bw / 2, y + 160), radius=40, fill=(*accent, 255))
    d.text((W / 2, y + 95), badge, font=bf, fill="white", anchor="mm")
    d.text((W / 2, y + 230), sub.upper(), font=_font(44), fill=TEXT, anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0))
    return im


def _card(text1: str, text2: str, text3: str, cta: str) -> Image.Image:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand(d, W, 260, accent)
    d.text((W / 2, 760), text1.upper(), font=_font(118), fill=TEXT, anchor="mm")
    d.text((W / 2, 900), text2.upper(), font=_font(118), fill=TEXT, anchor="mm")
    d.text((W / 2, 1060), text3.upper(), font=_font(104), fill=accent, anchor="mm")
    size = 48
    while d.textlength(cta.upper(), font=_font(size)) > W - 220 and size > 28:  # texto nunca sai da caixa
        size -= 2
    half = d.textlength(cta.upper(), font=_font(size)) / 2 + 60
    d.rounded_rectangle((W / 2 - half, 1500, W / 2 + half, 1630), radius=65, outline=accent, width=6)
    d.text((W / 2, 1565), cta.upper(), font=_font(size), fill=TEXT, anchor="mm")
    return im


def _segment(tmp: Path, idx: int, dur: float, overlay: Image.Image | None, clip: Path | None = None,
             still: Image.Image | None = None) -> Path:
    """Gera 1 cena 1080x1920: vídeo (ou imagem) inteiro no centro + mesmo conteúdo desfocado ao fundo + camada."""
    out = tmp / f"seg{idx}.mp4"
    inputs, frames = [], int(dur * FPS)
    if clip:
        inputs = ["-i", str(clip)]
        base = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=7:1,"
                f"eq=brightness=-0.10[bg];[b]scale={W}:-2[fg];[bg][fg]overlay=0:(H-h)/2-80[v0]")
    else:
        p = tmp / f"still{idx}.jpg"
        still.convert("RGB").save(p, quality=92)
        inputs = ["-loop", "1", "-t", f"{dur}", "-i", str(p)]
        if still.size == (W, H):  # cartão já em tela cheia: só zoom suave
            base = (f"[0:v]scale={W * 2}:{H * 2},zoompan=z='min(zoom+0.0008,1.08)':d={frames}:x='iw/2-(iw/zoom/2)'"
                    f":y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[v0]")
        else:  # capa do jogo: inteira no centro com zoom + fundo desfocado
            base = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=7:1,"
                    f"eq=brightness=-0.10[bg];[b]scale={W * 2}:-2,zoompan=z='min(zoom+0.0012,1.12)':d={frames}"
                    f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{int(W * still.height / still.width) // 2 * 2}:fps={FPS}[fg];"
                    f"[bg][fg]overlay=0:(H-h)/2-80[v0]")
    flt = base
    if overlay is not None:
        op = tmp / f"ov{idx}.png"
        overlay.save(op)
        inputs += ["-i", str(op)]
        flt += f";[v0][1:v]overlay=0:0[v1]"
        last = "v1"
    else:
        last = "v0"
    flt += f";[{last}]fps={FPS},format=yuv420p,setsar=1[v]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", flt, "-map", "[v]", "-t", f"{dur}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS), str(out)], check=True, timeout=300)
    return out


def _join_voz(tmp: Path, lst: Path, total: float, falas: list[tuple[Path, float]], out: Path) -> bytes:
    """Reel NARRADO: música embaixo (abaixa sozinha quando o dono fala) + cada fala no começo da sua cena."""
    from app import musica
    faixa, _ini = musica.escolher(total)
    inputs = ["-f", "concat", "-safe", "0", "-i", str(lst)]
    if faixa:
        inputs += ["-ss", "20", "-i", str(faixa)]
    else:
        music = (f"aevalsrc='0.5*sin(2*PI*55*t)*exp(-12*mod(t,0.5))+0.12*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.25*t))"
                 f"+0.06*sin(2*PI*329.6*t)*(0.5+0.5*sin(2*PI*0.5*t))':s=44100:d={total:.2f}")
        inputs += ["-f", "lavfi", "-i", music]
    for p, _t in falas:
        inputs += ["-i", str(p)]
    fmt = "aresample=44100,aformat=channel_layouts=stereo"
    f = [f"[1:a]{fmt},afade=t=in:d=0.5,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5,equalizer=f=1800:t=q:w=0.8:g=-3,volume=0.45[mu]"]
    labs = []
    for i, (_p, t0) in enumerate(falas):
        f.append(f"[{i + 2}:a]{fmt},volume=1.5,adelay={int(t0 * 1000)}:all=1[n{i}]")
        labs.append(f"[n{i}]")
    f.append("".join(labs) + f"amix=inputs={len(falas)}:normalize=0:dropout_transition=0,asplit[nv1][nv2]")
    f.append("[mu][nv1]sidechaincompress=threshold=0.02:ratio=20:attack=15:release=400[duck]")
    f.append(f"[duck][nv2]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:LRA=9:TP=-1.5,aresample=44100,atrim=0:{total:.2f}[a]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(f), "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)],
                   check=True, timeout=300)
    return ig_ready(out, out.with_name("ig_" + out.name))


def _join(tmp: Path, segs: list[Path], out: Path, falas: list[tuple[Path, float]] | None = None) -> bytes:
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    total = sum(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(s)],
                                     capture_output=True, text=True).stdout.strip() or 3) for s in segs)
    if falas:
        return _join_voz(tmp, lst, total, falas, out)
    tracks = sorted(Path("/app/data/music").glob("*.mp3")) if Path("/app/data/music").exists() else []
    if tracks:
        import random
        track = random.choice(tracks)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-ss", "20", "-i", str(track), "-filter_complex",
                        f"[1:a]afade=t=in:d=0.5,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5,volume=0.8[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}",
                        "-movflags", "+faststart", str(out)], check=True, timeout=300)
        return ig_ready(out, out.with_name("ig_" + out.name))
    music = (f"aevalsrc='0.5*sin(2*PI*55*t)*exp(-12*mod(t,0.5))+0.12*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.25*t))"
             f"+0.06*sin(2*PI*329.6*t)*(0.5+0.5*sin(2*PI*0.5*t))+0.04*sin(2*PI*440*t)*exp(-8*mod(t,0.25))':s=44100:d={total:.2f}")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-f", "lavfi", "-i", music,
                    "-filter_complex", f"[1:a]afade=t=in:d=0.4,afade=t=out:st={max(total - 1.2, 0):.2f}:d=1.2,volume=0.55[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True, timeout=300)
    return ig_ready(out, out.with_name("ig_" + out.name))


def ig_ready(src: Path, dst: Path) -> bytes:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-c:v", "libx264", "-profile:v", "high",
                    "-level", "4.1", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k", "-movflags", "+faststart", str(dst)],
                   check=True, timeout=600)
    return dst.read_bytes()


def _name_card(name: str, platform: str) -> Image.Image:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (1280, 720), (24, 24, 28))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1280, 14), fill=accent)
    y = 300 - 50 * (len(textwrap.wrap(name.upper(), 18)[:3]) - 1)
    for ln in textwrap.wrap(name.upper(), 18)[:3]:
        d.text((640, y), ln, font=_font(92), fill=TEXT, anchor="mm")
        y += 108
    d.text((640, 620), platform, font=_font(48, "regular"), fill=accent, anchor="mm")
    return im


def _cover_img(url: str) -> Image.Image | None:
    try:
        return Image.open(io.BytesIO(httpx.get(url, timeout=30).content)).convert("RGB")
    except Exception:
        return None


FRASE_PLAT = {"EPIC GAMES": "grátis na Epic Games", "STEAM": "de graça na Steam", "GOG": "de graça no GOG",
              "AMAZON LUNA": "de graça no Amazon Luna", "PRIME GAMING": "grátis no Prime Gaming",
              "PS PLUS": "incluso no PlayStation Plus", "GAME PASS": "incluso no Game Pass"}


def _nome_falado(name: str) -> str:
    """Nome do jogo para a narração. Entre [[ ]] o serviço de voz não aplica sotaque de português ao nome inglês, encurta
    subtítulos ("...: 25th Anniversary Remaster") e lê siglas/romanos/números (F1 25, II, GTA)."""
    return "[[" + re.sub(r"\s+", " ", re.sub(r"[™®©\[\]]", "", name)).strip() + "]]"


def _por_semana(opcoes: list[str]) -> str:
    """Abertura/encerramento muda de semana em semana (o mesmo texto toda semana soa robô)."""
    import datetime as _dt
    return opcoes[_dt.date.today().isocalendar()[1] % len(opcoes)]


ABERTURAS_GRATIS = ["Jogos grátis da semana! Resgata antes que acabe.", "Olha só os jogos grátis dessa semana! Corre pra resgatar.",
                    "Tem jogo de graça pra pegar agora! Resgata antes que acabe."]
FECHAMENTOS_GRATIS = ["Salva e manda pro amigo gamer! Os links estão aqui na descrição.",
                      "Marca aquele amigo gamer! O link do grupo de ofertas tá no perfil.",
                      "Salva esse vídeo e chama o amigo gamer! Os links estão aqui na descrição."]
ABERTURAS_PROMO = ["Jogos em promoção na Steam essa semana!", "Olha só os jogos em promoção na Steam!", "Promoção na Steam! Anota aí os jogos dessa semana."]
FECHAMENTOS_PROMO = ["Qual você vai pegar? Comenta aí! O link do grupo de ofertas tá no perfil.",
                     "Qual desses você leva? Me conta nos comentários! Os links estão aqui na descrição."]


def _fala_gratis(g: dict, i: int, n: int) -> str:
    """Uma fala por jogo, com molde diferente de um para o outro (menos "lista lida")."""
    nome = _nome_falado(g["name"])
    plat = FRASE_PLAT.get(g["platform"], "grátis, " + g["platform"].title())
    if n > 2 and i == n - 1:
        return f"E fechando a lista: {nome}, {plat}!"
    modelos = ["Começando com {n}, {p}!", "Tem também {n}, {p}.", "{n}! {P}.", "Olha só: {n}, {p}!", "E mais um: {n}, {p}.",
               "Não perde {n}, {p}!", "{n}, {p}. Corre!"]
    return modelos[i % len(modelos)].format(n=nome, p=plat, P=plat[:1].upper() + plat[1:])


def _fala_promo(g: dict, i: int, n: int, preco: str) -> str:
    nome, pct = _nome_falado(g["name"]), g["pct"]
    if n > 2 and i == n - 1:
        return f"E fechando: {nome}, {pct}% de desconto, saindo por {preco}!"
    modelos = ["{n}, com {d}% de desconto, por {p}!", "{n} caiu pra {p}, são {d}% de desconto!", "Olha só: {n}, {d}% de desconto, por apenas {p}.",
               "{n}! Por {p}, com {d}% de desconto.", "Tem também {n}, {d}% de desconto, por {p}."]
    return modelos[i % len(modelos)].format(n=nome, d=pct, p=preco)


def _debug_dump(sincronia, textos: list[str], nome: str) -> None:
    """Com REEL_DEBUG_DIR definido, guarda as falas (wav), os instantes e os textos: dá para refazer só a mixagem sem gerar a voz de novo."""
    import json
    import os
    import shutil
    base = os.getenv("REEL_DEBUG_DIR")
    if not base or not sincronia:
        return
    d = Path(base) / nome
    d.mkdir(parents=True, exist_ok=True)
    for i, (arq, _m) in enumerate(sincronia):
        shutil.copy(arq, d / f"fala{i:02d}.wav")
    (d / "marcas.json").write_text(json.dumps({"marcas": [m for _p, m in sincronia], "textos": textos}, ensure_ascii=False), encoding="utf-8")


def _com_voz(tmp: Path, linhas: list[str]) -> list[tuple[Path, float]] | None:
    """Pede a narração ao serviço de voz e grava os wavs em tmp -> [(arquivo, segundos)] ou None (Reel sai mudo)."""
    from app import voz
    r = voz.narrar(linhas)
    if not r:
        return None
    out = []
    for i, (wav, seg) in enumerate(r):
        p = tmp / f"fala{i}.wav"
        p.write_bytes(wav)
        out.append((p, seg))
    return out


def build_free() -> tuple[bytes, list[dict]] | None:
    games = free_games()
    if len(games) < 2:
        return None
    with tempfile.TemporaryDirectory() as t:
        tmp, segs = Path(t), []
        textos = [_por_semana(ABERTURAS_GRATIS)] + [_fala_gratis(g, i, len(games)) for i, g in enumerate(games)] + [_por_semana(FECHAMENTOS_GRATIS)]
        falas = _com_voz(tmp, textos)
        cena = [(max(d + 0.6, base), d) for d, base in zip([s for _p, s in falas], [2.0] + [2.4] * len(games) + [2.2])] if falas else None
        cursor, marcas = 0.0, []
        segs.append(_segment(tmp, 0, cena[0][0] if cena else 2.2, None, still=_card("jogos", "grátis", "da semana", "pc • ps plus • game pass • luna")))
        cursor += cena[0][0] if cena else 2.2
        marcas.append(0.3)
        shown = []
        for i, g in enumerate(games, 1):
            dur = cena[i][0] if cena else 3.2
            st = steam_lookup(g["name"])  # trailer/capa da Steam serve até para jogos de console/assinatura
            clip = tmp / f"tr{i}.mp4"
            sub_txt = {"PS PLUS": "incluso no ps plus", "GAME PASS": "incluso no game pass",
                       "AMAZON LUNA": "grátis com prime / luna", "PRIME GAMING": "grátis com prime"}.get(g["platform"],
                                                                                              f"resgate grátis • {g['platform']}")
            ov = _overlay("resgate e jogue", g["name"], "GRÁTIS", sub_txt)
            marcas.append(cursor + 0.35)
            cursor += dur
            if st and trailer_clip(st["id"], clip, dur=dur):
                segs.append(_segment(tmp, i, dur, ov, clip=clip))
                shown.append(g)
            else:
                img = (_cover_img(st["tiny_image"].replace("capsule_231x87", "header")) if st else None) or \
                    (_cover_img(g["image"]) if g.get("image") else None)
                if img is None:  # sem capa: cartão com o nome do jogo (não deixa o jogo sumir do vídeo)
                    img = _name_card(g["name"], g["platform"])
                segs.append(_segment(tmp, i, dur if cena else 3.0, ov, still=img))
                shown.append(g)
        segs.append(_segment(tmp, 99, cena[-1][0] if cena else 2.5, None, still=_card("pegue", "antes que", "acabe!", "link do grupo na bio")))
        marcas.append(cursor + 0.35)
        sincronia = [(p, m) for (p, _s), m in zip(falas, marcas)] if falas else None
        _debug_dump(sincronia, textos, "gratis")
        return _join(tmp, segs, tmp / "free.mp4", sincronia), shown  # legenda = exatamente o que aparece no vídeo


def build_top5() -> tuple[bytes, list[dict]] | None:
    from app.games import steam_deals
    deals = [g for g in steam_deals(10) if g["price"] > 0]
    deals = list({g["name"]: g for g in deals}.values())[:5]
    if len(deals) < 3:
        return None
    with tempfile.TemporaryDirectory() as t:
        tmp, segs = Path(t), []
        from app.templates import brl
        textos = [_por_semana(ABERTURAS_PROMO)] + [_fala_promo(g, i, len(deals), brl(g["price"])) for i, g in enumerate(deals)] + [_por_semana(FECHAMENTOS_PROMO)]
        falas = _com_voz(tmp, textos)
        durs = [max(d + 0.6, base) for d, base in zip([s for _p, s in falas], [1.8] + [2.4] * len(deals) + [2.2])] if falas else None
        segs.append(_segment(tmp, 0, durs[0] if durs else 2.0, None, still=_card("jogos em", "promoção", "da semana", "steam • tempo limitado")))
        cursor, marcas = durs[0] if durs else 2.0, [0.3]
        for rank, g in enumerate(deals, 1):  # sem ranking (pedido do dono): todos com o mesmo peso
            appid = int(re.search(r"/app/(\d+)", g["url"]).group(1))
            ov = _overlay("em promoção agora", g["name"], f"-{g['pct']}%  {brl(g['price'])}", f"de {brl(g['old'])} na steam")
            clip = tmp / f"tr{rank}.mp4"
            dur = durs[rank] if durs else 2.8
            marcas.append(cursor + 0.35)
            cursor += dur
            if trailer_clip(appid, clip, dur=dur):
                segs.append(_segment(tmp, rank, dur, ov, clip=clip))
            else:
                img = _cover_img(g["image"]) or _name_card(g["name"], "STEAM")
                segs.append(_segment(tmp, rank, dur, ov, still=img))
        segs.append(_segment(tmp, 99, durs[-1] if durs else 2.4, None, still=_card("qual você", "vai pegar?", "comenta aí", "link do grupo na bio")))
        marcas.append(cursor + 0.35)
        sincronia = [(p, m) for (p, _s), m in zip(falas, marcas)] if falas else None
        _debug_dump(sincronia, textos, "promo")
        return _join(tmp, segs, tmp / "top5.mp4", sincronia), deals


# ---------------------------------------------------------------- publicação (aprovado pelo dono 06/10)
TAGS = "#jogos #games #pcgamer #playstation #xbox #steam #epicgames #techhammer"


def post_free_reel() -> None:
    from app import fila_reels
    from app.reels import _publish
    from app.social import enabled
    if not enabled():
        return
    if fila_reels.publicar_tipo("gratis"):  # Reel pronto do PC (voz + trailers)
        return
    r = build_free()
    if not r:
        log.info("reel_skip", kind="gratis", reason="poucos jogos")
        return
    video, games = r
    lines = ["🆓 JOGOS GRÁTIS DA SEMANA — resgate antes que acabe!", ""]
    lines += [f"• {g['name']} — {g['platform'].title()}" for g in games]
    lines += ["", "💾 Salva e manda pro amigo gamer!", "📲 Links no nosso grupo de ofertas (link na bio)", "", TAGS]
    tl = ["🆓 Jogos grátis da semana:"] + [f"• {g['name'][:35]} ({g['platform'].title()})" for g in games[:8]]
    done = _publish(video, "\n".join(lines), "\n".join(tl))
    if done:
        from app.games import registrar_destaques
        registrar_destaques(games, "gratis")
    log.info("reel_posted", kind="gratis", nets=done)


def post_promo_reel() -> None:
    from app import fila_reels
    from app.reels import _publish
    from app.social import enabled
    from app.templates import brl
    if not enabled():
        return
    if fila_reels.publicar_tipo("promo"):
        return
    r = build_top5()
    if not r:
        log.info("reel_skip", kind="promo", reason="poucos jogos")
        return
    video, deals = r
    lines = ["🎮 JOGOS EM PROMOÇÃO DA SEMANA — por tempo limitado!", ""]
    lines += [f"• {g['name']} — {brl(g['price'])} (-{g['pct']}%)" for g in deals]
    lines += ["", "💬 Qual você vai pegar? Comenta aí!", "🔧 PC lento pra rodar? A TechHammer faz upgrade e manutenção.", "", TAGS]
    tl = ["🎮 Jogos em promoção:"] + [f"• {g['name'][:30]}: {g['url']}" for g in deals]
    done = _publish(video, "\n".join(lines), "\n".join(tl))
    if done:
        from app.games import registrar_destaques
        registrar_destaques(deals, "reel")
    log.info("reel_posted", kind="promo", nets=done)
