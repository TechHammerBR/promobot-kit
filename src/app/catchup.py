"""Recuperação AUTOMÁTICA de posts agendados que perderam o horário (servidor desligado, reinício do robô, falta de luz...).

Cada execução agendada (story, feed, carrossel de jogos, reel, renovação de token) é registrada em data/schedule_state.json.
A cada 20 min (e 3 min depois de subir) o robô confere se algum horário de HOJE passou sem rodar e ainda está dentro da
tolerância — e roda sozinho. Ninguém precisa perceber nem mandar nada (decisão do dono: tudo fica a cargo do servidor).
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import DATA_DIR, settings
from app.log import log

TZ = ZoneInfo("America/Sao_Paulo")
STATE = DATA_DIR / "schedule_state.json"
DIAS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def schedule() -> list[tuple]:
    """(nome, "HH:MM", dias ("*" ou "mon,wed"), tolerância em horas, função). Única fonte da agenda de posts de conteúdo."""
    from app import social, threads
    from app.content import post_edu
    from app.games import post_gratis, post_weekly
    from app.semanal import post_radar, post_top5
    from app.estudio import post_novidade

    def post_free_reel():  # import só na hora: o Wyse não tem as bibliotecas de vídeo
        from app.game_reels import post_free_reel as f
        f()

    def post_promo_reel():
        from app.game_reels import post_promo_reel as f
        f()
    itens = [("story", t.strip(), "*", 3, social.post_story) for t in settings.social_story_times.split(",") if t.strip()]
    vendas = settings.feed_vendas_enabled
    itens += [
        *([("feed", settings.social_feed_time, settings.social_feed_days, 3, social.post_feed)] if vendas else []),
        *([("edu", settings.edu_time, settings.edu_day, 4, post_edu)] if settings.edu_enabled else []),
        *([("reel_gratis", "12:30", "thu", 5, post_free_reel), ("reel_promo", "19:20", settings.games2_day, 4, post_promo_reel)]
          if settings.reels_enabled else []),
        *([("jogos1", settings.games_time, settings.games_day, 5, post_gratis),  # qui 13h: JOGOS GRÁTIS DA SEMANA
           ("jogos2", settings.games2_time, settings.games2_day, 4, post_weekly)] if settings.games_enabled else []),
        *([("radar", "12:00", "fri", 5, post_radar), ("top5", "11:00", "sat", 5, post_top5)] if vendas else []),
        *([("reel_ofertas", settings.reel_ofertas_hora, "*", 3, __import__("app.reels", fromlist=["x"]).offers_reel)]
          if settings.reel_ofertas_enabled else []),
        *([("novidade", settings.estudio_hora, settings.estudio_dias, 5, post_novidade)] if settings.estudio_enabled else []),
        ("threads_token", "04:00", "sun", 20, threads.refresh),
    ]
    return itens


def _load() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    corte = (datetime.now(TZ) - timedelta(days=10)).strftime("%Y-%m-%d")
    d = {k: v for k, v in d.items() if k.split("@", 1)[-1][:10] >= corte}
    try:
        STATE.write_text(json.dumps(d))
    except OSError as e:
        log.error("schedule_state_failed", error=str(e)[:150])


def _chave(nome: str, hhmm: str, dia: datetime | None = None) -> str:
    return f"{nome}@{(dia or datetime.now(TZ)):%Y-%m-%d}T{hhmm}"


def run(nome: str, hhmm: str, dia: datetime | None = None) -> None:
    """Executa uma ocorrência agendada (uma vez só por dia/horário) e registra."""
    fn = next((f for n, h, _d, _g, f in schedule() if (n, h) == (nome, hhmm)), None)
    if fn is None:
        return
    d = _load()
    chave = _chave(nome, hhmm, dia)
    if chave in d:
        return
    d[chave] = datetime.now(TZ).isoformat(timespec="seconds")
    _save(d)  # marca ANTES: dois gatilhos quase juntos não repetem o post
    fn()


def recover(agora: datetime | None = None) -> list[str]:
    """Roda os horários de hoje que passaram sem executar (tolerância por tipo de post). Retorna o que recuperou."""
    agora = agora or datetime.now(TZ)
    feitos = []
    for nome, hhmm, dias, tolerancia_h, _fn in schedule():
        if dias != "*" and DIAS[agora.weekday()] not in [x.strip() for x in dias.split(",")]:
            continue
        h, m = (int(x) for x in hhmm.split(":"))
        previsto = agora.replace(hour=h, minute=m, second=0, microsecond=0)
        if not (previsto + timedelta(minutes=5) <= agora <= previsto + timedelta(hours=tolerancia_h)):
            continue  # ainda não chegou, acabou de chegar (o agendador normal cuida) ou passou do prazo
        if _chave(nome, hhmm, agora) in _load():
            continue
        log.warning("catchup_run", job=nome, previsto=hhmm)
        try:
            run(nome, hhmm, agora)
        except Exception as e:  # noqa: BLE001
            log.error("catchup_failed", job=nome, error=str(e)[:200])
        feitos.append(f"{nome}@{hhmm}")
    return feitos
