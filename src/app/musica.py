"""Música dos Reels com RODÍZIO: não repete as últimas faixas usadas por nenhum Reel/Story/carrossel e começa num ponto diferente da faixa.

Faixas: /srv/cache/music/*.mp3 (Pixabay/Mixkit, uso comercial sem crédito; ver LICENCA.txt). Histórico em data/music_history.json."""
import json
import random
import subprocess
from pathlib import Path

from app.config import DATA_DIR

PASTAS = (Path("/srv/cache/music"), Path("/app/data/music"), DATA_DIR / "music")
HIST = DATA_DIR / "music_history.json"
MAX_RECENTES = 8  # quantas faixas "descansam" depois de usadas (limitado a n-1)


def faixas() -> list[Path]:
    return sorted({f for p in PASTAS if p.exists() for f in p.glob("*.mp3")})


def _historico() -> list[str]:
    try:
        return list(json.loads(HIST.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return []


def _duracao(f: Path) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True, timeout=20)
        return float(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def escolher(total: float = 30.0, registrar: bool = True) -> tuple[Path | None, float]:
    """-> (faixa, segundo inicial). A faixa não é uma das últimas usadas; o início é aleatório (de 8 em 8 s) se a faixa for longa o bastante."""
    fs = faixas()
    if not fs:
        return None, 0.0
    h = _historico()
    n = max(1, min(len(fs) - 1, MAX_RECENTES))
    pool = [f for f in fs if f.name not in h[-n:]] or fs
    f = random.choice(pool)
    folga = _duracao(f) - total - 6
    ss = float(random.randrange(0, int(folga) // 8 + 1) * 8) if folga >= 8 else 0.0
    if registrar:
        try:
            HIST.write_text(json.dumps((h + [f.name])[-60:], ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return f, ss
