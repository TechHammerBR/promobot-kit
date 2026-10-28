"""Interface comum dos coletores, com retry e detecção de bloqueio."""
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.schemas import RawOffer

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


class BlockedError(Exception):
    """Captcha / 403 / 429: a fonte entra em espera, sem tentar burlar."""


class LayoutChangedError(Exception):
    """A página respondeu, mas nada foi extraído: provável mudança de layout."""


class Collector:
    name = "base"

    @classmethod
    def enabled(cls) -> bool:
        return True


    def __init__(self) -> None:
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"},
                                   timeout=20, follow_redirects=True)

    @retry(retry=retry_if_exception_type(httpx.TransportError),
           stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    def get(self, url: str) -> httpx.Response:
        r = self.client.get(url)
        if r.status_code in (403, 429) or "captcha" in r.text[:5000].lower():
            raise BlockedError(f"{self.name}: HTTP {r.status_code} em {url}")
        # ML: tela "verifique sua conta" (trafego suspeito) = bloqueio anti-robo, nao mudanca de layout
        if "account-verification" in str(r.url) or "suspicious-traffic" in r.text[:2000]:
            raise BlockedError(f"{self.name}: verificacao anti-robo em {url}")
        r.raise_for_status()
        return r

    def collect(self) -> list[RawOffer]:
        raise NotImplementedError


def ml_paused() -> bool:
    from datetime import date
    from app.config import settings
    return bool(settings.ml_paused_until) and date.today().isoformat() < settings.ml_paused_until
