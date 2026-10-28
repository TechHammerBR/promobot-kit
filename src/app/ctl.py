"""Controle do robô pela linha de comando — uso do Claude/administrador (sem servidor HTTP e sem IA de conversa).

    cd /opt/apps/promobot && docker compose exec -T bot python -m app.ctl <comando> [argumentos]

Consulta:  status | diag | fila [n] | buscar TERMO | cupons-ativos | alertas [n] | relatorio
Ações:     pausar [min] | retomar | postar [n] | cupons | desconto N | limite N | intervalo MIN [MAX] | codigo-wa
Conteúdo:  tabela | preco "<serviço> <valor>" | edu [tema] | servico "<descrição>" | aprovar | cancelar

Tudo passa por app.control: o bot executa na próxima rodada (até ~1 min). Avisos do sistema ficam em data/alertas.log.
"""
import json
import sys
from datetime import datetime, timedelta

import httpx
from sqlalchemy import func, select

from app import control
from app.config import DATA_DIR, settings
from app.db import Coupon, Offer, SessionLocal, now


def _wa_connected() -> bool:
    try:
        return bool(httpx.get(f"{settings.wa_url}/status", timeout=10).json().get("connected"))
    except Exception:
        return False


def s2_fila_lar() -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count(Offer.id)).where(Offer.status == "new", Offer.canal == "lar")) or 0


def status() -> dict:
    from app.pipeline import posts_today
    c = control.load()
    control.apply_overrides(c)
    with SessionLocal() as s:
        queue = s.scalar(select(func.count(Offer.id)).where(Offer.status == "new", Offer.canal == "tech")) or 0
        last = s.scalars(select(Offer).where(Offer.status == "posted").order_by(Offer.posted_at.desc()).limit(5)).all()
        failed = s.scalar(select(func.count(Offer.id)).where(Offer.status == "failed",
                                                             Offer.created_at >= now() - timedelta(hours=24))) or 0
        codes = s.scalar(select(func.count()).select_from(Coupon).where(
            Coupon.code.is_not(None), Coupon.last_seen >= now() - timedelta(hours=2))) or 0
    return {
        "posts_hoje": posts_today(), "limite_diario": settings.daily_post_limit,
        **({"grupo_casa": {"posts_hoje": posts_today("lar"), "limite_diario": settings.lar_daily_limit,
                                "na_fila": s2_fila_lar(), "horario": f"{settings.lar_hour_start}h às {settings.lar_hour_end}h"}}
           if settings.lar_enabled else {}),
        "ofertas_na_fila": queue, "falhas_24h": failed, "cupons_com_codigo_ativos": codes,
        "whatsapp_conectado": _wa_connected(),
        "pausado": control.paused(c), "pausado_ate": c.get("paused_until") if control.paused(c) else None,
        "intervalo_minutos": [settings.interval_min, settings.interval_max],
        "desconto_minimo_pct": settings.min_discount_pct,
        "horario_ativo": f"{settings.active_hour_start}h às {settings.active_hour_end % 24}h" + (" do dia seguinte" if settings.active_hour_end > 24 else ""),
        "ultimos_posts": [{"titulo": o.title[:80], "preco": o.price, "link": o.affiliate_url or o.url,
                           "quando": o.posted_at.astimezone(control.TZ).strftime("%H:%M")} for o in last],
    }


def diag() -> str:
    from app.diagnose import diagnose
    return diagnose()


def pausar(minutos: int = 60) -> dict:
    until = datetime.now(control.TZ) + timedelta(minutes=min(max(int(minutos), 5), 1440))
    control.update(paused_until=until.isoformat())
    return {"ok": True, "pausado_ate": until.strftime("%d/%m %H:%M")}


def retomar() -> dict:
    control.update(paused_until=None)
    return {"ok": True}


def postar(quantidade: int = 1) -> dict:
    q = min(max(int(quantidade), 1), 10)
    control.update(post_now=q, paused_until=None)
    return {"ok": True, "mensagem": f"{q} oferta(s) serão postadas, 1 por minuto, começando em até 1 min."}


def cupons() -> dict:
    control.update(coupons_now=True)
    return {"ok": True, "mensagem": "Post de cupons sai em até 1 minuto."}


def ajustar(intervalo=None, desconto=None, limite=None, intervalo_max=None) -> dict:
    data = control.load()
    ov = data.get("overrides", {})
    if intervalo is not None:
        lo = min(max(float(intervalo), 3), 60)
        hi = min(max(float(intervalo_max if intervalo_max is not None else intervalo), lo), 60)
        for k, v in (("interval_min", lo), ("interval_max", hi), ("peak_interval_min", lo), ("peak_interval_max", hi)):
            ov[k] = v
    if desconto is not None:
        ov["min_discount_pct"] = min(max(int(desconto), 10), 80)
    if limite is not None:
        ov["daily_post_limit"] = min(max(int(limite), 10), 300)
    data["overrides"] = ov
    control.save(data)
    return {"ok": True, "ajustes_ativos": ov}


def fila(limite: int = 10) -> list:
    with SessionLocal() as s:
        rows = s.scalars(select(Offer).where(Offer.status == "new").order_by(Offer.score.desc()).limit(min(int(limite), 30))).all()
    return [{"titulo": o.title[:90], "preco": o.price, "preco_antigo": o.old_price, "fonte": o.source} for o in rows]


def buscar(termo: str, limite: int = 10) -> list:
    with SessionLocal() as s:
        rows = s.scalars(select(Offer).where(Offer.title.ilike(f"%{termo}%"), Offer.created_at >= now() - timedelta(days=3))
                         .order_by(Offer.score.desc()).limit(min(int(limite), 30))).all()
    return [{"titulo": o.title[:90], "preco": o.price, "preco_antigo": o.old_price, "status": o.status,
             "link": o.affiliate_url or o.url} for o in rows]


def cupons_ativos() -> list:
    with SessionLocal() as s:
        rows = s.scalars(select(Coupon).where(Coupon.code.is_not(None), Coupon.last_seen >= now() - timedelta(hours=2))
                         .order_by(Coupon.max_discount.desc())).all()
    return [{"codigo": c.code, "regra": c.title} for c in rows]


def codigo_wa() -> dict:
    if _wa_connected():
        return {"ok": True, "mensagem": "O WhatsApp já está conectado; não precisa de código."}
    number = settings.whatsapp_number
    if not number:
        return {"ok": False, "erro": "WHATSAPP_NUMBER não configurado no .env"}
    code = httpx.get(f"{settings.wa_url}/pair", params={"number": number}, timeout=60).json().get("code")
    return {"ok": True, "codigo": code,
            "como_usar": "WhatsApp > Aparelhos conectados > Conectar um aparelho > Conectar com número de telefone. Expira em ~2 min."}


def _linhas_alertas() -> list[dict]:
    f = DATA_DIR / "alertas.log"
    out = []
    for ln in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def alertas(n: int = 20) -> list:
    return _linhas_alertas()[-int(n):]


def relatorio(dia: str = "") -> str:
    """Relatório do dia (posts por loja, comissão, vendas): `ctl relatorio` ou `ctl relatorio 2026-10-13`."""
    from app.report import ctl as _rel
    return _rel(dia)


def _lazy(modulo: str, nome: str, join: bool = True):
    def run(*args):
        import importlib
        fn = getattr(importlib.import_module(modulo), nome)
        return fn(" ".join(args)) if join else fn()
    return run


COMANDOS = {
    "status": status, "diag": diag, "pausar": pausar, "retomar": retomar, "postar": postar, "cupons": cupons,
    "desconto": lambda v: ajustar(desconto=v), "limite": lambda v: ajustar(limite=v),
    "intervalo": lambda a, b=None: ajustar(intervalo=a, intervalo_max=b), "fila": fila, "buscar": buscar, "cupons-ativos": cupons_ativos,
    "codigo-wa": codigo_wa, "alertas": alertas, "relatorio": relatorio,
    "tabela": _lazy("app.prices", "preview", join=False), "preco": _lazy("app.prices", "set_price"),
    "edu": _lazy("app.content", "draft_edu"),
    "revisao-ig": lambda dias="60": __import__("app.revisao_ig", fromlist=["x"]).gerar(int(dias)),
    "servico": lambda *a: _lazy("app.content", "preview_service")(*(a or ("manutenção completa",))),
    "aprovar": _lazy("app.content", "approve_service", join=False),
    "cancelar": _lazy("app.content", "cancel_service", join=False),
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMANDOS:
        print(__doc__)
        return 2
    out = COMANDOS[argv[0]](*argv[1:])
    print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
