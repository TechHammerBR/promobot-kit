from app.affiliate import to_affiliate
from app.config import settings
from app.schemas import RawOffer


def make(**kw):
    base = dict(source="t", title="Produto X", url="https://exemplo.com/p", price=80, old_price=100)
    return RawOffer(**(base | kw))


def test_discount():
    assert make().discount_pct == 20
    assert make(old_price=None).discount_pct == 0


def test_fingerprint_ignores_case_and_punctuation():
    assert make(title="Produto X!").fingerprint == make(title="produto x").fingerprint


def test_product_key():
    from app.engine import product_key
    assert product_key("https://produto.mercadolivre.com.br/MLB-4081278987-tenis-_JM") == "MLB4081278987"
    assert product_key("https://www.mercadolivre.com.br/x/p/MLB18725310?a=1") == "MLB18725310"
    assert product_key("https://www.amazon.com.br/dp/B0D1YNK75P") == "AMZB0D1YNK75P"


def test_non_affiliate_site_passthrough():
    assert to_affiliate("https://www.kabum.com.br/p/1") == ("https://www.kabum.com.br/p/1", False)


def test_clean_url_strips_third_party_affiliates():
    from app.affiliate import clean_url
    assert clean_url("https://www.amazon.com.br/Algo/dp/B0D1YNK75P?tag=gatry0b-20&amp;th=1") == \
        "https://www.amazon.com.br/dp/B0D1YNK75P"
    out = clean_url("https://produto.mercadolivre.com.br/MLB-1-x?matt_tool=99&utm_source=y&foo=1#pos")
    assert out == "https://produto.mercadolivre.com.br/MLB-1-x?foo=1"


def test_coupon_parse_keeps_only_general():
    from app.coupons import parse_card
    general = parse_card("25% OFF em Itens para Casa\nCupom 25% OFF\nEm produtos selecionados\nCompra mínima\nR$\n25\nLimite de\nR$\n20\nVence 31 de outubro\nAplicar")
    assert general == {"title": "25% OFF em Itens para Casa", "scope": "Em produtos selecionados",
                       "min_purchase": 25.0, "max_discount": 20.0, "expires_text": "Vence 31 de outubro"}
    assert parse_card("5% OFF\nEm produtos de Universalcases2\nCompra mínima\nR$\n930\nVence em domingo") is None


def test_photo_url_full_size_jpg():
    from app.media import photo_url
    assert photo_url("https://http2.mlstatic.com/D_Q_NP_2X_760745-MLA95700724020_102025-AB.webp") == \
        "https://http2.mlstatic.com/D_NQ_NP_760745-MLA95700724020_102025-O.jpg"


def test_all_modules_import():
    """Evita subir código que nem importa (o bot chegou a quebrar ao iniciar)."""
    import importlib
    for m in ("app.main", "app.pipeline", "app.publisher", "app.coupons", "app.media", "app.ai"):
        importlib.import_module(m)


def test_payment_lines():
    from app.templates import payment_lines
    assert payment_lines("ou R$ 139 , 38 em outros meios") == ("no PIX", "💳 ou R$ 139,38 em outros meios")
    assert payment_lines("em 10x R$ 98 , 90 sem juros") == ("à vista", "💳 ou 10x de R$ 98,90 sem juros")
    assert payment_lines("2x R$ 48 , 33 com Linha de Crédito") == ("à vista", None)
    assert payment_lines("ou R$ 1.398 , 78 em 10x R$ 139 , 88 sem juros") ==         ("à vista", "💳 ou R$ 1.398,78 em 10x de R$ 139,88 sem juros")
    assert payment_lines(None) == ("", None)


def test_category_emoji():
    from app.templates import category_emoji
    assert category_emoji("Smartphone Samsung Galaxy A36") == "📱"
    assert category_emoji("Monitor LG 20") == "🖥️"
    assert category_emoji("Coisa aleatória") == "🛍️"


def test_variable_interval_ranges():
    from app.config import settings
    from app.pipeline import is_peak, next_delay_seconds
    assert is_peak(12) and is_peak(20) and not is_peak(9) and not is_peak(23)
    delays = {round(next_delay_seconds()) for _ in range(50)}
    assert len(delays) > 10  # varia de verdade
    assert all(settings.peak_interval_min * 60 <= d <= settings.interval_max * 60 for d in delays)


def test_alert_so_registra_em_arquivo(tmp_path, monkeypatch):
    """Sem chatbot/notificações (07/10/2026): alert() apenas grava em data/alertas.log."""
    from app import publisher
    monkeypatch.setattr(publisher, "DATA_DIR", tmp_path)
    publisher.alert("teste de alerta")
    assert "teste de alerta" in (tmp_path / "alertas.log").read_text(encoding="utf-8")


def test_ctl_ajustar_respeita_limites(tmp_path, monkeypatch):
    from app import control, ctl
    monkeypatch.setattr(control, "FILE", tmp_path / "control.json")
    ov = ctl.ajustar(desconto=5, limite=9999, intervalo=1)["ajustes_ativos"]
    assert ov["min_discount_pct"] == 10 and ov["daily_post_limit"] == 300 and ov["interval_min"] == 3


def test_gpu_espera_so_com_trava_recente(tmp_path, monkeypatch):
    import os
    import time
    from app import gpu
    monkeypatch.setattr(gpu, "LOCK", tmp_path / "busy")
    assert not gpu.busy()
    (tmp_path / "busy").write_text("x")
    assert gpu.busy()
    old = time.time() - 4 * 3600
    os.utime(tmp_path / "busy", (old, old))
    assert not gpu.busy()  # trava velha (laboratório caiu) é ignorada


def test_store_photos_le_og_image(monkeypatch):
    """Plano B de foto: pega og:image e JSON-LD da página da loja; ignora logos; desiste se tiver captcha."""
    import httpx
    from app import storephoto

    class R:
        status_code = 200
        url = httpx.URL("https://loja.exemplo.com.br/p/1")
        text = ("<html><head><meta property=\"og:image\" content=\"/img/produto.jpg\">"
                "<script type=\"application/ld+json\">{\"@type\":\"Product\",\"image\":[\"https://cdn.exemplo.com/a.jpg\","
                "\"https://cdn.exemplo.com/logo.png\"]}</script></head></html>")

    monkeypatch.setattr(storephoto.httpx, "get", lambda *a, **k: R())
    fotos = storephoto.store_photos("https://loja.exemplo.com.br/p/1")
    assert fotos == ["https://loja.exemplo.com.br/img/produto.jpg", "https://cdn.exemplo.com/a.jpg"]
    R.text = "<html>captcha</html>"
    assert storephoto.store_photos("https://loja.exemplo.com.br/p/1") == []


def test_legenda_social_sem_preco_antigo():
    """Oferta bem votada (sem preço antigo) também vai para as redes, com legenda de em alta e sem -%."""
    from types import SimpleNamespace
    from app import social
    o = SimpleNamespace(price=485.99, old_price=None, post_title="Processador Ryzen 5 5500", title="x", affiliate_url=None, url="https://loja.com/p")
    cap = social._caption(o, ig=True)
    assert "Por apenas R$ 485,99" in cap and "-%" not in cap and "De R$" not in cap
    o2 = SimpleNamespace(price=80.0, old_price=100.0, post_title="Mouse", title="x", affiliate_url=None, url="https://loja.com/p")
    assert "(-20%)" in social._caption(o2, ig=True)


def test_catchup_recupera_so_uma_vez_e_dentro_da_tolerancia(tmp_path, monkeypatch):
    """Post agendado perdido (servidor desligado) é recuperado sozinho: 1x, só dentro da tolerância e no dia certo."""
    from datetime import datetime
    from app import catchup
    monkeypatch.setattr(catchup, "STATE", tmp_path / "estado.json")
    rodou = []
    monkeypatch.setattr(catchup, "schedule", lambda: [
        ("story", "14:00", "*", 3, lambda: rodou.append("story14")),
        ("feed", "19:30", "mon,wed,fri", 3, lambda: rodou.append("feed")),
        ("reel", "12:30", "thu", 5, lambda: rodou.append("reel"))])
    quarta = lambda h, m: datetime(2026, 10, 7, h, m, tzinfo=catchup.TZ)  # 07/10/2026 = quarta
    assert catchup.recover(quarta(14, 2)) == []                     # recém passou: o agendador normal cuida
    assert catchup.recover(quarta(14, 48)) == ["story@14:00"]        # perdeu: recupera
    assert catchup.recover(quarta(15, 10)) == []                    # já rodou: não repete
    assert catchup.recover(quarta(20, 0)) == ["feed@19:30"]          # quarta é dia de feed
    assert catchup.recover(quarta(23, 30)) == []                    # story 14h passou da tolerância; reel é só quinta
    assert rodou == ["story14", "feed"]


def test_ali_golpes_e_legitimas():
    """Anti-golpe do AliExpress (07/10): ficha técnica x preço, usado, capacidade falsa; marca/preço normal passam."""
    from app.alicheck import verificar
    golpe = "2026 14.1 Inch Ultra Thin Laptop 2026 Win11 Intel I9-9880H DDR4 16GB/32GB RAM 2TB SSD Portable Business"
    assert "notebook" in verificar(golpe, 1455.77)
    assert verificar("Lenovo IdeaPad 3 Laptop Intel i5 16GB RAM 512GB SSD", 2400) is None
    assert "usado" in verificar("AMD Ryzen 5 2600 Tray CPU 6 Core 12 Thread AM4", 256)
    assert "usado" in verificar("Xiaomi Redmi K50 gaming 5G smartphone Snapdragon 8 Gen1 used phone", 1367)
    assert "capacidade" in verificar("2TB USB 3.0 Flash Drive Pen Drive High Speed", 45)
    assert "capacidade" in verificar("SSD NVMe M.2 1TB PCIe 4.0", 120)
    assert verificar("Kingston NV2 1TB NVMe M.2 SSD", 340) is None
    assert "placa de vídeo" in verificar("RTX 4090 24GB Graphics Card GDDR6X", 900)
    assert verificar("GPU Cooler Fan for RTX 4090", 90) is None
    assert "celular" in verificar("Smartphone 16GB+1TB Android 14 Snapdragon 8 Gen 3 5G", 700)
    assert verificar("AULA SC580X Tri-mode Wireless Gaming Mouse 12000DPI", 123) is None
    assert verificar("Controle 8BitDo Ultimate 2 sem Fio 2.4G para PC e Android", 225) is None
    assert "vendas" in verificar("Monitor Gamer 27 polegadas 144Hz", 900, vendas=5)
    assert "nota" in verificar("Fone Bluetooth ANC", 200, nota=4.2)


def test_ali_vendas_e_nota_do_cartao():
    from app.collectors.aliexpress import _vendas_nota
    assert _vendas_nota("Titulo\n4.5152 sold\nBRL289.69") == (152, 4.5)
    assert _vendas_nota("Titulo\n4.32000+ sold\nBRL6.99") == (2000, 4.3)
    assert _vendas_nota("Titulo\n1 sold\nBRL17.89") == (1, None)
    assert _vendas_nota("Titulo\n4.6\nBRL1367.45") == (0, 4.6)


def test_ali_produto_principal_nao_confunde_periferico():
    from app.alicheck import verificar
    assert verificar("AULA SC580X Tri-mode Wireless Gaming Mouse 12000DPI Rechargeable Ergonomic for PC Laptop", 123) is None
    assert verificar("Laptop Cooling Pad 17 inch with 6 fans", 90) is None
    assert verificar("Bluetooth Gamepad for Smartphone Android iOS", 80) is None
    assert "notebook" in verificar("14.1 Inch Ultra Thin Laptop Intel I9-9880H 32GB RAM 2TB SSD", 1455)


def test_voz_desligada_ou_fora_do_ar_nao_trava(monkeypatch):
    """Narração: flag desligada -> None; serviço fora do ar -> None (o Reel sai mudo); resposta boa -> [(wav, segundos)]."""
    import base64

    from app import voz
    monkeypatch.setattr(voz.settings, "voice_enabled", False)
    assert voz.narrar(["oi"]) is None
    monkeypatch.setattr(voz.settings, "voice_enabled", True)

    def cai(*a, **k):
        raise RuntimeError("serviço fora do ar")
    monkeypatch.setattr(voz.httpx, "post", cai)
    assert voz.narrar(["oi"]) is None

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"itens": [{"wav_b64": base64.b64encode(b"RIFFx").decode(), "segundos": 1.5, "sim": 0.9}]}
    visto = {}

    def ok(*a, **k):
        visto.update(k)
        return R()
    monkeypatch.setattr(voz.httpx, "post", ok)
    assert voz.narrar(["oi"]) == [(b"RIFFx", 1.5)]
    assert visto["json"]["estilo"] == voz.settings.voice_style  # o estilo de fala configurado vai no pedido
    assert voz.narrar(["a", "b"]) is None  # quantidade de falas diferente do pedido


def test_nome_falado_marca_o_nome_do_jogo():
    from app.game_reels import _nome_falado
    assert _nome_falado("F1® 25™") == "[[F1 25]]"
    assert _nome_falado("Hunt:  Showdown [1896]") == "[[Hunt: Showdown 1896]]"
