from datetime import datetime, timedelta
from types import SimpleNamespace as N

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import coupon_codes, pricehist
from app.templates import render


def _sessao():
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        pricehist.criar(c)
    return sessionmaker(eng)()


def _dia(n):
    return (datetime.now(pricehist.TZ) - timedelta(days=n)).strftime("%Y-%m-%d")


def test_historico_de_preco():
    s = _sessao()
    assert pricehist.analisar(s, "X", 100.0) == ("novo", 0)
    for n in (5, 4, 3, 2):
        s.execute(text("INSERT INTO price_history VALUES ('X', :d, 100.0)"), {"d": _dia(n)})
    assert pricehist.analisar(s, "X", 100.0) == ("estavel", 5)  # "desconto" que é o preço de sempre
    assert pricehist.analisar(s, "X", 99.0)[0] == "estavel"
    assert pricehist.analisar(s, "X", 89.0) == ("queda", 5)
    assert pricehist.analisar(s, "X", 96.5)[0] == "normal"
    pricehist.registrar(s, "Y", 50.0)
    pricehist.registrar(s, "Y", 45.0)
    pricehist.registrar(s, "Y", 60.0)
    assert s.execute(text("SELECT price FROM price_history WHERE product_key = 'Y'")).scalar() == 45.0


def test_post_sem_riscado_quando_o_desconto_e_falso():
    base = dict(title="Fone QCY T13 ANC Bluetooth", post_title=None, price=125.0, old_price=250.0, payment=None, coupon=None,
                url="https://shopee.com.br/product/1/2", affiliate_url="https://s.shopee.com.br/x")
    normal = render(N(**base), "whatsapp")
    assert "-50%" in normal
    falso = render(N(preco_situacao="estavel", preco_dias=6, **base), "whatsapp")
    assert "-50%" not in falso and "250" not in falso
    queda = render(N(preco_situacao="queda", preco_dias=6, **base), "whatsapp")
    assert "Menor preço dos últimos 6 dias" in queda and "-50%" in queda


def test_cupom_sugerido(monkeypatch):
    cup = [N(code="MODA15", title="R$ 15 OFF em R$ 89 em Moda", scope=""),
           N(code="GRANDE", title="R$ 30 OFF em R$ 149", scope=""),
           N(code="GERAL20", title="R$ 20 OFF em R$ 60", scope="")]
    monkeypatch.setattr(coupon_codes, "active_codes", lambda s, loja="ml": cup if loja == "shopee" else [])
    d = coupon_codes.sugerir(None, "https://shopee.com.br/product/1/2", 99.0)
    assert d["code"] == "GERAL20"  # o de moda é restrito e o de R$ 149 não cabe no preço
    assert coupon_codes.sugerir(None, "https://shopee.com.br/product/1/2", 40.0) is None
    assert coupon_codes.sugerir(None, "https://www.amazon.com.br/dp/B0G1TMXHRZ", 99.0) is None
    assert coupon_codes.sugerir(None, "https://www.mercadolivre.com.br/p/MLB1", 99.0) is None
    post = render(N(title="Fone QCY T13", post_title=None, price=99.0, old_price=None, payment=None, coupon=None, cupom_dica=d,
                    url="https://shopee.com.br/product/1/2", affiliate_url="https://s.shopee.com.br/x"), "whatsapp")
    assert "Tente o cupom *GERAL20*" in post and "lote de cupons" in post


def test_cupom_ml_nao_e_barrado_pelo_nome_da_loja(monkeypatch):
    cup = [N(code="CARRINHOML", title="10% OFF em R$ 79, limitado a R$ 30", scope="Válido no Mercado Livre")]
    monkeypatch.setattr(coupon_codes, "active_codes", lambda s, loja="ml": cup)
    assert coupon_codes.sugerir(None, "https://www.mercadolivre.com.br/p/MLB1", 120.0)["code"] == "CARRINHOML"


def test_kabum_so_cupom_da_awin(monkeypatch):
    from app import awin
    monkeypatch.setattr(awin, "cupons", lambda mid: [])
    assert coupon_codes.sugerir(None, "https://www.kabum.com.br/produto/1/x", 500.0) is None
    monkeypatch.setattr(awin, "cupons", lambda mid: [{"code": "KABUMAWIN", "title": "5% OFF no site", "url": None}])
    assert coupon_codes.sugerir(None, "https://www.kabum.com.br/produto/1/x", 500.0)["code"] == "KABUMAWIN"


def test_horario_24h_com_janela_de_manutencao(monkeypatch):
    from app.config import settings
    from app.pipeline import hora_ativa
    monkeypatch.setattr(settings, "active_hour_start", 6)
    monkeypatch.setattr(settings, "active_hour_end", 27)
    assert [h for h in range(24) if not hora_ativa(h)] == [3, 4, 5]
    monkeypatch.setattr(settings, "active_hour_end", 24)
    assert [h for h in range(24) if not hora_ativa(h)] == [0, 1, 2, 3, 4, 5]


def test_variacoes_do_anuncio():
    from app.titles import variacoes
    assert variacoes("SSD Lexar THOR PRO 512GB 1TB 2TB 4TB PCIe 4.0x4 NVMe M.2 2280") == ["512GB", "1TB", "2TB", "4TB"]
    assert variacoes("Memória JUHOR DDR4 8GB 16GB 3200MHz CL18") == ["8GB", "16GB"]
    assert variacoes("Lexar NQ790, M.2, SSD, 2TB, 1TB, Jogos") == ["1TB", "2TB"]
    assert variacoes("SSD Kingston NV3 1TB NVMe") == []
    assert variacoes("Notebook Lenovo 16GB/512GB Ryzen 5") == []
    assert variacoes("Memória JUHOR DDR5 32GB (16GBX2) 6000MHz") == []


def test_canal_de_casa(monkeypatch):
    from app.config import settings
    from app.engine import canal_de, is_lar
    monkeypatch.setattr(settings, "lar_enabled", True)
    assert canal_de("Air Fryer Mondial 4L Family Inox") == "lar"
    assert canal_de("Jogo de Panelas Tramontina Paris 5 peças") == "lar"
    assert canal_de("Aspirador de Pó Vertical Electrolux") == "lar"
    assert canal_de("SSD Kingston NV3 1TB NVMe") == "tech"
    assert canal_de("Mouse Gamer Logitech G203") == "tech"
    assert canal_de("Tênis Nike Revolution 7") == "tech"  # nem casa nem tecnologia: segue a regra antiga (recusado)
    assert not is_lar("Mesa digitalizadora Wacom")  # "mesa" sozinha não é móvel; precisa "mesa de jantar"
    monkeypatch.setattr(settings, "lar_enabled", False)
    assert canal_de("Air Fryer Mondial 4L Family Inox") == "tech"


def test_rodape_divulga_os_outros_canais(monkeypatch):
    from app.config import settings
    from app.templates import invite_lines
    monkeypatch.setattr(settings, "lar_enabled", True)
    monkeypatch.setattr(settings, "group_invite_link", "https://chat.whatsapp.com/TECH")
    monkeypatch.setattr(settings, "lar_invite_link", "https://chat.whatsapp.com/CASA")
    monkeypatch.setattr(settings, "telegram_invite_link", "https://t.me/canal")
    wa, tg, casa = (" ".join(invite_lines(c, ch)) for c, ch in (("tech", "whatsapp"), ("tech", "telegram"), ("lar", "whatsapp")))
    assert "TECH" not in wa and "CASA" in wa and "t.me" in wa
    assert "TECH" in tg and "CASA" in tg and "t.me" not in tg
    assert "CASA" not in casa and "TECH" in casa and "t.me" in casa
