from app.collectors.aliexpress import AliExpressCollector
from app.collectors.canais import CanaisCollector
from app.collectors.bonus import GatryCollector, PromobitCollector
from app.collectors.mercadolivre import MercadoLivreCollector
from app.collectors.pelando import PelandoCollector
from app.collectors.shopee import ShopeeCollector

# Ordem = prioridade. ML e Shopee monetizam; o resto é bônus de atração.
COLLECTORS = [MercadoLivreCollector, AliExpressCollector, CanaisCollector, PelandoCollector, ShopeeCollector, PromobitCollector, GatryCollector]
