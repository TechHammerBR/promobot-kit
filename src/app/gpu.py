"""Coordena a GPU de 8 GB com o laboratório de voz (/opt/apps/voicelab).

O laboratório cria data/gpu/busy enquanto treina/gera voz (e descarrega o modelo do Ollama). Nesse intervalo as chamadas
à IA local esperam aqui em vez de recarregar o modelo e brigar pela memória de vídeo.
"""
import time

import httpx

from app.config import DATA_DIR

LOCK = DATA_DIR / "gpu" / "busy"
STALE_S = 3 * 3600  # trava mais velha que isso = laboratório caiu; ignora


def busy() -> bool:
    try:
        return LOCK.exists() and time.time() - LOCK.stat().st_mtime < STALE_S
    except OSError:
        return False


def wait(max_s: int = 1500) -> None:
    t0 = time.time()
    while busy() and time.time() - t0 < max_s:
        time.sleep(5)


def post(url: str, tries: int = 3, espera: float = 12.0, **kw) -> httpx.Response:
    """httpx.post para o Ollama, esperando o laboratório de voz soltar a GPU. Se o Ollama devolver erro 5xx ou cair (ele reinicia o runner sozinho e recarrega
    o modelo em segundos), tenta de novo: antes uma falha momentânea virava rejeição DEFINITIVA da oferta (08/10: 23 ofertas rejeitadas)."""
    for k in range(tries):
        wait()
        try:
            r = httpx.post(url, **kw)
            if r.status_code < 500 or k == tries - 1:
                return r  # na última tentativa devolve o que veio (o chamador já trata o erro como antes)
        except httpx.HTTPError:
            if k == tries - 1:
                raise
        time.sleep(espera)
    raise RuntimeError("gpu.post sem tentativas")
