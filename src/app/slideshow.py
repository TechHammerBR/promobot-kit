"""Slides (imagens) -> REEL em vídeo com música de fundo (15/10/2026, ideia do dono: "reel propaga mais que foto").

Cada imagem entra com um leve zoom, sobre fundo desfocado 9:16, com transição suave; música livre de direitos de data/music
(ou /srv/cache/music) com volume baixo e fade no fim. Sem IA, só ffmpeg (roda no Wyse, prioridade baixa).
Uso (teste): python -m app.slideshow <saida.mp4> <img1.jpg> <img2.jpg> ...
"""
import random
import subprocess
import sys
from pathlib import Path

PASTAS_MUSICA = (Path("/srv/cache/music"), Path("/opt/promobot/data/music"))
FADE = 0.45  # segundos de transição


def musica() -> Path | None:
    from app import musica as _m
    return _m.escolher(30.0)[0]  # rodízio


def slides_para_reel(imagens: list[Path], saida: Path, duracoes: list[float] | None = None, faixa: Path | None = None) -> Path:
    n = len(imagens)
    duracoes = duracoes or [3.0] * n
    cmd = ["nice", "-n", "19", "ffmpeg", "-v", "error", "-y"]
    for img, d in zip(imagens, duracoes):
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{d + FADE:.2f}", "-i", str(img)]
    faixa = faixa or musica()
    if faixa:
        cmd += ["-stream_loop", "-1", "-i", str(faixa)]
    f = []
    for i, d in enumerate(duracoes):
        dur = d + FADE
        f.append(f"[{i}:v]split[a{i}][b{i}];"
                 f"[a{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:6,eq=brightness=-0.18[bg{i}];"
                 f"[b{i}]scale=w='trunc(1080*(1+0.045*t/{dur:.2f})/2)*2':h=-2:eval=frame[fg{i}];"
                 f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p[v{i}]")
    ultimo, acumulado = "v0", duracoes[0]
    for i in range(1, n):
        f.append(f"[{ultimo}][v{i}]xfade=transition=fade:duration={FADE}:offset={acumulado:.2f}[x{i}]")
        ultimo, acumulado = f"x{i}", acumulado + duracoes[i]
    total = sum(duracoes) + FADE
    cmd += ["-filter_complex", ";".join(f), "-map", f"[{ultimo}]"]
    if faixa:
        cmd += ["-map", f"{n}:a", "-af", f"volume=0.35,afade=t=in:d=0.6,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5", "-c:a", "aac",
                "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-t", f"{total:.2f}", "-movflags", "+faststart", str(saida)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"slideshow falhou: {r.stderr[-400:]}")
    return saida


if __name__ == "__main__":
    saida, *imgs = sys.argv[1:]
    paths = [Path(i) for i in imgs]
    tempos = [2.6] + [3.8] * (len(paths) - 3) + [3.0, 2.6] if len(paths) >= 4 else None  # capa, cartões, fontes, chamada
    print(slides_para_reel(paths, Path(saida), tempos))
