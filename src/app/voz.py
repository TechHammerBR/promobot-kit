"""Narração com a VOZ DO DONO nos vídeos: chama o serviço de voz do servidor (/opt/apps/voicelab, http://voice:8300).

O serviço gera várias versões de cada frase e o controle de qualidade local (Whisper + verificação de timbre) escolhe a melhor.
Desligado por padrão (VOICE_ENABLED=false) até o dono aprovar a voz. Se o serviço falhar, devolve None e o Reel sai SEM narração
(como antes): nunca trava a postagem.
"""
import base64
import time

import httpx

from app.config import settings
from app.log import log


def narrar(linhas: list[str]) -> list[tuple[bytes, float]] | None:
    """-> [(wav 24 kHz mono, segundos), ...] na ordem das linhas; None se desligada/indisponível."""
    if not settings.voice_enabled or not linhas:
        return None
    try:
        r = httpx.post(f"{settings.voice_url}/narrar", json={"linhas": linhas, "n": 3, "estilo": settings.voice_style}, timeout=1800)  # espera a GPU (IA do robô sai da frente)
        r.raise_for_status()
        itens = r.json()["itens"]
        if len(itens) != len(linhas):
            raise ValueError("quantidade de falas diferente do pedido")
        log.info("voz_ok", linhas=len(itens), estilo=settings.voice_style, sim=round(sum(i["sim"] for i in itens) / len(itens), 2),
                 sim_min=round(min(i["sim"] for i in itens), 2), versoes=sum(i.get("tentativas", 1) for i in itens))
        return [(base64.b64decode(i["wav_b64"]), float(i["segundos"])) for i in itens]
    except Exception as e:  # noqa: BLE001
        log.warning("voz_indisponivel", error=str(e)[:200])
        return None


def narrar_texto(texto: str, unidades: list[str]) -> dict | None:
    """Texto CORRIDO (várias frases) numa narração só -> {"wav": bytes, "segundos": s, "tempos": [[ini, fim], ...]} (tempo de cada unidade de legenda);
    None se desligada/indisponível. É o que acaba com a "colagem" de falas geradas separadas."""
    if not settings.voice_enabled or not texto:
        return None
    for tentativa in range(3):  # o serviço de voz reinicia sozinho se cair no meio (08/10: falha de segmentação); espera e tenta de novo
        try:
            r = httpx.post(f"{settings.voice_url}/narrar_texto", json={"texto": texto, "unidades": unidades, "n": 3, "estilo": settings.voice_style}, timeout=1800)
            r.raise_for_status()
            d = r.json()
            log.info("voz_texto_ok", segundos=d["segundos"], blocos=d["blocos"], sim=d["sim"], tom_st=d["st"], naturalidade=d["mos"], versoes=d["tentativas"])
            return {"wav": base64.b64decode(d["wav_b64"]), "segundos": float(d["segundos"]), "tempos": d["tempos"]}
        except Exception as e:  # noqa: BLE001
            log.warning("voz_indisponivel", error=str(e)[:200], tentativa=tentativa + 1)
            time.sleep(60)
    return None
