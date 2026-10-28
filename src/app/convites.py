"""Convite diário dos contatos do dono para os grupos (decisão do dono em 14/10/2026, ciente do risco de bloqueio do número).

O conector `wa` escolhe os próximos contatos ainda não convidados (pula quem já está nos grupos) e envia devagar.
Acompanhar: `curl -s 127.0.0.1:3000/convite-status` (só contagens). Desligar: CONVITE_ENABLED=false no .env.
"""
from pathlib import Path

import httpx

from app.config import settings
from app.log import log

TEXTO = Path(__file__).parent / "assets" / "convite.txt"


def enviar_lote(n: int | None = None) -> dict:
    grupos = [g for g in ("", settings.lar_whatsapp_group_id) if g]
    r = httpx.post(f"{settings.wa_url}/convite-lote", timeout=180, json={
        "text": TEXTO.read_text(encoding="utf-8").strip(), "n": n or settings.convite_por_dia, "skip_groups": grupos})
    resp = r.json()
    log.info("convite_lote", status=r.status_code, **{k: v for k, v in resp.items() if k != "error"})
    return resp
