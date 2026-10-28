import sqlite3
import sys

sys.path.insert(0, "/opt/promobot")
from app.titles import limpar, mal_traduzido, marca, parecidos

db = sqlite3.connect("file:/opt/promobot/data/promobot.db?mode=ro", uri=True)
modo = sys.argv[1] if len(sys.argv) > 1 else "fila"
if modo == "posts":
    rows = db.execute("select id, source, price, title from offers where status='posted' order by posted_at").fetchall()
    vistos = []
    for i, s, p, t in rows:
        dup = next((v for v in vistos if parecidos(t, p, v[1], v[0])), None)
        m = marca(t) if s == "aliexpress" else "-"
        flag = "REPETIDO " if dup else ""
        flag += "SEM-MARCA " if m is None else ""
        flag += "TRAD " if s == "aliexpress" and mal_traduzido(t) else ""
        print(f"{flag or 'ok ':<22}| {limpar(t)}")
        vistos.append((p, t))
else:
    rows = db.execute("select price, title from offers where status in ('new','pending') and source='aliexpress' order by score desc").fetchall()
    ok = sem = trad = 0
    for p, t in rows:
        m = marca(t)
        if m is None:
            sem += 1
            if modo == "sem":
                print("SEM", t[:90])
        elif mal_traduzido(t):
            trad += 1
            if modo == "sem":
                print("TRAD", t[:90])
        else:
            ok += 1
            if modo == "fila":
                print(f"{m:<12}| {limpar(t)}")
    print("passam", ok, "sem marca", sem, "mal traduzido", trad)
