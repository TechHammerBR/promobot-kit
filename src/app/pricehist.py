"""Histórico de preço por produto (13/10/2026) — detector de DESCONTO FALSO sem IA.

A cada coleta o robô anota o menor preço do dia de cada produto (tabela price_history: produto, dia, preço). Na hora de publicar:
- "estavel": o preço de hoje é o mesmo dos dias anteriores -> o "de R$ X por R$ Y" da loja é enfeite: o post sai SEM o riscado e a
  oferta perde prioridade na fila.
- "queda": o preço de hoje está abaixo do menor preço que o robô já viu -> o post ganha "📉 Menor preço em N dias" e a oferta sobe.
- "novo": ainda não há dias suficientes de histórico (mínimo PRICE_HISTORY_MIN_DAYS) -> nada muda.
O histórico só enxerga o que o próprio robô coletou (começou em 13/10/2026) e guarda 90 dias.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.config import settings

TZ = ZoneInfo("America/Sao_Paulo")
DDL = "CREATE TABLE IF NOT EXISTS price_history (product_key VARCHAR(64) NOT NULL, day VARCHAR(10) NOT NULL, price FLOAT NOT NULL, PRIMARY KEY (product_key, day))"


def _hoje() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def criar(conn) -> None:
    conn.execute(text(DDL))


def registrar(session, key: str | None, price: float | None) -> None:
    """Anota o menor preço visto hoje para o produto."""
    if not key or not price or price <= 0:
        return
    dia = _hoje()
    atual = session.execute(text("SELECT price FROM price_history WHERE product_key = :k AND day = :d"), {"k": key, "d": dia}).scalar()
    if atual is None:
        session.execute(text("INSERT INTO price_history (product_key, day, price) VALUES (:k, :d, :p)"), {"k": key, "d": dia, "p": price})
    elif price < atual:
        session.execute(text("UPDATE price_history SET price = :p WHERE product_key = :k AND day = :d"), {"k": key, "d": dia, "p": price})


def analisar(session, key: str | None, price: float | None) -> tuple[str, int]:
    """("novo" | "estavel" | "queda" | "normal", dias de histórico anteriores a hoje)."""
    if not key or not price:
        return "novo", 0
    desde = (datetime.now(TZ) - timedelta(days=settings.price_history_window_days)).strftime("%Y-%m-%d")
    linhas = session.execute(text("SELECT day, price FROM price_history WHERE product_key = :k AND day >= :desde AND day < :hoje"),
                             {"k": key, "desde": desde, "hoje": _hoje()}).all()
    if len(linhas) < settings.price_history_min_days:
        return "novo", len(linhas)
    menor = min(p for _, p in linhas)
    primeiro = min(d for d, _ in linhas)
    dias = (datetime.now(TZ).date() - datetime.strptime(primeiro, "%Y-%m-%d").date()).days
    if price <= menor * (1 - settings.price_drop_pct / 100):
        return "queda", dias
    if price >= menor * 0.98:
        return "estavel", dias
    return "normal", dias


def limpar(session) -> int:
    corte = (datetime.now(TZ) - timedelta(days=90)).strftime("%Y-%m-%d")
    return session.execute(text("DELETE FROM price_history WHERE day < :c"), {"c": corte}).rowcount
