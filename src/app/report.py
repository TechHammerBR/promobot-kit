"""Relatório diário (13/10/2026): posts por loja e por fonte, quantos com comissão, vendas/comissões da Shopee e da Awin.

Fica gravado em data/relatorios/AAAA-MM-DD.txt (nada é enviado ao WhatsApp/Telegram do dono). Roda sozinho às 23h50 e sob pedido:
`python -m app.ctl relatorio` (hoje) ou `python -m app.ctl relatorio 2026-10-13`.
"""
import time
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import DATA_DIR, settings
from app.db import Offer, SessionLocal
from app.log import log

TZ = ZoneInfo("America/Sao_Paulo")
PASTA = DATA_DIR / "relatorios"
LOJAS = (("aliexpress", "AliExpress"), ("shopee", "Shopee"), ("mercadoli", "Mercado Livre"), ("meli.la", "Mercado Livre"),
         ("amazon", "Amazon"), ("kabum", "KaBuM"), ("terabyte", "Terabyte"), ("magazine", "Magalu"), ("pichau", "Pichau"),
         ("samsung", "Samsung"), ("playstation", "PlayStation"), ("xbox", "Xbox"), ("nintendo", "Nintendo"))


def loja(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return next((nome for chave, nome in LOJAS if chave in host), host.removeprefix("www.") or "?")


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _shopee(inicio: datetime, fim: datetime) -> str:
    if not (settings.shopee_app_id and settings.shopee_secret):
        return "Shopee: sem chave da API."
    from app.affiliate import shopee_graphql
    q = ("{conversionReport(purchaseTimeStart:%d, purchaseTimeEnd:%d, limit:200){nodes{totalCommission orders{orderId items{itemPrice qty}}}}}"
         % (int(inicio.timestamp()), int(fim.timestamp())))
    try:
        nos = shopee_graphql(q)["conversionReport"]["nodes"]
    except Exception as e:
        return f"Shopee: não consegui ler as vendas ({str(e)[:80]})."
    pedidos = sum(len(n.get("orders") or []) for n in nos)
    valor = sum(float(i.get("itemPrice") or 0) * int(i.get("qty") or 1) for n in nos for o in (n.get("orders") or []) for i in (o.get("items") or []))
    comissao = sum(float(n.get("totalCommission") or 0) for n in nos)
    return f"Shopee: {pedidos} pedido(s), {_brl(valor)} em vendas, comissão estimada {_brl(comissao)}."


def _awin(inicio: datetime, fim: datetime) -> str:
    if not (settings.awin_token and settings.awin_publisher_id):
        return "Awin: sem token da API."
    import httpx
    from app import awin
    try:
        r = httpx.get(f"{awin.API}/publishers/{settings.awin_publisher_id}/transactions/", headers=awin._headers(), timeout=30,
                      params={"startDate": inicio.strftime("%Y-%m-%dT%H:%M:%S"), "endDate": fim.strftime("%Y-%m-%dT%H:%M:%S"),
                              "timezone": "America/Sao_Paulo"})
        r.raise_for_status()
        ts = r.json()
    except Exception as e:
        return f"Awin: não consegui ler as vendas ({str(e)[:80]})."
    valor = sum(float((t.get("saleAmount") or {}).get("amount") or 0) for t in ts)
    comissao = sum(float((t.get("commissionAmount") or {}).get("amount") or 0) for t in ts)
    sit = awin.situacao()["lojas_do_robo"]
    lojas = ", ".join(f"{h}: {s}" for h, s in sit.items())
    return f"Awin: {len(ts)} venda(s), {_brl(valor)} em vendas, comissão {_brl(comissao)}. Lojas: {lojas}."


def _ali(d) -> str:
    """Pedidos pagos no dia pelos nossos links do AliExpress (app Online desde 14/10/2026). Valores: a API devolve em centavos
    (ainda NÃO conferido com um pedido real — conferir no portal quando aparecer o primeiro)."""
    try:
        from app import aliapi
        r = aliapi.call("aliexpress.affiliate.order.list", start_time=f"{d:%Y-%m-%d} 00:00:00", end_time=f"{d:%Y-%m-%d} 23:59:59",
                        status="Payment Completed", page_no=1, page_size=50)
        pedidos = (r.get("orders") or {}).get("order") or []
        venda = sum(float(x.get("paid_amount") or 0) for x in pedidos) / 100
        com = sum(float(x.get("estimated_paid_commission") or 0) for x in pedidos) / 100
        return f"AliExpress: {len(pedidos)} pedido(s) pago(s), {venda:.2f} em vendas, comissão estimada {com:.2f} (valores a conferir no portal)."
    except Exception as e:  # noqa: BLE001
        return f"AliExpress: não consegui consultar ({str(e)[:80]})."


def gerar(dia: str | None = None, gravar: bool = True) -> str:
    """Texto do relatório do dia (AAAA-MM-DD; padrão hoje, horário de Brasília)."""
    d = datetime.strptime(dia, "%Y-%m-%d").replace(tzinfo=TZ) if dia else datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    fim = d + timedelta(days=1)
    with SessionLocal() as s:
        posts = s.scalars(select(Offer).where(Offer.status == "posted", Offer.posted_at >= d, Offer.posted_at < fim)).all()
        rej = Counter()
        for motivo, in s.execute(select(Offer.reason).where(Offer.status == "rejected", Offer.created_at >= d, Offer.created_at < fim)):
            m = (motivo or "?").split(":")[0].split(" [")[0]
            rej["desconto abaixo do mínimo" if m.startswith("desconto ") else m[:45]] += 1
        fila = len(s.scalars(select(Offer.id).where(Offer.status.in_(("new", "pending")))).all())
    por_loja, por_fonte, com = Counter(), Counter(), Counter()
    for o in posts:
        l = loja(o.url)
        por_loja[l] += 1
        por_fonte[o.source] += 1
        if o.affiliate_url and o.affiliate_url != o.url:
            com[l] += 1
    casa = [o for o in posts if (o.canal or "tech") == "lar"]
    total, comiss = len(posts), sum(com.values())
    linhas = [f"RELATÓRIO TECHHAMMER — {d:%d/%m/%Y}", "",
              f"Posts de oferta: {total} | com comissão: {comiss} ({round(100 * comiss / total) if total else 0}%) | na fila agora: {fila}", "",
              f"  (grupo de tecnologia {total - len(casa)} | grupo de casa {len(casa)})", "",
              "Por loja (posts / com comissão):"]
    linhas += [f"  {l:<16} {n:>3} / {com.get(l, 0)}" for l, n in por_loja.most_common()] or ["  (nenhum post)"]
    linhas += ["", "Por fonte: " + (", ".join(f"{f} {n}" for f, n in por_fonte.most_common()) or "-"), "",
               "Recusadas hoje (principais motivos):"]
    linhas += [f"  {n:>5}  {m}" for m, n in rej.most_common(8)] or ["  (nenhuma)"]
    linhas += ["", "Vendas e comissões (o que as plataformas informam; pode levar dias para aparecer):",
               "  " + _shopee(d, min(fim, datetime.now(TZ))), "  " + _awin(d, min(fim, datetime.now(TZ))),
               "  " + _ali(d)]
    texto = "\n".join(linhas)
    if gravar:
        PASTA.mkdir(exist_ok=True)
        (PASTA / f"{d:%Y-%m-%d}.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


def diario() -> None:
    try:
        gerar()
        with SessionLocal() as s:
            from app import pricehist
            pricehist.limpar(s)
            s.commit()
        log.info("relatorio_diario_gravado")
    except Exception as e:
        log.warning("relatorio_diario_falhou", error=str(e)[:200])


def ctl(dia: str = "") -> str:
    return gerar(dia.strip() or None)
