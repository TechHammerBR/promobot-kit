"""Ponto de entrada: `python -m app.main` (contínuo) ou `python -m app.main --once`."""
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from app import control
from app.config import settings
from app.db import init_db
from app.log import log, setup_logging
from app.coupons import collect_coupons, coupons_posted_today, post_coupons
from app.status_posts import post_status
from app.watchdog import check_whatsapp
from app.coupon_codes import post_codes_if_new
from app.pipeline import collect_all, next_delay_seconds, publish_next, run_cycle


def main() -> None:
    setup_logging()
    init_db()
    if "--once" in sys.argv:
        run_cycle()
        return
    sched = BlockingScheduler(timezone="America/Sao_Paulo")
    start = datetime.now(ZoneInfo("America/Sao_Paulo"))  # mesmo fuso do agendador
    sched.add_job(collect_all, "interval", minutes=settings.collect_interval_min,
                  max_instances=1, coalesce=True, next_run_time=start)

    rodando = {"publish": False, "publish_lar": False}  # a rodada sai da agenda enquanto executa; o control_watch não deve recriá-la

    def publish_lar_tick() -> None:  # canal de casa (comunidade): ritmo e limite próprios; pausa geral vale para os dois
        posted = False
        rodando["publish_lar"] = True
        try:
            if not control.paused(control.load()):
                posted = publish_next("lar")
        except Exception as e:  # noqa: BLE001
            log.error("publish_lar_erro", error=str(e)[:200])
        finally:
            delay = next_delay_seconds("lar") if posted else 120
            sched.add_job(publish_lar_tick, "date", run_date=datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(seconds=delay),
                          id="publish_lar", replace_existing=True, misfire_grace_time=None)
            rodando["publish_lar"] = False

    def publish_tick() -> None:
        posted, forced = False, False
        rodando["publish"] = True
        try:
            c = control.load()  # comandos da IA local (serviço ops): pausa, postar agora, cupons, ajustes
            control.apply_overrides(c)
            if c.get("coupons_now"):
                control.update(coupons_now=False)
                post_coupons()
            if control.paused(c):
                log.info("paused", until=c.get("paused_until"))
            elif c.get("post_now", 0) > 0:
                forced = True
                if publish_next():
                    control.update(post_now=control.load().get("post_now", 1) - 1)
            else:
                posted = publish_next()
        finally:  # reagenda sempre: intervalo aleatório após post; 1 min se não postou ou em "postar agora"
            delay = next_delay_seconds() if posted and not forced else 60
            sched.add_job(publish_tick, "date", run_date=datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(seconds=delay),
                          id="publish", replace_existing=True, misfire_grace_time=None)
            rodando["publish"] = False
            log.info("next_post_in", minutes=round(delay / 60, 1))

    # misfire_grace_time=None: roda mesmo atrasado. Em 13/10/2026 o relógio pulou 4 min ao ligar (acerto pela internet),
    # o agendador descartou a rodada como "perdida" e o robô ficou sem publicar até ser reiniciado.
    sched.add_job(publish_tick, "date", run_date=start + timedelta(seconds=90), id="publish", misfire_grace_time=None)
    if settings.lar_enabled:
        sched.add_job(publish_lar_tick, "date", run_date=start + timedelta(seconds=150), id="publish_lar", misfire_grace_time=None)

    def control_watch() -> None:  # "postar agora"/"cupons agora" da IA local: antecipa a rodada (até 30 s)
        c = control.load()
        job = sched.get_job("publish")
        soon = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(seconds=2)
        if settings.lar_enabled and not rodando["publish_lar"] and sched.get_job("publish_lar") is None:
            log.warning("publish_job_recriado", canal="lar")
            sched.add_job(publish_lar_tick, "date", run_date=soon, id="publish_lar", replace_existing=True, misfire_grace_time=None)
        if rodando["publish"]:
            return
        if job is None:  # rede de segurança: a rodada de publicação nunca pode sumir da agenda
            log.warning("publish_job_recriado")
            sched.add_job(publish_tick, "date", run_date=soon, id="publish", replace_existing=True, misfire_grace_time=None)
        elif (c.get("post_now", 0) > 0 or c.get("coupons_now")) and not control.paused(c):
            if job.next_run_time > soon + timedelta(seconds=5):
                sched.add_job(publish_tick, "date", run_date=soon, id="publish", replace_existing=True, misfire_grace_time=None)

    sched.add_job(control_watch, "interval", seconds=30, max_instances=1, coalesce=True)
    sched.add_job(collect_coupons, "interval", hours=settings.coupon_refresh_hours,
                  max_instances=1, coalesce=True, next_run_time=start + timedelta(minutes=3))
    sched.add_job(post_coupons, "cron", hour=settings.coupon_post_hour, minute=0, max_instances=1, coalesce=True)
    # recupera o post de cupons do dia se o robô estava desligado no horário (ex.: reinício do servidor)
    if settings.coupon_post_hour <= start.hour < 23 and not coupons_posted_today():
        sched.add_job(post_coupons, "date", run_date=start + timedelta(minutes=4))
    sched.add_job(post_codes_if_new, "interval", minutes=10, max_instances=1, coalesce=True,
                  next_run_time=start + timedelta(minutes=6))
    # agenda de posts de conteúdo (stories, feed, educativo, jogos, reels, token do Threads): app/catchup.py
    # (cada execução é registrada; se o servidor estava desligado no horário, o robô recupera sozinho)
    if settings.content_enabled:
        from app import catchup
        for name, hhmm, days, _tolerancia, _fn in catchup.schedule():
            hh, mm = (int(x) for x in hhmm.split(":"))
            kw = {} if days == "*" else {"day_of_week": days}
            sched.add_job(catchup.run, "cron", hour=hh, minute=mm, args=[name, hhmm], max_instances=1, coalesce=True, **kw)
        sched.add_job(catchup.recover, "interval", minutes=20, max_instances=1, coalesce=True, next_run_time=start + timedelta(minutes=3))
    from app.health import daily_report
    if settings.convite_enabled:
        from app.convites import enviar_lote
        hh, mm = (int(x) for x in settings.convite_hora.split(":"))
        sched.add_job(enviar_lote, "cron", hour=hh, minute=mm, max_instances=1, coalesce=True)
    if settings.content_enabled and settings.estudio_enabled:  # estúdio: recebe o que o PC escreveu e repõe as tarefas
        from app.estudio import ciclo as estudio_ciclo
        sched.add_job(estudio_ciclo, "interval", minutes=60, max_instances=1, coalesce=True,
                      next_run_time=start + timedelta(minutes=5))
    sched.add_job(daily_report, "cron", hour=23, minute=0, max_instances=1, coalesce=True)
    from app.report import diario as relatorio_diario
    sched.add_job(relatorio_diario, "cron", hour=23, minute=50, max_instances=1, coalesce=True)
    for i, hhmm in enumerate(t for t in settings.status_times.split(",") if t.strip()):
        hh, mm = (int(x) for x in hhmm.strip().split(":"))
        sched.add_job(post_status, "cron", hour=hh, minute=mm, args=["grupo" if i % 2 == 0 else "oferta"],
                      max_instances=1, coalesce=True)
    log.info("started", collect_min=settings.collect_interval_min, daily_limit=settings.daily_post_limit,
             interval=f"{settings.interval_min}-{settings.interval_max} min (pico {settings.peak_interval_min}-{settings.peak_interval_max})")
    sched.start()


if __name__ == "__main__":
    main()
