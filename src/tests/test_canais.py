from app.collectors.canais import extrair, loja_limpa


def test_extrair_formatos_dos_canais():
    a = extrair("🔥 Microfone Gamer Condensador Fifine SuperFrame Edition SFM2, USB, RGB, Black\n\n💲R$79,99\n\n🔗https://x.y/z\n\n#Anuncio")
    assert a == {"title": "Microfone Gamer Condensador Fifine SuperFrame Edition SFM2, USB, RGB, Black", "price": 79.99, "coupon": None}
    b = extrair("Mouse Gamer Redragon Predator RGB M612 por R$79,98\n\nCompre aqui: https://link.amazon/B09")
    assert b["title"] == "Mouse Gamer Redragon Predator RGB M612" and b["price"] == 79.98
    c = extrair("🔥Caixa de Som JBL PartyBox 330 280W RMS Luzes RGB e Bateria de Até 18h - R$ 2273\n\nhttps://s.shopee.com.br/x")
    assert c["title"].startswith("Caixa de Som JBL PartyBox 330") and c["price"] == 2273.0
    d = extrair("🔥 Processador Intel Core I5 14600Kf 3 5Ghz\n\n💵 R$ 1.439,99 com cupom: KORUJAOHARD\n\n🔗 Link do produto:\nhttps://aoferta.net/x")
    assert d["price"] == 1439.99 and d["coupon"] == "KORUJAOHARD" and d["title"].startswith("Processador Intel Core I5")
    e = extrair("Samsung Galaxy Book4 por R$2.967,12\n🎟️Com cupom LAPTOP200\n\n*Intel Core i3-1315U")
    assert e["title"] == "Samsung Galaxy Book4" and e["coupon"] == "LAPTOP200"
    f = extrair("👌 Câmera de Segurança Elsys Wi-Fi, Full HD\n\n💲 Valor: R$49,99 no PIX\n\n👀 https://pcdofafa.com.br/p/kabum/58mvll")
    assert f["title"] == "Câmera de Segurança Elsys Wi-Fi, Full HD" and f["price"] == 49.99


def test_post_de_cupom_nao_e_oferta():
    assert extrair("🔥 Cupom Shopee\n\nR$ 20 OFF em R$ 60 - D1AD3CUP0M10\n\nAtive aqui >> https://s.shopee.com.br/3q") is None
    assert extrair("Bom dia, pessoal!") is None


def test_loja_limpa_tira_afiliado():
    assert loja_limpa("https://www.amazon.com.br/dp/B0G1TMXHRZ?tag=geovani0d-20") == "https://www.amazon.com.br/dp/B0G1TMXHRZ"
    assert loja_limpa("https://www.kabum.com.br/produto/509689/aspirador-de-po?awc=1234_abc") == "https://www.kabum.com.br/produto/509689/aspirador-de-po"
    assert loja_limpa("https://www.terabyteshop.com.br/produto/25612/microfone-fifine?p=1025558") == "https://www.terabyteshop.com.br/produto/25612/microfone-fifine"
    assert loja_limpa("https://shopee.com.br/user/voucher-wallet?mmp_pid=an_1") is None
    assert loja_limpa("https://www.mercadolivre.com.br/social/canalexemplo?matt_word=canalexemplo") is None
    assert loja_limpa("https://www.youtube.com/watch?v=abc") is None
