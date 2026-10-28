from app.titles import limpar, mal_traduzido, marca, parecidos


def test_nao_come_palavra_do_modelo():
    t = limpar("GameSir Nova Lite Controle Sem Fio para Jogos, Compatível com Switch, Android, iOS, PC e Steam")
    assert t == "GameSir Nova Lite Controle Sem Fio para Jogos"
    assert "para PC" in limpar("Controlador de jogos sem fio 8BitDo Ultimate 2 para PC e Android com joysticks TMR")


def test_limite_e_fim_limpo():
    t = limpar("Placa-mãe Mini ITX JGINYUE AMD B550 AM4, compatível com processadores Ryzen R5 da série 4000/5000, memória RAM")
    assert t == "Placa-mãe Mini ITX JGINYUE AMD B550 AM4"
    longo = limpar("Mouse Gamer Sem Fio Rapoo VT0 Air MAX com Taxa de Polling Verdadeira de 8K, Leve (39g), Grau Esports")
    assert len(longo) <= 60 and longo.rsplit(" ", 1)[-1].lower() not in ("com", "de", "para")


def test_repetidas_e_variacoes():
    assert limpar("KOOTION SSD SATA Disco Rígido 128GB 240GB 480GB 512GB 1TB SATA3").startswith("KOOTION SSD SATA Disco Rígido 128GB a 1TB")
    assert limpar("Notebook HP 200 G2i Core i5 16GB 256GB W11") == "Notebook HP 200 G2i Core i5 16GB 256GB W11"  # RAM e SSD não são faixa
    assert limpar("KZ Castor PRO 2DD Dinâmico em fones de ouvido High-end Fones de ouvido sintonizáveis").count("ouvido") == 1


def test_aviso_do_agregador_sem_preco():
    assert limpar("(R$ 22,82 +por- / Prime) Mouse Pad Gamer Havit MP847 Grande Antiderrapante").startswith("[Prime] Mouse Pad Gamer Havit")
    assert limpar("[Taxas/Moedas R$8,89] Kit 2x Controle Smart TV 4K Universal").startswith("[Taxas/Moedas] Kit 2x")


def test_marca():
    assert marca("Controle GameSir Nova Lite Switch com Efeito Hall") == "GameSir"
    assert marca("Qcy t13 anc cancelamento de ruído ativo sem fio") == "QCY"
    assert marca("Processador AMD Ryzen 5 R5 3600 3,6 GHz 6 núcleos") == "AMD"
    assert marca("MACHINIST-B450 Placa-mãe, Processador AMD, Dual-Channel, Memória DDR4") == "MACHINIST"
    assert marca("Placa-mãe QIYIDA X99 D4, Processador AMD") is None
    assert marca("CPU Air Cooler, X79, X99, 3Pin, 4Pin, Ventilador de refrigeração para Intel") is None
    assert marca("Memória JUHOR DDR5 32GB (16GBX2) 6000MHz") == "JUHOR"  # dono, 13/10: JUHOR, MOUGOL e MACHINIST são boas
    assert marca("Memória CUSU DDR5 32GB 6000MHz") is None
    assert marca("Capa de silicone para Xiaomi Redmi Note 13") is None


def test_mal_traduzido():
    assert mal_traduzido("Amd novo ryzen wraith cooler wraith prisma ventilador original 4 pinos pode suportar r3 r5 r7 r9 cpu")
    assert not mal_traduzido("Webcam FIFINE 1440p Full HD para PC com Microfone, Tripé, para Desktop e Laptop")
    assert not mal_traduzido("Jogo SIFU - Nintendo Switch")


def test_parecidos():
    a = "GameSir Nova Lite Controle Sem Fio para Jogos, Compatível com Switch, Android, iOS, PC e Steam"
    b = "Controle GameSir Nova Lite Switch com Efeito Hall para Nintendo Switch, iPhone, Celulares Android, PC Windows"
    c = "GameSir Nova Lite Controle Sem Fio, Controlador de Jogos Bluetooth com Efeito Hall para Switch, Android, iOS"
    assert parecidos(a, 107.16, b, 106.58) and parecidos(a, 107.16, c, 111.31) and parecidos(b, 106.58, c, 111.31)
    assert not parecidos("Monitor Gamer Samsung Odyssey G5 34 Uwqhd", 1364.1, "Monitor Gamer Samsung Odyssey G5 32'' QHD 165Hz", 910.0)
    assert not parecidos("Jogo Dark Souls Remastered - Xbox", 24.39, "Jogo Sekiro: Shadows Die Twice GOTY - Xbox", 55.89)
    assert not parecidos("Console PS5 Slim Digital 825GB Branco", 3689.0, "Console PS5 Slim Digital 1TB Branco", 3700.0)
    assert not parecidos(a, 107.16, "GameSir Nova Lite Controle Sem Fio para Jogos", 300.0)  # preço muito diferente = outro item


def test_cozinha_nao_e_tecnologia():
    from app.engine import is_tech
    assert not is_tech("Mini Processador Manual 3 Lâminas Aço Inoxidável")
    assert is_tech("Processador AMD Ryzen 5 5600")


def test_regras_dos_programas_de_afiliado():
    from types import SimpleNamespace as N
    from app.engine import cupom_proibido
    from app.templates import render
    assert cupom_proibido("https://www.kabum.com.br/produto/1/x") and cupom_proibido("https://shop.samsung.com/br/x")
    assert not cupom_proibido("https://www.amazon.com.br/dp/B0G1TMXHRZ")
    base = dict(title="Processador AMD Ryzen 5 5600", post_title=None, price=799.0, old_price=None, payment=None, affiliate_url=None)
    kabum = render(N(url="https://www.kabum.com.br/produto/1/x", coupon="KORUJAOHARD", **base), "whatsapp")
    assert "KORUJAOHARD" not in kabum and "enquanto durarem os estoques" in kabum
    amazon = render(N(url="https://www.amazon.com.br/dp/B0G1TMXHRZ", coupon="LAPTOP200", **base), "whatsapp")
    assert "LAPTOP200" in amazon and "lote de cupons" in amazon
