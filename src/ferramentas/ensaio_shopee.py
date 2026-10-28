import sys
import time

sys.path.insert(0, "/opt/promobot")
from app.collectors.shopee import STATE, ShopeeCollector
from app.config import settings
from app.db import SessionLocal
from app.engine import evaluate, product_key
from app.titles import limpar

settings.shopee_keywords_per_cycle = 14
antes = STATE.read_text() if STATE.exists() else None
t = time.time()
r = ShopeeCollector().collect()
print(len(r), "ofertas de marca/loja oficial em", round(time.time() - t), "s")
ok = 0
with SessionLocal() as s:
    for o in r:
        motivo = evaluate(o, s, product_key(str(o.url)))
        if motivo is None:
            ok += 1
            print(f"{o.price:>8.2f} -{o.discount_pct:>2}% {o.nota} {o.vendas:>5} | {limpar(o.title)}")
print("passariam no filtro de desconto/tecnologia:", ok)
if antes is None:
    STATE.unlink(missing_ok=True)
else:
    STATE.write_text(antes)
