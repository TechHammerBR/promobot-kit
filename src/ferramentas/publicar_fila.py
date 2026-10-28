"""Entrega os Reels prontos da fila (/srv/cache/reels-prontos) na hora marcada. Rodado pelo timer promobot-fila-reels a cada 5 min.
Uso: python ferramentas/publicar_fila.py [processar|estado]"""
import json
import sys

sys.path.insert(0, "/opt/promobot")
from app import fila_reels  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "processar"
    if cmd == "estado":
        print(json.dumps(fila_reels.resumo(), ensure_ascii=False, indent=1))
    else:
        n = fila_reels.processar()
        if n:
            print(f"publicados: {n}")
