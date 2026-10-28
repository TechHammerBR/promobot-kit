"""Stories em VÍDEO (até 60 s, 9:16): Instagram (media_type=STORIES, upload direto) + Página do Facebook (video_stories, 3 fases).
`testar()` faz tudo até o ponto antes de publicar (cria o contêiner e envia o arquivo), para validar sem postar nada."""
import time

import httpx

from app.config import settings
from app.log import log
from app.social import _api


def _enviar(uri: str, video: bytes) -> None:
    r = httpx.post(uri, content=video, timeout=600, headers={"Authorization": f"OAuth {settings.meta_page_token}", "offset": "0", "file_size": str(len(video))})
    r.raise_for_status()


def instagram(video: bytes, publicar: bool = True) -> str | None:
    c = _api("POST", f"{settings.meta_ig_id}/media", media_type="STORIES", upload_type="resumable")
    _enviar(c["uri"], video)
    for _ in range(60):
        st = _api("GET", c["id"], fields="status_code,status")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"instagram recusou o vídeo: {st.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError("instagram: o vídeo não terminou de processar")
    return _api("POST", f"{settings.meta_ig_id}/media_publish", creation_id=c["id"])["id"] if publicar else c["id"]


def pagina(video: bytes, publicar: bool = True) -> str | None:
    s = _api("POST", f"{settings.meta_page_id}/video_stories", upload_phase="start")
    _enviar(s["upload_url"], video)
    if not publicar:
        return s["video_id"]
    _api("POST", f"{settings.meta_page_id}/video_stories", upload_phase="finish", video_id=s["video_id"])
    return s["video_id"]


def publicar(video: bytes) -> list[str]:
    """-> redes em que saiu ([] se nenhuma)."""
    done = []
    for nome, f in (("instagram", instagram), ("facebook", pagina)):
        try:
            f(video)
            done.append(nome)
        except Exception as e:  # noqa: BLE001
            log.error("story_video_failed", net=nome, error=str(e)[:300])
    return done


def testar(video: bytes) -> dict:
    out = {}
    for nome, f in (("instagram", instagram), ("facebook", pagina)):
        try:
            out[nome] = "ok: " + str(f(video, publicar=False))
        except Exception as e:  # noqa: BLE001
            out[nome] = "ERRO: " + str(e)[:300]
    return out
