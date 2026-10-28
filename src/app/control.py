"""Painel de controle compartilhado entre o bot e o serviço `ops` (ações seguras da IA local).

Arquivo data/control.json (escrita atômica). O bot lê a cada rodada de publicação:
- paused_until: ISO; enquanto no futuro, não publica
- post_now: quantos posts fazer já (1 por minuto), ignorando o intervalo normal
- coupons_now: true = posta cupons na próxima rodada
- overrides: ajustes de settings (só chaves de ALLOWED, com limites)
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import DATA_DIR, settings

TZ = ZoneInfo("America/Sao_Paulo")
FILE = DATA_DIR / "control.json"
# chave -> (mínimo, máximo)
ALLOWED = {
    "interval_min": (3, 60), "interval_max": (3, 60),
    "peak_interval_min": (3, 60), "peak_interval_max": (3, 60),
    "min_discount_pct": (10, 80), "daily_post_limit": (10, 300),
}


def load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, FILE)


def update(**changes) -> dict:
    data = load()
    data.update(changes)
    save(data)
    return data


def apply_overrides(data: dict | None = None) -> None:
    for k, v in (data if data is not None else load()).get("overrides", {}).items():
        if k in ALLOWED:
            lo, hi = ALLOWED[k]
            setattr(settings, k, type(getattr(settings, k))(min(max(float(v), lo), hi)))


def paused(data: dict | None = None) -> bool:
    until = (data if data is not None else load()).get("paused_until")
    return bool(until) and datetime.fromisoformat(until) > datetime.now(TZ)
