from app import awin
from app.config import settings


def test_loja_sem_aprovacao_nao_ganha_link(monkeypatch):
    monkeypatch.setattr(settings, "awin_token", "")
    monkeypatch.setattr(settings, "awin_approved_mids", "")
    assert awin.loja_de("https://www.kabum.com.br/produto/1/x") == 17729
    assert awin.link("https://www.kabum.com.br/produto/1/x") is None
    assert not awin.aplicavel("https://www.kabum.com.br/produto/1/x")


def test_link_de_loja_aprovada(monkeypatch):
    monkeypatch.setattr(settings, "awin_token", "")
    monkeypatch.setattr(settings, "awin_approved_mids", "17729")
    monkeypatch.setattr(settings, "awin_publisher_id", "123456")
    l = awin.link("https://www.kabum.com.br/produto/509689/aspirador")
    assert l.startswith("https://www.awin1.com/cread.php?awinmid=17729&awinaffid=123456&ued=https%3A%2F%2Fwww.kabum.com.br%2Fproduto%2F509689")


def test_samsung_e_outras_lojas_ficam_de_fora(monkeypatch):
    monkeypatch.setattr(settings, "awin_token", "")
    monkeypatch.setattr(settings, "awin_approved_mids", "17729,25539")
    assert awin.link("https://shop.samsung.com/br/galaxy-s25") is None  # só promoção vinda da Awin
    assert awin.link("https://www.amazon.com.br/dp/B0G1TMXHRZ") is None
