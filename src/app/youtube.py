"""YouTube Shorts (22/10/2026, pedido do dono: "sempre traga conteúdo também no YouTube"). Upload resumable com OAuth do dono (canal Tech Hammer).
Credenciais em data/youtube/{youtube_client.json,youtube_token.json} (chmod 600). Cada Reel da fila sai também como Short; falha aqui nunca derruba as outras redes."""
import json
import re
from datetime import datetime, timezone

import httpx

from app.config import DATA_DIR
from app.log import log

PASTA = DATA_DIR / "youtube"
_GRUPOS_OK = "chat.whatsapp.com"


def enabled() -> bool:
    return (PASTA / "youtube_client.json").exists() and (PASTA / "youtube_token.json").exists()


def _acesso() -> str:
    cli = json.loads((PASTA / "youtube_client.json").read_text(encoding="utf-8"))["installed"]
    tok = json.loads((PASTA / "youtube_token.json").read_text(encoding="utf-8"))
    r = httpx.post(cli["token_uri"], data={"client_id": cli["client_id"], "client_secret": cli["client_secret"],
                                            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


_CHAMAR = "nos comentários ou no Instagram @techhammer.br"


def _para_youtube(texto: str) -> str:
    """No YouTube não existe direct: chama nos comentários ou no Instagram."""
    texto = texto.replace("no direct do Instagram @techhammer.br", _CHAMAR)
    return re.sub(r"[Nn]o direct", _CHAMAR, texto)


def _titulo(legenda: str) -> str:
    linha = next((x.strip() for x in legenda.splitlines() if x.strip() and not x.strip().startswith("#")), "TechHammer")
    linha = re.sub(r"\s+", " ", linha)[:84].rstrip()
    return f"{linha} #Shorts"


def publicar_short(video: bytes, legenda: str, capa: bytes | None = None, publicar_em: datetime | None = None) -> str | None:
    """Sobe o vídeo como Short. Sem publicar_em: público na hora. Com publicar_em: privado + AGENDADO na própria plataforma (publishAt). Devolve o id (ou None)."""
    token = _acesso()
    descricao = _para_youtube(legenda.rstrip())
    if "#Shorts" not in descricao:
        descricao += "\n\n#Shorts"
    meta = {"snippet": {"title": _titulo(legenda), "description": descricao[:4900], "categoryId": "28", "defaultLanguage": "pt", "defaultAudioLanguage": "pt"},
            "status": ({"privacyStatus": "private", "publishAt": publicar_em.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0Z"),
                        "selfDeclaredMadeForKids": False} if publicar_em else {"privacyStatus": "public", "selfDeclaredMadeForKids": False})}
    h = {"Authorization": "Bearer " + token}
    r = httpx.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", json=meta, timeout=120,
                   headers={**h, "X-Upload-Content-Length": str(len(video)), "X-Upload-Content-Type": "video/mp4"})
    r.raise_for_status()
    loc = r.headers["Location"]
    up = httpx.put(loc, content=video, timeout=900, headers={"Content-Type": "video/mp4"})
    up.raise_for_status()
    vid = up.json()["id"]
    log.info("youtube_short_agendado" if publicar_em else "youtube_short_publicado", id=vid, mb=round(len(video) / 1e6, 1),
             quando=publicar_em.isoformat() if publicar_em else None)
    if capa:
        try:
            httpx.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", content=capa, timeout=120,
                       headers={**h, "Content-Type": "image/jpeg"}).raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("youtube_capa_falhou", error=str(e)[:150])
    return vid
