"""Reels automáticos (06/10) — o formato que mais traz seguidores novos. Instagram (Reels) + Página (vídeo) + Threads.

Vídeo vertical 1080x1920, ~12–18 s: capa chamativa -> cenas (zoom suave + transição) -> chamada final pro grupo.
Trilha: batida leve SINTETIZADA pelo ffmpeg (sem direitos autorais). Feito 100% no servidor (PIL + ffmpeg), sem IA externa.
- Ofertas do dia: as 3 melhores ofertas postadas nas últimas 24h (REEL_OFFERS_TIME).
- Jogos: até 5 jogos em promoção, logo depois do carrossel de jogos (seg e qui).
Instagram exige o vídeo numa URL pública: o vídeo sobe primeiro como vídeo da Página e usamos a URL dele.
"""
import io
import json
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.db import Offer, SessionLocal, now
from app.log import log
from app.media import product_jpeg
from app.social import _api, enabled
from app.social_art import BG, MUTED, TEXT, _brand, _font, _hex, render_art

W, H, FPS = 1080, 1920, 30
XF = 0.4  # duração da transição
TAGS = "#ofertas #promoção #tecnologia #pcgamer #saopaulo #zonasulsp #techhammer"


def _scene_text(top: str, big: str, accent_line: str, bottom: str = "") -> Image.Image:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand(d, W, 200, accent)
    d.text((W / 2, 700), top.upper(), font=_font(56, "regular"), fill=MUTED, anchor="mm")
    y = 860
    for ln in big.upper().split("\n"):
        d.text((W / 2, y), ln, font=_font(130), fill=TEXT, anchor="mm")
        y += 150
    d.text((W / 2, y + 40), accent_line.upper(), font=_font(110), fill=accent, anchor="mm")
    if bottom:
        d.rounded_rectangle((W / 2 - 380, 1560, W / 2 + 380, 1680), radius=60, outline=accent, width=5)
        d.text((W / 2, 1620), bottom.upper(), font=_font(46), fill=TEXT, anchor="mm")
    return im


def _fit_vertical(img: Image.Image) -> Image.Image:
    """Coloca uma arte 1080x1350 (feed) no centro de um quadro 1080x1920."""
    if img.size == (W, H):
        return img
    im = Image.new("RGB", (W, H), BG)
    img = img.resize((W, int(img.height * W / img.width)))
    im.paste(img, (0, (H - img.height) // 2))
    return im


def _render_leve(scenes: list[tuple[Image.Image, float]]) -> bytes:
    """Wyse: cada cena vira um clipe curto (fade de entrada/saída), um de cada vez; depois junta e põe a música."""
    import random
    with tempfile.TemporaryDirectory(dir="/srv/cache") as tmp:
        tmp = Path(tmp)
        lista = []
        for i, (img, dur) in enumerate(scenes):
            foto, clip = tmp / f"s{i}.jpg", tmp / f"c{i}.mp4"
            img.convert("RGB").resize((W, H)).save(foto, quality=92)
            subprocess.run(["nice", "-n", "10", "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", f"{dur}", "-i", str(foto),
                            "-vf", f"fps={FPS},format=yuv420p,fade=t=in:st=0:d=0.25,fade=t=out:st={dur - 0.25:.2f}:d=0.25",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-threads", "1", "-x264-params", "rc-lookahead=5:ref=1:sync-lookahead=0", str(clip)],
                           check=True, timeout=300)
            lista.append(f"file '{clip}'")
        (tmp / "lista.txt").write_text("\n".join(lista))
        total = sum(d for _, d in scenes)
        out = tmp / "reel.mp4"
        from app import musica
        faixa, ini = musica.escolher(total)
        audio = ["-ss", f"{ini:g}", "-i", str(faixa)] if faixa else ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total}"]
        subprocess.run(["nice", "-n", "10", "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "lista.txt"),
                        *audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-af", f"atrim=0:{total:.2f},afade=t=in:d=0.5,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5,volume=0.8",
                        "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)],
                       check=True, timeout=300)
        return out.read_bytes()


def _render(scenes: list[tuple[Image.Image, float]]) -> bytes:
    """Cenas (imagem, segundos) -> MP4 H.264 com zoom suave, transições e trilha sintetizada."""
    if settings.reel_leve:
        return _render_leve(scenes)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        args, filters = [], []
        for i, (img, dur) in enumerate(scenes):
            p = tmp / f"s{i}.jpg"
            img.convert("RGB").save(p, quality=92)
            args += ["-loop", "1", "-t", f"{dur}", "-i", str(p)]
            frames = int(dur * FPS)
            if settings.reel_leve:  # Wyse: sem zoom (zoompan em 2x custa minutos no Atom)
                filters.append(f"[{i}:v]scale={W}:{H},fps={FPS},format=yuv420p,setsar=1[v{i}]")
                continue
            # zoom-in leve e contínuo (efeito "Ken Burns") — dá vida à imagem parada
            filters.append(f"[{i}:v]scale={W * 2}:{H * 2},zoompan=z='min(zoom+0.0009,1.10)':d={frames}"
                           f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1[v{i}]")
        # transições entre cenas
        last, offset = "v0", 0.0
        for i in range(1, len(scenes)):
            offset += scenes[i - 1][1] - XF
            filters.append(f"[{last}][v{i}]xfade=transition=slideleft:duration={XF}:offset={offset:.2f}[x{i}]")
            last = f"x{i}"
        total = sum(d for _, d in scenes) - XF * (len(scenes) - 1)
        # trilha: kick a 120 bpm + baixo suave + "pad" (tudo gerado, sem direitos autorais)
        music = (f"aevalsrc='0.55*sin(2*PI*55*t)*exp(-12*mod(t,0.5))"
                 f"+0.10*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.25*t))"
                 f"+0.05*sin(2*PI*329.6*t)*(0.5+0.5*sin(2*PI*0.5*t))':s=44100:d={total:.2f}")
        from app import musica
        faixa, ini = musica.escolher(total) if settings.reel_leve else (None, 0.0)
        if faixa:  # música licenciada (uso comercial sem crédito), em rodízio
            args += ["-ss", f"{ini:g}", "-i", str(faixa)]
            filters.append(f"[{len(scenes)}:a]atrim=0:{total:.2f},afade=t=in:d=0.5,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5,"
                           f"volume=0.8[a]")
        else:
            filters.append(f"{music},afade=t=in:d=0.5,afade=t=out:st={max(total - 1.2, 0):.2f}:d=1.2,volume=0.6[a]")
        out = tmp / "reel.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(filters),
               "-map", f"[{last}]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
               "-t", f"{total:.2f}", str(out)]
        subprocess.run(cmd, check=True, timeout=600)
        return out.read_bytes()


def _publish(video: bytes, caption: str, threads_text: str, na_grade: bool = True, marcar: list[str] | None = None, capa: bytes | None = None) -> list[str]:
    """Instagram Reels (upload direto, resumable) + vídeo na Página + Threads (URL do vídeo da Página)."""
    done, ig_url = [], None
    for tentativa in range(1, 4):  # o upload do Instagram falha de vez em quando (400 ProcessingFailedError, 23-24/10): tenta até 3x
        if "instagram" in done:
            break
        if tentativa > 1:
            time.sleep(150)
        try:  # Instagram: upload direto dos bytes (a URL do vídeo da Página dava erro 2207076)
            extra = {"user_tags": json.dumps([{"username": u} for u in marcar])} if marcar else {}
            if capa:  # capa própria: a arte sobe como foto oculta da Página e o Instagram baixa pela URL
                try:
                    from app.social import _upload_hidden
                    extra["cover_url"] = _upload_hidden(capa)[1]
                except Exception as e:  # noqa: BLE001
                    log.warning("reel_capa_ig_falhou", error=str(e)[:200])
            try:
                c = _api("POST", f"{settings.meta_ig_id}/media", media_type="REELS", upload_type="resumable", caption=caption,
                         share_to_feed="true" if na_grade else "false", **extra)
            except Exception as e:
                if not extra:
                    raise
                log.warning("reel_extra_recusado", error=str(e)[:200], campos=list(extra))  # marcação/capa recusada: sai sem eles (o @ continua na legenda)
                c = _api("POST", f"{settings.meta_ig_id}/media", media_type="REELS", upload_type="resumable", caption=caption,
                         share_to_feed="true" if na_grade else "false")
            r = httpx.post(c["uri"], content=video, timeout=600, headers={
                "Authorization": f"OAuth {settings.meta_page_token}", "offset": "0", "file_size": str(len(video))})
            r.raise_for_status()
            for _ in range(60):
                st = _api("GET", c["id"], fields="status_code,status")
                if st.get("status_code") == "FINISHED":
                    break
                if st.get("status_code") == "ERROR":
                    raise RuntimeError(st.get("status"))
                time.sleep(5)
            ig_media = _api("POST", f"{settings.meta_ig_id}/media_publish", creation_id=c["id"])["id"]
            done.append("instagram")
            # Threads não tem upload direto e não consegue baixar o vídeo oculto da Página:
            # usa a URL pública do Reel recém-publicado no Instagram
            for _ in range(10):
                ig_url = _api("GET", ig_media, fields="media_url").get("media_url")
                if ig_url:
                    break
                time.sleep(6)
        except Exception as e:
            log.error("reel_failed", net="instagram", tentativa=tentativa, error=str(e)[:300])
            if tentativa == 3:
                from app.publisher import alert
                alert("Reel não subiu no Instagram após 3 tentativas (subiu nas outras redes): " + str(e)[:120])
    url = None
    try:
        fb = _api("POST", f"{settings.meta_page_id}/videos", description=caption,
                  files={"source": ("reel.mp4", video, "video/mp4")})
        done.append("facebook")
        if capa:  # miniatura preferida do vídeo na Página
            try:
                _api("POST", f"{fb['id']}/thumbnails", is_preferred="true", files={"source": ("capa.jpg", capa, "image/jpeg")})
            except Exception as e:  # noqa: BLE001
                log.warning("reel_capa_fb_falhou", error=str(e)[:200])
        for _ in range(40):
            url = _api("GET", fb["id"], fields="source").get("source")
            if url:
                break
            time.sleep(6)
    except Exception as e:
        log.error("reel_failed", net="facebook", error=str(e)[:300])
    from app import threads
    url = ig_url or url
    if url and threads.enabled():
        try:
            t = threads._api("POST", "me/threads", media_type="VIDEO", video_url=url, text=threads_text[:500])
            for _ in range(60):
                stt = threads._api("GET", t["id"], fields="status").get("status")
                if stt == "FINISHED":
                    break
                if stt == "ERROR":
                    raise RuntimeError("Threads recusou o vídeo")
                time.sleep(5)
            threads._api("POST", "me/threads_publish", creation_id=t["id"])
            done.append("threads")
        except Exception as e:
            log.error("reel_failed", net="threads", error=str(e)[:300])
    return done


def offers_reel() -> None:
    if not enabled():
        return
    from app import fila_reels
    if fila_reels.publicar_tipo("ofertas"):  # Reel pronto feito no PC (fila); sem ele o Wyse monta o simples (plano B)
        return
    with SessionLocal() as s:
        rows = s.scalars(select(Offer).where(Offer.status == "posted", Offer.old_price.isnot(None), Offer.canal == "tech",
                                             Offer.posted_at >= now() - __import__("datetime").timedelta(hours=24))
                         .order_by(Offer.score.desc())).all()
        picks = []
        for o in rows:
            if o.price and o.old_price and o.old_price > o.price:
                photo = product_jpeg(o.image_url)
                if photo:
                    s.expunge(o)
                    picks.append((o, photo))
            if len(picks) == 5:
                break
    if len(picks) < 2:
        log.info("reel_skip", kind="ofertas", reason="poucas ofertas")
        return
    scenes = [(_scene_text("as melhores de hoje", "ofertas\ndo dia", "tecnologia", "assista até o fim"), 2.2)]
    scenes += [(Image.open(io.BytesIO(render_art(o, ph, "story"))), 3.2) for o, ph in picks]
    scenes.append((_scene_text("todo dia tem mais", "entra no\ngrupo", "é grátis", "link na bio"), 2.6))
    video = _render(scenes)
    lines = ["🔥 AS MELHORES OFERTAS DE HOJE — por tempo limitado!", ""]
    lines += [f"• {(o.post_title or o.title)[:60]} — R$ {o.price:.2f}".replace(".", ",") for o, _ in picks]
    from app.templates import chamada_grupos
    lines += ["", chamada_grupos(False), "💬 Qual você levaria?", "", TAGS]
    tlines = ["🔥 As melhores ofertas de hoje:"] + [f"• {(o.post_title or o.title)[:45]}: {o.affiliate_url or o.url}" for o, _ in picks]
    from app.templates import grupos_threads
    tlines.insert(1, grupos_threads())  # logo depois do título: o Threads corta em 500 caracteres e os grupos não podem ser os cortados
    done = _publish(video, "\n".join(lines), "\n".join(tlines), na_grade=False)  # dono: venda fora da grade do perfil
    log.info("reel_posted", kind="ofertas", nets=done)


def games_reel() -> None:
    if not enabled():
        return
    from app.games import _slide, epic_free, steam_deals
    games = list({g["name"]: g for g in epic_free()[:2] + steam_deals(6)}.values())[:5]
    if len(games) < 3:
        log.info("reel_skip", kind="jogos", reason="poucos jogos")
        return
    scenes = [(_scene_text("steam • epic games", "jogos em\npromoção", "essa semana", "corre que acaba"), 2.2)]
    scenes += [(_fit_vertical(Image.open(io.BytesIO(_slide(g, i + 1, len(games))))), 2.8) for i, g in enumerate(games)]
    scenes.append((_scene_text("toda semana tem mais", "segue a\ntechhammer", "e não perca", "link do grupo na bio"), 2.6))
    video = _render(scenes)
    from app.templates import brl
    lines = ["🎮 JOGOS EM PROMOÇÃO ESSA SEMANA — por tempo limitado!", ""]
    lines += [f"• {g['name']} — {'GRÁTIS' if g['price'] == 0 else brl(g['price'])} na {g['store']}" for g in games]
    lines += ["", "💾 Salva e manda pro amigo gamer!", "🔧 PC lento pra rodar? A TechHammer faz upgrade e manutenção.", "",
              "#steam #epicgames #jogosgratis #pcgamer #saopaulo #techhammer"]
    tlines = ["🎮 Jogos em promoção:"] + [f"• {g['name'][:30]}: {g['url']}" for g in games]
    done = _publish(video, "\n".join(lines), "\n".join(tlines))
    log.info("reel_posted", kind="jogos", nets=done)
