import logging
import re
import sys
from logging.handlers import RotatingFileHandler

import structlog

from app.config import DATA_DIR


_SEGREDO = re.compile(r"(bot[0-9]{6,}:[A-Za-z0-9_-]{20,}|access_token=[^&\s\"]+|Bearer [A-Za-z0-9._-]{20,})")


def _ocultar(logger, method, event_dict):
    """Chave/token que aparecer num texto de erro nunca vai para o log."""
    for k, v in event_dict.items():
        if isinstance(v, str) and _SEGREDO.search(v):
            event_dict[k] = _SEGREDO.sub("<oculto>", v)
    return event_dict


def setup_logging() -> None:
    (DATA_DIR / "logs").mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        DATA_DIR / "logs" / "promobot.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        handlers=[logging.StreamHandler(sys.stdout), file_handler])
    structlog.configure(
        processors=[
            _ocultar,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


log = structlog.get_logger()

# não logar URLs de requisição (a do Telegram contém o token)
import logging as _logging
_logging.getLogger("httpx").setLevel(_logging.WARNING)
_logging.getLogger("httpcore").setLevel(_logging.WARNING)
