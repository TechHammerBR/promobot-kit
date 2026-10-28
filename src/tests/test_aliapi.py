"""API de afiliados do AliExpress: assinatura, leitura das respostas e conversão em oferta (sem rede)."""
import hashlib
import hmac

import pytest

from app import aliapi
from app.collectors.aliexpress import AliExpressCollector, _from_api
from app.collectors.base import BlockedError
from app.config import settings

PRODUTO = {
    "product_id": 1005007869391858, "product_title": " SSD Netac 1TB ", "target_sale_price": "187.99",
    "target_original_price": "261.10", "lastest_volume": 8276, "evaluate_rate": "96.9%",
    "product_main_image_url": "https://ae-pic-a1.aliexpress-media.com/kf/x.jpg",
}


class Resposta:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@pytest.fixture
def chaves(monkeypatch):
    monkeypatch.setattr(settings, "ali_app_key", "123")
    monkeypatch.setattr(settings, "ali_app_secret", "segredo")
    monkeypatch.setattr(settings, "ali_tracking_id", "default")


def responde(monkeypatch, data, visto=None):
    def fake_get(url, params=None, timeout=None):
        if visto is not None:
            visto.append(params)
        return Resposta(data)
    monkeypatch.setattr(aliapi.httpx, "get", fake_get)


def test_sign_ordena_parametros_e_usa_hmac_sha256():
    params = {"method": "m", "app_key": "123", "b": "2"}
    esperado = hmac.new(b"segredo", b"app_key123b2methodm", hashlib.sha256).hexdigest().upper()
    assert aliapi.sign(params, "segredo") == esperado


def test_configured_exige_chave_e_segredo(monkeypatch):
    monkeypatch.setattr(settings, "ali_app_key", "123")
    monkeypatch.setattr(settings, "ali_app_secret", "")
    assert not aliapi.configured()


def test_search_devolve_produtos_e_assina_a_chamada(monkeypatch, chaves):
    visto = []
    responde(monkeypatch, {"aliexpress_affiliate_product_query_response": {"resp_result": {
        "resp_code": 200, "result": {"products": {"product": [PRODUTO]}}}}}, visto)
    assert aliapi.search("ssd nvme") == [PRODUTO]
    q = visto[0]
    assert q["keywords"] == "ssd nvme" and q["target_currency"] == "BRL" and q["tracking_id"] == "default"
    sem_sign = {k: v for k, v in q.items() if k != "sign"}
    assert q["sign"] == aliapi.sign(sem_sign, "segredo")


def test_busca_vazia_nao_e_erro(monkeypatch, chaves):
    responde(monkeypatch, {"aliexpress_affiliate_product_query_response": {"resp_result": {
        "resp_code": 405, "resp_msg": "The result is empty"}}})
    assert aliapi.search("nada") == []


def test_link_devolve_o_curto(monkeypatch, chaves):
    responde(monkeypatch, {"aliexpress_affiliate_link_generate_response": {"resp_result": {"resp_code": 200, "result": {
        "promotion_links": {"promotion_link": [{"promotion_link": "https://s.click.aliexpress.com/e/_abc"}]}}}}})
    assert aliapi.link("https://pt.aliexpress.com/item/1.html?x=1") == "https://s.click.aliexpress.com/e/_abc"


def test_tracking_id_recusado_vira_erro(monkeypatch, chaves):
    responde(monkeypatch, {"aliexpress_affiliate_link_generate_response": {"resp_result": {
        "resp_code": 402, "resp_msg": "TrackingId input parameter error"}}})
    with pytest.raises(RuntimeError, match="402"):
        aliapi.link("https://pt.aliexpress.com/item/1.html")


def test_limite_de_chamadas_pausa_a_fonte(monkeypatch, chaves):
    responde(monkeypatch, {"error_response": {"code": "ApiCallLimit", "msg": "too many"}})
    with pytest.raises(BlockedError):
        aliapi.search("ssd")


def test_sem_permissao_vira_erro_comum(monkeypatch, chaves):
    responde(monkeypatch, {"error_response": {"code": "InsufficientPermission", "msg": "no"}})
    with pytest.raises(RuntimeError, match="InsufficientPermission"):
        aliapi.call("aliexpress.affiliate.hotproduct.query")


def test_produto_vira_oferta():
    o = _from_api(PRODUTO)
    assert o.title == "SSD Netac 1TB" and o.price == 187.99 and o.old_price == 261.10
    assert str(o.url) == "https://pt.aliexpress.com/item/1005007869391858.html"
    assert o.vendas == 8276 and o.nota == 4.8 and o.store == "AliExpress"


def test_descarta_pecinha_e_produto_sem_vendas():
    assert _from_api({**PRODUTO, "target_sale_price": "12.69"}) is None
    assert _from_api({**PRODUTO, "lastest_volume": 3}) is None
    assert _from_api({"product_id": 1}) is None


def test_sem_preco_antigo_maior_fica_sem_desconto():
    o = _from_api({**PRODUTO, "target_original_price": "187.99", "evaluate_rate": None})
    assert o.old_price is None and o.nota is None


def test_coletor_usa_a_api_e_nao_repete_produto(monkeypatch, chaves, tmp_path):
    monkeypatch.setattr("app.collectors.aliexpress.STATE", tmp_path / "idx")
    monkeypatch.setattr(settings, "ali_keywords", "ssd,teclado")
    monkeypatch.setattr(settings, "ali_keywords_per_cycle", 2)
    monkeypatch.setattr(aliapi, "search", lambda kw: [PRODUTO, {**PRODUTO, "product_id": 2}])
    ofertas = AliExpressCollector().collect()
    assert len(ofertas) == 2


def test_datas_voltam_com_fuso_e_comparam_em_utc(tmp_path):
    """SQLite (robô leve) guarda sem fuso: a coluna UTCDateTime converte na ida e na volta."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db import Base, Offer
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    Base.metadata.create_all(eng)
    sp = ZoneInfo("America/Sao_Paulo")
    quando = datetime(2026, 10, 13, 22, 30, tzinfo=sp)  # 01:30 UTC do dia 14
    with Session(eng) as s:
        s.add(Offer(source="x", title="t", url="https://a/1", price=1.0, fingerprint="f1", status="posted", posted_at=quando))
        s.commit()
        o = s.scalar(select(Offer))
        assert o.posted_at.tzinfo is not None and o.posted_at == quando
        meia_noite_13 = datetime(2026, 10, 13, 0, 0, tzinfo=sp)
        meia_noite_14 = meia_noite_13 + timedelta(days=1)
        assert s.scalar(select(Offer.id).where(Offer.posted_at >= meia_noite_13)) is not None
        assert s.scalar(select(Offer.id).where(Offer.posted_at >= meia_noite_14)) is None


def test_rodizio_nao_deixa_o_aliexpress_tomar_a_fila(tmp_path, monkeypatch):
    """Com AliExpress recém-postado e outra fonte na fila, a vez é da outra fonte mesmo com nota menor."""
    from datetime import datetime, timezone

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db import Base, Offer
    eng = create_engine(f"sqlite:///{tmp_path / 'r.db'}")
    Base.metadata.create_all(eng)
    agora = datetime.now(timezone.utc)
    with Session(eng) as s:
        s.add(Offer(source="aliexpress", title="a", url="https://a/1", price=1.0, fingerprint="p", status="posted", posted_at=agora, score=90))
        s.add(Offer(source="aliexpress", title="b", url="https://a/2", price=1.0, fingerprint="n1", status="new", score=120))
        s.add(Offer(source="pelando", title="c", url="https://a/3", price=1.0, fingerprint="n2", status="new", score=40))
        s.commit()
        recentes = s.scalars(select(Offer.source).where(Offer.status == "posted").order_by(Offer.posted_at.desc()).limit(2)).all()
        evitar = ["aliexpress"] if "aliexpress" in recentes else []
        q = select(Offer).where(Offer.status == "new").where(Offer.source.notin_(evitar))
        assert s.scalars(q.order_by(Offer.score.desc()).limit(1)).first().source == "pelando"
