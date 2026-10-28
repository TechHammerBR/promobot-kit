"""Guardião: checa a saúde de tudo a cada 5 min (chamado por scripts/guardian.sh no host).

Saída (stdout, 1 linha por ação para o host executar): RESTART <serviço>. Alertas vão ao dono (WhatsApp próprio /
Telegram) sem repetir o mesmo problema por ALERT_REPEAT_H horas; avisa também quando resolve.
"""
import json
import shutil
from datetime import datetime, timedelta

import httpx
from sqlalchemy import func, select

from app import control
from app.config import DATA_DIR, settings
from app.db import Offer, SessionLocal, now
from app.log import log

STATE = DATA_DIR / "guardian_state.json"
ALERT_REPEAT_H = 6
RESTART_MIN_MIN = 60  # minutos mínimos entre dois reinícios do mesmo serviço
TZ = control.TZ


def _get(url: str, **kw):
    try:
        return httpx.get(url, timeout=kw.pop("timeout", 20), **kw)
    except Exception:
        return None


def checks() -> tuple[dict[str, str], list[str]]:
    """Retorna (problemas {chave: mensagem}, serviços a reiniciar)."""
    problems, restart = {}, []
    hour = datetime.now(TZ).hour
    from app.pipeline import hora_ativa
    active = hora_ativa(hour)

    r = _get(f"{settings.wa_url}/status")
    if r is None:
        problems["wa_down"] = "Conector do WhatsApp não responde (vou reiniciar)."
        restart.append("wa")
    elif not r.json().get("connected"):
        problems["wa_logout"] = ("WhatsApp do robô DESCONECTADO. Peça um código novo ao Claude "
                                 "(ou: WhatsApp > Aparelhos conectados > Conectar com número de telefone).")

    r = _get("http://linkgen:8000/health", timeout=40)
    if r is None or r.status_code != 200:
        problems["linkgen_down"] = "Gerador de links do Mercado Livre não responde (vou reiniciar)."
        restart.append("linkgen")
    elif not r.json().get("logged_in", True) and not __import__("app.collectors.base", fromlist=["x"]).ml_paused():
        problems["ml_login"] = ("Login do Mercado Livre EXPIROU: os links de afiliado param. "
                                "Refaça pelo atalho 'Navegador do Servidor' no PC.")
    if r is not None and r.status_code == 200 and settings.ali_enabled and not settings.ali_app_key and r.json().get("ali_logged_in") is False:
        problems["ali_login"] = ("Login do AliExpress Portals CAIU: ofertas do AliExpress pausadas. "
                                 "Entre de novo pelo atalho 'Navegador do Servidor' no PC (aba do Portals).")

    if settings.social_enabled and settings.meta_page_token:
        r = _get("https://graph.facebook.com/v21.0/me", params={"access_token": settings.meta_page_token})
        if r is not None and r.status_code in (400, 401, 403):
            problems["meta_token"] = ("Conexão com Instagram/Facebook CAIU (token da Meta inválido): "
                                     "posts nas redes pararam. Peça ao Claude para reconectar.")
    r = _get(f"{settings.ollama_url}/api/tags")
    if r is None or r.status_code != 200:
        problems["ollama_down"] = "IA local (Ollama) não responde: posts saem sem título curto e fotos não são validadas."

    if active and not control.paused():
        with SessionLocal() as s:
            last = s.scalar(select(func.max(Offer.posted_at)))
            queue = s.scalar(select(func.count(Offer.id)).where(Offer.status == "new")) or 0
            fails = s.scalars(select(Offer.status).where(Offer.status.in_(["posted", "failed"]))
                              .order_by(Offer.id.desc()).limit(3)).all()
        idle_min = (now() - last).total_seconds() / 60 if last else 9999
        started_today = datetime.now(TZ).replace(hour=settings.active_hour_start, minute=0)
        if started_today > datetime.now(TZ):  # madrugada: o turno começou ontem
            started_today -= timedelta(days=1)
        if idle_min > max(45, settings.interval_max * 6) and datetime.now(TZ) - started_today > timedelta(minutes=60):
            if queue == 0:
                from app.diagnose import diagnose
                problems["no_offers"] = f"Sem posts há {int(idle_min)} min.\n" + diagnose()
            else:
                problems["bot_stuck"] = f"Robô sem postar há {int(idle_min)} min com {queue} ofertas na fila (vou reiniciar)."
                restart.append("bot")
        if len(fails) == 3 and all(x == "failed" for x in fails):
            problems["post_failing"] = "Os 3 últimos envios FALHARAM (WhatsApp ou login do ML)."

    disk = shutil.disk_usage("/app/data")
    if disk.used / disk.total > 0.85:
        problems["disk"] = f"Disco do servidor com {disk.used * 100 // disk.total}% usado."
    return problems, restart


def run() -> None:
    from app.publisher import alert
    problems, restart = checks()
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        state = {}
    t = datetime.now(TZ)
    for key, msg in problems.items():
        last = state.get(key)
        if not last or t - datetime.fromisoformat(last) > timedelta(hours=ALERT_REPEAT_H):
            alert(f"🛡️ {msg}")
            state[key] = t.isoformat()
    for key in [k for k in state if k not in problems and not k.startswith("_")]:
        alert(f"✅ Resolvido: {key}")
        del state[key]
    # não reinicia o MESMO serviço em loop (08/10: depois de uma queda de energia a IA, agora só na CPU, demora para o 1º post e o guardião reiniciava o robô a cada 5 min)
    ult = state.setdefault("_reinicio", {})
    permitidos = []
    for svc in dict.fromkeys(restart):
        quando = ult.get(svc)
        if quando and t - datetime.fromisoformat(quando) < timedelta(minutes=RESTART_MIN_MIN):
            log.info("guardian_reinicio_adiado", service=svc)
            continue
        ult[svc] = t.isoformat()
        permitidos.append(svc)
    STATE.write_text(json.dumps(state))
    log.info("guardian", problems=list(problems), restart=permitidos)
    for svc in permitidos:
        print(f"RESTART {svc}")


def daily_report() -> None:
    """Resumo do dia para o dono (23h)."""
    from app.coupon_codes import active_codes
    from app.pipeline import posts_today
    from app.publisher import alert
    with SessionLocal() as s:
        since = now() - timedelta(hours=24)
        failed = s.scalar(select(func.count(Offer.id)).where(Offer.status == "failed", Offer.created_at >= since)) or 0
        top = s.scalars(select(Offer).where(Offer.status == "posted", Offer.posted_at >= since)
                        .order_by(Offer.score.desc()).limit(3)).all()
        codes = len(active_codes(s))
    problems, _ = checks()
    lines = [f"📊 Resumo TechHammer {datetime.now(TZ):%d/%m}",
             f"Posts hoje: {posts_today()} | falhas 24h: {failed} | cupons com código: {codes}",
             "Destaques: " + "; ".join(o.title[:40] for o in top) if top else "Sem posts hoje.",
             "Saúde: tudo ok ✅" if not problems else "Atenção: " + " | ".join(problems.values())]
    alert("\n".join(lines))


if __name__ == "__main__":
    run()
