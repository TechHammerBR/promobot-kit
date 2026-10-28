"""Avaliador de foto sem IA: imagens sintéticas que imitam os casos reais (catálogo, cena, propaganda, colagem, kit, capa)."""
import io
import random

from PIL import Image, ImageDraw

from app import photocheck
from app.config import settings
from app.media import validate_photo


def catalogo(fundo=(255, 255, 255), cor=(40, 40, 40)) -> Image.Image:
    im = Image.new("RGB", (800, 800), fundo)
    ImageDraw.Draw(im).rounded_rectangle([220, 250, 580, 560], radius=30, fill=cor)
    return im


def com_texto(im: Image.Image, linhas: int = 3, letras: int = 9, cor=(20, 20, 20)) -> Image.Image:
    d = ImageDraw.Draw(im)
    for li in range(linhas):
        for k in range(letras):
            x, y = 80 + k * 46, 60 + li * 60
            d.rectangle([x, y, x + 28, y + 36], fill=cor)
    return im


def cena() -> Image.Image:
    random.seed(3)
    im = Image.new("RGB", (800, 800))
    d = ImageDraw.Draw(im)
    for _ in range(400):
        x, y = random.randint(0, 800), random.randint(0, 800)
        d.rectangle([x, y, x + random.randint(30, 160), y + random.randint(30, 160)],
                    fill=tuple(random.randint(0, 255) for _ in range(3)))
    return im


def jpeg(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)
    return b.getvalue()


def test_produto_em_fundo_branco_passa():
    ok, motivo, m = photocheck.avaliar(catalogo())
    assert ok and m["medios"] == 0 and m["letras"] == 0, motivo


def test_produto_em_fundo_escuro_liso_passa():
    assert photocheck.avaliar(catalogo(fundo=(12, 12, 14), cor=(200, 60, 60)))[0]


def test_cena_com_fundo_irregular_reprova():
    ok, motivo, _ = photocheck.avaliar(cena())
    assert not ok and "fundo irregular" in motivo


def test_texto_de_propaganda_reprova():
    ok, motivo, m = photocheck.avaliar(com_texto(catalogo()))
    assert not ok and "texto" in motivo and m["letras"] >= 10


def test_pouco_texto_passa_no_modo_normal():
    assert photocheck.avaliar(com_texto(catalogo(), linhas=1, letras=4))[0]


def test_arte_escura_que_encosta_nas_bordas_reprova():
    im = Image.new("RGB", (800, 800), (10, 10, 30))
    ImageDraw.Draw(im).rectangle([0, 150, 799, 700], fill=(180, 180, 200))  # faixa de lado a lado
    ok, motivo, _ = photocheck.avaliar(im)
    assert not ok


def test_colagem_de_objetos_diferentes_reprova():
    im = Image.new("RGB", (800, 800), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([60, 60, 420, 420], fill=(30, 30, 30))
    d.rectangle([500, 80, 640, 200], fill=(120, 40, 160))
    d.rectangle([520, 300, 760, 520], fill=(30, 120, 200))
    d.rectangle([120, 520, 300, 720], fill=(30, 160, 60))
    ok, motivo, m = photocheck.avaliar(im)
    assert not ok and "colagem" in motivo and not m["kit"]


def test_kit_de_itens_iguais_passa():
    im = Image.new("RGB", (900, 600), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for r in range(2):
        for c in range(6):
            d.ellipse([60 + c * 135, 110 + r * 220, 150 + c * 135, 260 + r * 220], fill=(35, 35, 35))
    ok, motivo, m = photocheck.avaliar(im)
    assert ok and m["kit"], motivo


def test_selo_vermelho_no_canto_reprova_e_logo_amarelo_nao():
    im = catalogo()
    ImageDraw.Draw(im).ellipse([620, 40, 760, 180], fill=(230, 20, 20))
    assert "selo" in photocheck.avaliar(im)[1]
    im = catalogo()
    ImageDraw.Draw(im).rectangle([40, 40, 150, 130], fill=(250, 220, 0))
    assert photocheck.avaliar(im)[0]


def test_foto_pequena_e_faixa_muito_larga_reprovam():
    assert "pequena" in photocheck.avaliar(Image.new("RGB", (150, 150), (255, 255, 255)))[1]
    assert "faixa" in photocheck.avaliar(Image.new("RGB", (1600, 300), (255, 255, 255)))[1]


def test_teclado_largo_em_fundo_branco_passa():
    im = Image.new("RGB", (1200, 520), (255, 255, 255))
    ImageDraw.Draw(im).rounded_rectangle([60, 90, 1140, 430], radius=20, fill=(50, 50, 55))
    assert photocheck.avaliar(im)[0]


def test_parece_jogo():
    assert photocheck.parece_jogo("Sekiro: Shadows Die Twice - PS4")
    assert photocheck.parece_jogo("Qualquer coisa", "https://store.steampowered.com/app/1/")
    assert photocheck.parece_jogo("Jogo Dark Souls Remastered Nintendo Switch")
    assert not photocheck.parece_jogo("Controle sem fio DualSense PS5")
    assert not photocheck.parece_jogo("Headset Gamer HyperX Cloud para Xbox")
    assert not photocheck.parece_jogo("SSD Kingston NV3 1TB")


def test_validate_photo_sem_ia_usa_as_regras(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    assert validate_photo(jpeg(catalogo()), "SSD 1TB") == (True, "regra: produto em fundo uniforme")
    ok, motivo = validate_photo(jpeg(cena()), "SSD 1TB")
    assert not ok and motivo.startswith("regra: fundo irregular")
    ok, motivo = validate_photo(jpeg(catalogo(fundo=(12, 12, 14), cor=(200, 60, 60))), "Cooler RGB")
    assert ok and motivo.startswith("regra:")


def test_capa_de_jogo_passa_so_quando_e_jogo(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    capa = jpeg(cena())
    assert validate_photo(capa, "Sekiro PS4", game=True) == (True, "regra: capa de jogo")
    assert not validate_photo(capa, "Sekiro PS4", game=False)[0]


def test_fundo_branco_com_texto_nao_passa_pelo_atalho_antigo(monkeypatch):
    """Sem IA, a borda branca sozinha não aprova: propaganda em fundo branco tem de ser reprovada pelo texto."""
    monkeypatch.setattr(settings, "ai_enabled", False)
    ok, motivo = validate_photo(jpeg(com_texto(catalogo())), "Webcam 4K")
    assert not ok and "texto" in motivo
