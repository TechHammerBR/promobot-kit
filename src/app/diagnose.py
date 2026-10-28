"""Diagnóstico em linguagem simples: POR QUE o robô não está postando e o que fazer (06/10).

Usado por `ctl diag` e pelo guardião no alerta no_offers (data/alertas.log).
Determinístico (sem IA inventando): lê fila, motivos de rejeição, saúde das fontes, pausa, WhatsApp, linkgen, Ollama.
"""
from collections import Counter
from datetime import timedelta

import httpx
from sqlalchemy import func, select

from app import control
from app.config import settings
from app.db import Offer, SessionLocal, SourceHealth, now

GROUPS = [  # motivo (trecho) -> explicação curta
    ("desconto", "desconto baixo ou sem preço antigo"),
    ("foto", "foto reprovada (propaganda/pessoa/sem foto)"),
    ("IA curadoria", "IA achou o produto fraco/sem marca"),
    ("duplicada", "repetida"),
    ("já publicado", "já publicado nos últimos dias"),
    ("palavra proibida", "palavra proibida"),
]


def _get(url: str):
    try:
        return httpx.get(url, timeout=20)
    except Exception:
        return None


def diagnose(hours: int = 6) -> str:
    since = now() - timedelta(hours=hours)
    with SessionLocal() as s:
        last = s.scalar(select(func.max(Offer.posted_at)))
        queue = s.scalar(select(func.count(Offer.id)).where(Offer.status == "new")) or 0
        posted = s.scalar(select(func.count(Offer.id)).where(Offer.status == "posted", Offer.posted_at >= since)) or 0
        reasons = s.scalars(select(Offer.reason).where(Offer.status.in_(["rejected", "failed"]), Offer.created_at >= since)).all()
        by_src = Counter(s.scalars(select(Offer.source).where(Offer.created_at >= since)).all())
        health = s.scalars(select(SourceHealth)).all()
    idle = int((now() - last).total_seconds() // 60) if last else None
    lines = [f"🩺 *Diagnóstico* (últimas {hours}h)",
             f"• Último post: há {idle} min" if idle is not None else "• Nenhum post ainda",
             f"• Posts: {posted} | Fila esperando: {queue}"]
    grouped = Counter()
    for r in reasons:
        g = next((txt for key, txt in GROUPS if key in (r or "")), "outros")
        grouped[g] += 1
    if grouped:
        lines.append("• Reprovadas: " + ", ".join(f"{n} {g}" for g, n in grouped.most_common(4)))
    lines.append("• Coletadas por fonte: " + (", ".join(f"{k} {v}" for k, v in by_src.most_common()) or "nenhuma"))
    from app.collectors.base import ml_paused
    skip = ("demo", "mercadolivre") if ml_paused() else ("demo",)
    bad = [h for h in health if h.consecutive_failures and h.source not in skip]
    for h in bad:
        lines.append(f"• ⚠️ Fonte {h.source} falhando ({h.consecutive_failures}x): {(h.last_error or '')[:70]}")
    # serviços
    issues = []
    if control.paused():
        issues.append("o robô está PAUSADO (`ctl retomar`)")
    w = _get(f"{settings.wa_url}/status")
    if w is None or not w.json().get("connected"):
        issues.append("WhatsApp desconectado (`ctl codigo-wa` gera o código para reconectar)")
    lg = _get("http://linkgen:8000/health")
    if lg is None:
        issues.append("gerador de links fora do ar (o guardião religa sozinho em até 10 min)")
    elif settings.ali_enabled and not settings.ali_app_key and lg.json().get("ali_logged_in") is False:
        issues.append("login do AliExpress caiu (entre pelo atalho Navegador do Servidor)")
    if _get(f"{settings.ollama_url}/api/tags") is None:
        issues.append("IA local fora do ar (fotos não são validadas)")
    # conclusão
    lines.append("")
    if issues:
        lines.append("❗ Causa provável: " + "; ".join(issues) + ".")
    elif queue == 0:
        top = grouped.most_common(1)[0][0] if grouped else "poucas ofertas coletadas"
        lines.append(f"❗ Causa provável: falta de oferta boa — a fila está vazia e o principal motivo de reprovação foi: {top}.")
        lines.append("💡 Sugestões: `ctl desconto 25` (aceita mais ofertas) ou esperar a próxima coleta "
                     f"(a cada {settings.collect_interval_min} min).")
    elif idle is not None and idle > 60:
        lines.append("❗ Há ofertas na fila mas nada saiu: o guardião vai reiniciar o robô. Se continuar, use `ctl postar`.")
    else:
        lines.append("✅ Tudo funcionando: posts saindo normalmente.")
    return "\n".join(lines)
