"""Chamada v2 dos posts de oferta (28/10/2026)."""
from types import SimpleNamespace

from app.templates import render


def _o(**kw):
    base = dict(title="Fone Gamer Redragon Themis H220", post_title=None, price=89.0, old_price=269.0, payment=None, coupon=None, cupom_dica=None,
                affiliate_url="https://meli.la/x", url="https://www.mercadolivre.com.br/x", source="mercadolivre", preco_situacao=None, preco_dias=0)
    base.update(kw)
    return SimpleNamespace(**base)


def test_selo_no_titulo_e_sem_repetir_percentual():
    t = render(_o(), "whatsapp")
    assert t.splitlines()[0].count("-67% | ") == 1
    price = next(x for x in t.splitlines() if x.startswith("💰"))
    assert "-67%" not in price and "R$ 269,00" in price


def test_desconto_pequeno_nao_tem_selo_e_mantem_percentual_no_preco():
    t = render(_o(price=80.0, old_price=100.0), "whatsapp")
    assert "-20% | " not in t.splitlines()[0]
    assert "-20%" in next(x for x in t.splitlines() if x.startswith("💰"))


def test_linha_da_loja_so_para_loja_conhecida():
    assert "🏪 Vendido no Mercado Livre" in render(_o(), "whatsapp")
    assert "🏪 Vendido na Shopee" in render(_o(source="shopee"), "whatsapp")
    assert "🏪" not in render(_o(source="pelando"), "whatsapp")
    assert "🏪" not in render(_o(source="aliexpress", url="https://pt.aliexpress.com/item/1.html"), "whatsapp")


def test_desliga_com_variavel(monkeypatch):
    monkeypatch.setenv("CHAMADA_V2", "0")
    t = render(_o(), "whatsapp")
    assert "% | " not in t.splitlines()[0] and "🏪" not in t
    assert "-67%" in next(x for x in t.splitlines() if x.startswith("💰"))
