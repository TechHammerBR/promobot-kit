import sys
import time

sys.path.insert(0, "/opt/promobot")
from app.collectors.canais import VISTOS, CanaisCollector

t = time.time()
r = CanaisCollector().collect()
print(len(r), "ofertas em", round(time.time() - t), "s")
for o in r:
    print(f"{o.price:>9.2f} | {o.coupon or '-':<12} | {o.title[:58]} | {str(o.url)[:62]}")
VISTOS.unlink(missing_ok=True)
