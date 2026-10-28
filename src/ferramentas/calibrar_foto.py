"""Reavalia a amostra congelada (rotulos_base.json + jpgs em cache) com o photocheck atual e compara com os rótulos."""
import io
import json
import sys
import time

from PIL import Image, ImageDraw

from app.photocheck import avaliar

CACHE = "/srv/cache/promobot/calib"
base = json.load(open(f"{CACHE}/rotulos_base.json"))
# rótulos dados olhando as folhas (índice da amostra): B = boa (deve passar), R = ruim (deve reprovar)
BOAS = [0, 3, 12, 18, 20, 25, 26, 27, 28, 29, 32, 34, 39, 43, 50, 52, 54, 57, 58, 61, 66, 51,
        72, 73, 74, 75, 76, 77, 79, 82, 83, 84, 86, 88, 89, 90, 92, 93, 95, 96, 97, 100, 101, 102, 103, 108, 109, 110, 111,
        114, 116, 118, 119, 122, 124, 126, 127, 130, 132, 134, 138, 139, 141]
RUINS = [2, 4, 5, 6, 7, 8, 9, 10, 11, 13, 16, 19, 22, 23, 24, 30, 35, 36, 38, 40, 42, 44, 46, 47, 48, 49, 53, 55, 56, 59, 60,
         62, 64, 65, 67, 68, 14, 15, 63, 69, 71, 31, 70, 41, 17, 21, 37]
CAPAS = [80, 85, 87, 91, 94, 98, 106, 113, 120, 125, 129, 133, 136, 142, 143]  # capas de jogo (tratadas pelo título)
out, thumbs, tempos = [], [], []
for o in base:
    im = Image.open(f"{CACHE}/{o['id']}.jpg").convert("RGB")
    t = time.time()
    ok, why, m = avaliar(im, o["ali"])
    tempos.append(time.time() - t)
    out.append({"i": o["i"], "ok": ok, "why": why, **{k: v for k, v in m.items() if k != "fundo"}})
    th = im.copy()
    th.thumbnail((200, 200))
    thumbs.append(th)
cab = ["i", "fundo_claro", "borda_suja", "frente", "fatia_maior", "medios", "resto", "linhas", "letras", "selos", "toca_bordas", "pecas"]


def lin(i):
    d = out[i]
    return " ".join(str(d[k]).rjust(6) for k in cab) + "  " + d["why"][:30]


fa = [i for i in RUINS if out[i]["ok"]]
fr = [i for i in BOAS if not out[i]["ok"]]
print("ms por foto (mediana):", round(sorted(tempos)[len(tempos) // 2] * 1000))
print(f"BOAS aprovadas: {len(BOAS) - len(fr)}/{len(BOAS)} | RUINS reprovadas: {len(RUINS) - len(fa)}/{len(RUINS)}")
print(" ".join(c[:6].rjust(6) for c in cab))
print("-- RUINS que passaram:", fa)
for i in fa:
    print(lin(i))
print("-- BOAS reprovadas:", fr)
for i in fr:
    print(lin(i))
if "--tudo" in sys.argv:
    print("-- BOAS")
    for i in BOAS:
        print(lin(i))
    print("-- RUINS")
    for i in RUINS:
        print(lin(i))
print("capas de jogo aprovadas pela foto:", [i for i in CAPAS if out[i]["ok"]])
if "--folhas" in sys.argv:
    C, R, S = 6, 4, 210
    for f in range(0, len(thumbs), C * R):
        sheet = Image.new("RGB", (C * S, R * (S + 18)), (90, 90, 90))
        d = ImageDraw.Draw(sheet)
        for k, th in enumerate(thumbs[f:f + C * R]):
            x, y = (k % C) * S, (k // C) * (S + 18)
            o = out[f + k]
            sheet.paste(th, (x + (S - th.width) // 2, y + 18 + (S - th.height) // 2))
            d.rectangle([x, y, x + S - 1, y + 17], fill=(0, 110, 0) if o["ok"] else (150, 0, 0))
            d.text((x + 3, y + 3), f"{o['i']} {'OK' if o['ok'] else o['why'][:26]}", fill=(255, 255, 255))
        sheet.save(f"/tmp/folha{f // (C * R)}.jpg", quality=72)
