"""PREVIA das artes das redes sociais (Story e feed) com a melhor oferta recente, SEM publicar nada e sem marcar a oferta como usada.

Uso (no servidor, na pasta /opt/promobot):  PYTHONPATH=/opt/promobot venv/bin/python ferramentas/social_previa.py [horas]
- Pega a oferta mais interessante ja 'postada' nas ultimas N horas (padrao 72; em modo simulacao as ofertas simuladas contam) e gera:
    data/previa/story-<id>.jpg  (1080x1920)  e  data/previa/feed-<id>.jpg  (1080x1350)
- Veja as imagens (scp para o seu computador) e so ligue SOCIAL_ENABLED=true quando aprovar o visual.
- Cores, nome da marca e chamada vem de BRAND_NAME, BRAND_COLOR, ACCENT_COLOR e SOCIAL_CTA no .env (docs/13-white-label.md)."""
import os
import sys
from pathlib import Path

from app import social
from app.social_art import render_art

horas = int(sys.argv[1]) if len(sys.argv) > 1 else 72
saida = Path(os.getenv("PROMOBOT_PREVIA", "/opt/promobot/data/previa"))
saida.mkdir(parents=True, exist_ok=True)
pick = social._pick(hours=horas)
if not pick:
    print(f"\n  Nenhuma oferta elegivel nas ultimas {horas} h. Deixe o robo rodar em simulacao por algumas horas (ou aumente as horas: ... social_previa.py 168).\n")
    sys.exit(1)
o, foto = pick
for fmt in ("story", "feed"):
    arq = saida / f"{fmt}-{o.id}.jpg"
    arq.write_bytes(render_art(o, foto, fmt))
    print(f"  previa {fmt}: {arq}")
print(f"\n  Oferta usada: {o.title[:70]}  (nada foi publicado nem marcado como usado)\n")
