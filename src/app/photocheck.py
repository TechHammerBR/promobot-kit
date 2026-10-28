"""Avaliador de foto SEM IA (robô leve): decide por medidas da própria imagem se ela é "foto de catálogo".

Ideia: foto boa = um produto em destaque sobre um fundo uniforme (branco, cinza, preto ou colorido liso).
Foto ruim = cena/ambiente (fundo irregular), propaganda (texto grande, selos), colagem (vários objetos).

Como mede (só Pillow, ~0,2 s por foto no Atom do Wyse):
1) reduz a imagem a GRADE x GRADE; cor do fundo = mediana do anel externo; "borda_suja" = quanto do anel foge dessa cor;
2) máscara = pixels diferentes do fundo; componentes ligados (busca em largura);
3) produto = maior componente; "medios" = outros objetos grandes (colagem); selos = mancha de cor forte num canto;
4) texto = componentes pequenos, de altura parecida, alinhados na mesma linha (letras). "letras" = quantas letras em linhas assim.
medir() devolve as medidas (para calibrar e para o log); avaliar() aplica os limites e devolve (ok, motivo, medidas).
Calibrado em 13/10/2026 com 144 fotos reais da fila (ver CLAUDE.md, "FOTO SEM IA").
"""
import io
from collections import deque

from PIL import Image

GRADE = 160
ANEL = 6
TOL_FUNDO = 30  # diferença máxima (por canal) para um pixel ainda ser "fundo"


def _mediana(vals: list[int]) -> int:
    vals = sorted(vals)
    return vals[len(vals) // 2]


def _componentes(mask: list[list[bool]]) -> list[dict]:
    n = len(mask)
    visto = [[False] * n for _ in range(n)]
    comps = []
    for y0 in range(n):
        linha = mask[y0]
        for x0 in range(n):
            if not linha[x0] or visto[y0][x0]:
                continue
            fila = deque([(x0, y0)])
            visto[y0][x0] = True
            area, x1, y1, x2, y2 = 0, x0, y0, x0, y0
            while fila:
                x, y = fila.popleft()
                area += 1
                if x < x1:
                    x1 = x
                elif x > x2:
                    x2 = x
                if y > y2:
                    y2 = y
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < n and 0 <= ny < n and mask[ny][nx] and not visto[ny][nx]:
                        visto[ny][nx] = True
                        fila.append((nx, ny))
            comps.append({"area": area, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": x2 - x1 + 1, "h": y2 - y1 + 1})
    comps.sort(key=lambda c: -c["area"])
    return comps


def _linhas_de_texto(resto: list[dict], n: int) -> tuple[int, int]:
    """(linhas, letras): letras = componentes pequenos de altura parecida alinhados na horizontal (4 ou mais por linha)."""
    hmin, hmax, wmax = max(2, n // 64), n // 7, n // 5
    cand = [c for c in resto if hmin <= c["h"] <= hmax and c["w"] <= wmax and c["area"] >= 3]
    cand.sort(key=lambda c: (c["y1"] + c["y2"]) / 2)
    linhas = letras = 0
    usado = [False] * len(cand)
    for i, c in enumerate(cand):
        if usado[i]:
            continue
        cy, h = (c["y1"] + c["y2"]) / 2, c["h"]
        grupo = [i]
        for j in range(i + 1, len(cand)):
            d = cand[j]
            dy = (d["y1"] + d["y2"]) / 2 - cy
            if dy > max(2.0, h * 0.35):
                break
            if not usado[j] and 0.6 * h <= d["h"] <= 1.6 * h:
                grupo.append(j)
        if len(grupo) >= 4:
            xs = [cand[k]["x1"] for k in grupo] + [cand[k]["x2"] for k in grupo]
            if max(xs) - min(xs) >= n * 0.12:
                linhas += 1
                letras += len(grupo)
                for k in grupo:
                    usado[k] = True
    return linhas, letras


def medir(img: Image.Image) -> dict:
    """Medidas da imagem (frações de 0 a 1, salvo contagens). Não decide nada."""
    w, h = img.size
    small = img.convert("RGB").resize((GRADE, GRADE), Image.BILINEAR)
    px = small.load()
    n = GRADE
    anel = [px[x, y] for y in range(n) for x in range(n) if x < ANEL or y < ANEL or x >= n - ANEL or y >= n - ANEL]
    fundo = tuple(_mediana([p[c] for p in anel]) for c in range(3))
    fr, fg, fb = fundo

    def fora(p) -> bool:
        return abs(p[0] - fr) > TOL_FUNDO or abs(p[1] - fg) > TOL_FUNDO or abs(p[2] - fb) > TOL_FUNDO

    borda_suja = sum(1 for p in anel if fora(p)) / len(anel)
    mask = [[fora(px[x, y]) for x in range(n)] for y in range(n)]
    total = n * n
    frente = sum(sum(linha) for linha in mask)
    comps = _componentes(mask)
    maior = comps[0] if comps else {"area": 0, "x1": 0, "y1": 0, "x2": 0, "y2": 0, "w": 0, "h": 0}
    resto = comps[1:]
    medios = [c for c in resto if c["area"] >= total * 0.012]
    grandes = [maior["area"]] + [c["area"] for c in medios]
    kit = len(grandes) >= 4 and max(grandes) <= 1.6 * min(grandes)  # várias unidades iguais do mesmo produto (kit), não colagem
    linhas, letras = _linhas_de_texto(resto, n)
    # selo promocional: mancha de cor forte (vermelho/laranja/amarelo) pequena, num canto, separada do produto
    hsv = small.convert("HSV").load()
    selos = 0
    for c in resto:
        if not (total * 0.003 <= c["area"] <= total * 0.08):
            continue
        cx, cy = (c["x1"] + c["x2"]) / 2, (c["y1"] + c["y2"]) / 2
        if not ((cx < n * 0.33 or cx > n * 0.67) and (cy < n * 0.33 or cy > n * 0.67)):
            continue
        amostra = [hsv[x, y] for y in range(c["y1"], c["y2"] + 1, 2) for x in range(c["x1"], c["x2"] + 1, 2) if mask[y][x]]
        if amostra:
            # só vermelho/laranja (selo de oferta); amarelo fica de fora: é cor comum de logotipo de marca
            forte = sum(1 for (hh, ss, vv) in amostra if ss > 140 and vv > 120 and (hh < 28 or hh > 240)) / len(amostra)
            if forte > 0.55:
                selos += 1
    toca = sum([maior["x1"] <= 1, maior["y1"] <= 1, maior["x2"] >= n - 2, maior["y2"] >= n - 2]) if comps else 0
    return {
        "lado_min": min(w, h), "proporcao": round(max(w, h) / max(1, min(w, h)), 2),
        "fundo": fundo, "fundo_claro": round(sum(fundo) / 3),
        "borda_suja": round(borda_suja, 3), "frente": round(frente / total, 3),
        "fatia_maior": round(maior["area"] / frente, 3) if frente else 0.0,
        "medios": len(medios), "resto": round((frente - maior["area"]) / total, 3),
        "linhas": linhas, "letras": letras, "selos": selos, "toca_bordas": toca, "pecas": len(comps), "kit": kit,
    }


def avaliar(img: Image.Image, tolerante: bool = False) -> tuple[bool, str, dict]:
    """(aprovada, motivo, medidas). tolerante = AliExpress (as fotos de lá quase sempre têm algum texto)."""
    m = medir(img)
    if m["lado_min"] < 200:
        return False, "foto pequena demais", m
    if m["proporcao"] > 3.2:
        return False, "formato de faixa/banner", m
    claro = m["fundo_claro"] >= 200
    if m["borda_suja"] > (0.38 if claro else 0.20):  # 23/10: era 0.30/0.12 (barrava 234 ofertas de casa em 3 h)
        return False, "fundo irregular (cena ou banner)", m
    if not claro and m["toca_bordas"] >= 3:
        return False, "arte de fundo escuro/colorido", m
    if m["frente"] < 0.03:
        return False, "quase vazia", m
    if m["frente"] > 0.92:
        return False, "sem fundo livre", m
    # 28/10/2026: textura/cena sem produto (ex.: quadro de VIDEO do anuncio ML, retrato 9:16, madeira): muitos pedacinhos e nenhum objeto grande.
    # Calibrado em 250 fotos postadas: so a madeira (101 pedacos, maior objeto 4,9%) cai aqui; produto bom tem objeto >= 10% ou poucos pedacos.
    maior = round(m["fatia_maior"] * m["frente"], 3)
    if (m["pecas"] >= 70 and maior < 0.10) or (m["proporcao"] >= 1.7 and maior < 0.12):
        return False, f"sem produto em destaque (textura/cena) [maior {maior} pecas {m['pecas']}]", m
    if m["selos"] >= 1:
        return False, "selo promocional no canto", m
    if m["letras"] >= (8 if tolerante else 10) or m["linhas"] >= 3:
        return False, f"texto de propaganda ({m['letras']} letras)", m
    if m["medios"] >= 3 and not m["kit"]:
        return False, f"colagem ({m['medios'] + 1} objetos)", m
    if m["medios"] >= 2 and m["letras"] >= 4:
        return False, "vários objetos com texto", m
    return True, "produto em fundo uniforme", m


def avaliar_jpeg(jpeg: bytes, tolerante: bool = False) -> tuple[bool, str, dict]:
    return avaliar(Image.open(io.BytesIO(jpeg)), tolerante)


# --- capa de jogo: para um JOGO a "foto do produto" é a arte da capa (fundo cheio, título grande): a regra de catálogo não vale
LOJAS_DE_JOGO = ("store.steampowered.com", "steampowered.com", "store.playstation.com", "nintendo.com", "xbox.com", "epicgames.com",
                 "gog.com", "nuuvem.com", "greenmangaming.com", "humblebundle.com", "ea.com", "ubisoft.com", "battle.net")
PALAVRAS_JOGO = ("jogo ", "game ", " ps4", " ps5", "playstation", "xbox", "nintendo", "switch", "steam", "epic games", " gog",
                 "remastered", "remake", "goty", "game of the year", "deluxe edition", "edição deluxe", "mídia física", "midia fisica", "dlc")
NAO_E_JOGO = ("controle", "controller", "joystick", "gamepad", "console", "headset", "fone", "cabo", "capa ", "case", "película",
              "pelicula", "suporte", "carregador", "base ", "dock", "ssd", "hd ", "teclado", "mouse", "volante", "cadeira", "monitor",
              "tv ", "cartão de memória", "cartao de memoria", "memória", "skin", "grip", "bolsa", "mochila", "gift card", "cartão presente")


def parece_jogo(titulo: str, url: str = "") -> bool:
    """True se a oferta é um jogo (loja digital de jogos, ou título de jogo sem palavra de acessório/aparelho)."""
    u = (url or "").lower()
    if any(loja in u for loja in LOJAS_DE_JOGO):
        return True
    t = " " + (titulo or "").lower() + " "
    if any(w in t for w in NAO_E_JOGO):
        return False
    return any(w in t for w in PALAVRAS_JOGO)


def avaliar_capa(img: Image.Image) -> tuple[bool, str]:
    """Capa de jogo: basta ter tamanho e formato de capa (retrato, quadrada ou paisagem moderada)."""
    w, h = img.size
    if min(w, h) < 250:
        return False, "capa pequena demais"
    if max(w, h) / min(w, h) > 2.4:
        return False, "formato de faixa/banner"
    return True, "capa de jogo"
