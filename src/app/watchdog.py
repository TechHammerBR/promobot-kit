"""Vigia do WhatsApp: avisa o dono (alert → Telegram admin) quando a conexão cai e quando volta."""
import httpx

from app.config import settings
from app.log import log

_down_checks = 0
_alerted = False


def check_whatsapp() -> None:
    global _down_checks, _alerted
    if not settings.whatsapp_group_name:
        return
    try:
        ok = httpx.get(f"{settings.wa_url}/status", timeout=15).json().get("connected", False)
    except Exception:
        ok = False
    from app.publisher import alert
    if ok:
        if _alerted:
            alert("WhatsApp reconectado. Publicações voltaram ao normal.")
        _down_checks, _alerted = 0, False
        return
    _down_checks += 1
    log.warning("wa_down", checks=_down_checks)
    if _down_checks >= 2 and not _alerted:  # ~10 min fora do ar
        _alerted = True
        alert("WhatsApp do robô DESCONECTADO há ~10 min. Peça um novo código de pareamento ao Claude "
              "(WhatsApp > Aparelhos conectados > Conectar com número de telefone).")
