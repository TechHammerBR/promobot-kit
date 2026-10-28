"""Envio para todos os canais configurados: Telegram (Bot API) e WhatsApp (conector próprio `wa`).

Sem nenhum canal configurado: simulação em data/outbox.log.
"""
import base64
import html

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import DATA_DIR, settings
from app.db import Offer
from app.log import log
from app.media import photo_url
from app.templates import render


def any_channel() -> bool:
    return bool(settings.telegram_bot_token or settings.whatsapp_group_name)


def format_message(o: Offer) -> str:
    return render(o, "telegram")


class TelegramError(Exception):
    pass


@retry(retry=retry_if_exception_type((httpx.HTTPError, TelegramError)),
       stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=60), reraise=True)
def _send(chat_id: str, text: str, photo: bytes | None = None) -> None:
    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    if photo:
        r = httpx.post(f"{base}/sendPhoto", timeout=30, files={"photo": ("foto.jpg", photo, "image/jpeg")},
                       data={"chat_id": chat_id, "caption": text, "parse_mode": "HTML"})
    else:
        r = httpx.post(f"{base}/sendMessage", timeout=20,
                       data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                             "link_preview_options": '{"is_disabled": true}'})
    if r.status_code == 429:
        raise TelegramError("rate limited")
    if r.status_code >= 500:
        raise TelegramError(f"telegram {r.status_code}")
    r.raise_for_status()


_wa_group_id: str | None = None


def _wa_target() -> str:
    """Resolve o grupo do WhatsApp pelo nome (WHATSAPP_GROUP_NAME) e guarda o id."""
    global _wa_group_id
    if _wa_group_id is None:
        groups = httpx.get(f"{settings.wa_url}/groups", timeout=60).raise_for_status().json()
        name = settings.whatsapp_group_name.strip().lower()
        _wa_group_id = next((g["id"] for g in groups if (g["name"] or "").strip().lower() == name), None)
        if not _wa_group_id:
            raise RuntimeError(f"grupo do WhatsApp '{settings.whatsapp_group_name}' não encontrado")
    return _wa_group_id


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=30), reraise=True)
def _send_whatsapp(text: str, photo: bytes | None, to: str | None = None) -> None:
    body = {"to": to or _wa_target(), "text": text}
    if photo:
        body["image_b64"] = base64.b64encode(photo).decode()
    r = httpx.post(f"{settings.wa_url}/send", json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"whatsapp: {r.text[:200]}")


def publish(o: Offer, photo: bytes | None, canal: str = "tech") -> None:
    """Publica uma oferta em todos os canais (foto obrigatória). Canal "lar": só o grupo de avisos da comunidade de casa."""
    if canal == "lar":
        if not photo:
            raise RuntimeError("post sem foto bloqueado")
        _send_whatsapp(render(o, "whatsapp", canal="lar"), photo, to=settings.lar_whatsapp_group_id)
        return
    if not any_channel():
        with open(DATA_DIR / "outbox.log", "a", encoding="utf-8") as f:
            f.write(render(o, "whatsapp") + "\n" + "-" * 40 + "\n")
        log.info("simulated_post", offer_id=o.id)
        return
    send_post({"telegram": render(o, "telegram"), "whatsapp": render(o, "whatsapp")}, photo)


def send_post(texts: dict[str, str], photo: bytes | None) -> None:
    """Envia o mesmo post (texto por canal + foto) a todos os canais; falha só se TODOS falharem."""
    if not photo:
        raise RuntimeError("post sem foto bloqueado")
    errors, sent = [], 0
    if settings.telegram_post_enabled and settings.telegram_bot_token and settings.telegram_channel_id:
        try:
            _send(settings.telegram_channel_id, texts["telegram"], photo)
            sent += 1
        except Exception as e:
            errors.append(f"telegram: {e}")
    if settings.whatsapp_group_name:
        try:
            _send_whatsapp(texts["whatsapp"], photo)
            sent += 1
        except Exception as e:
            errors.append(f"whatsapp: {e}")
    for err in errors:
        log.error("channel_failed", error=err[:300])
    if not sent:
        raise RuntimeError("; ".join(errors) or "nenhum canal configurado")


def alert(message: str) -> None:
    """Sem notificações ao dono (decisão 07/10/2026): registra no log e em data/alertas.log, que o Claude consulta
    (`python -m app.ctl alertas`). Nada é enviado para WhatsApp/Telegram."""
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    log.warning("alert", message=message)
    try:
        with open(DATA_DIR / "alertas.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({"quando": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
                                "msg": message}, ensure_ascii=False) + "\n")
    except OSError as e:
        log.error("alert_file_failed", error=str(e)[:200])


__all__ = ["publish", "send_post", "alert", "any_channel", "photo_url"]
