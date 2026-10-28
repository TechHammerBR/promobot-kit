"""Coleta (a cada COLLECT_INTERVAL_MIN) e publicação cadenciada (1 oferta por PUBLISH_INTERVAL_SEC).

O link de afiliado do ML (meli.la) é gerado só na hora de publicar, pelo navegador logado
(serviço linkgen): 1 geração por publicação = ritmo humano, sem chamar atenção do WAF.
"""
import random
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update

from app.affiliate import aliexpress_link, clean_url, is_aliexpress, is_mercadolivre, mercadolivre_page, to_affiliate
from app.collectors import COLLECTORS
from app.collectors.base import BlockedError, LayoutChangedError, ml_paused
from app.config import settings
from app.db import Offer, SessionLocal, SourceHealth, now
from app.engine import canal_de, evaluate, is_tech, product_key, score, queda_expressiva
from app.log import log
from app.ai import judge_ali, judge_offer, short_title
from app.photocheck import parece_jogo
from app.titles import mal_traduzido, marca, parecidos
from app import aliapi, awin, pricehist
from app.coupon_codes import sugerir as sugerir_cupom
from app.media import foto_pequena, product_jpeg, validate_photo
from app.publisher import alert, any_channel, publish
from app.storephoto import preco_amazon, store_photos
from app.alicheck import verificar as verificar_ali

ALERT_AFTER_FAILURES = 3
MAX_PUBLISH_ATTEMPTS = 20  # 23/10: era 6; com muita foto/repetida barrada o grupo de casa soltava 1 post a cada 30 min


def _health(session, name: str) -> SourceHealth:
    h = session.get(SourceHealth, name)
    if not h:
        h = SourceHealth(source=name, consecutive_failures=0)
        session.add(h)
    return h


def collect_all() -> None:
    with SessionLocal() as session:
        for cls in COLLECTORS:
            if not cls.enabled():
                continue
            h = _health(session, cls.name)
            if h.blocked_until and h.blocked_until.replace(tzinfo=now().tzinfo) > now():
                continue
            try:
                raw = cls().collect()
                if not raw and not getattr(cls, "empty_ok", False):
                    raise LayoutChangedError(f"{cls.name}: 0 ofertas extraídas")
            except Exception as e:
                h.consecutive_failures += 1
                h.last_error = str(e)
                if isinstance(e, BlockedError):
                    # espera crescente: 30min, 1h, 2h... até 12h
                    h.blocked_until = now() + timedelta(minutes=min(30 * 2 ** (h.consecutive_failures - 1), 720))
                log.error("collect_failed", source=cls.name, error=str(e), failures=h.consecutive_failures)
                if h.consecutive_failures == ALERT_AFTER_FAILURES:
                    alert(f"Fonte {cls.name} falhou {ALERT_AFTER_FAILURES}x seguidas: {e}")
                session.commit()
                continue

            h.consecutive_failures, h.last_ok, h.blocked_until = 0, now(), None
            new = 0
            batch_keys: set[str] = set()
            for item in raw:
                key = product_key(str(item.url))
                pricehist.registrar(session, key, item.price)
                canal = canal_de(item.title)
                reason = evaluate(item, session, key, canal) or ("duplicada no lote" if key in batch_keys else None)
                batch_keys.add(key)
                if not reason and settings.mix_enabled and loja_de(item.source, str(item.url)) == "outra":
                    reason = "loja sem afiliado (só Mercado Livre, Shopee e AliExpress)"
                if reason:
                    aff_url, monetized = None, False
                elif item.affiliate_url:
                    aff_url, monetized = item.affiliate_url, True
                elif ml_paused() and is_mercadolivre(str(item.url)):
                    aff_url, monetized = clean_url(str(item.url)), False  # afiliado ML suspenso: bônus sem comissão
                elif is_mercadolivre(str(item.url)) or is_aliexpress(str(item.url)):
                    aff_url, monetized = None, True  # link de afiliado gerado na hora de publicar
                else:
                    aff_url, monetized = to_affiliate(str(item.url))
                session.add(Offer(
                    fingerprint=item.fingerprint, product_key=key, source=item.source, title=item.title,
                    url=clean_url(str(item.url)), affiliate_url=aff_url, monetized=monetized,
                    price=item.price, old_price=item.old_price, coupon=item.coupon, image_url=item.image_url,
                    score=0 if reason else score(item, monetized),
                    status="rejected" if reason else ("pending" if settings.require_approval else "new"),
                    reason=reason, canal=canal,
                ))
                new += 0 if reason else 1
            session.commit()
            log.info("collected", source=cls.name, total=len(raw), approved=new)


class OfferGone(Exception):
    """A oferta acabou ou piorou entre a coleta e a publicação."""


def _ensure_link(o: Offer) -> list[str]:
    """ML: gera o meli.la e confere preço/foto na mesma visita à página do produto.

    Retorna as fotos da galeria do anúncio (reserva se a foto principal for reprovada).
    """
    if o.affiliate_url:
        return []
    if is_aliexpress(o.url):
        o.affiliate_url = aliexpress_link(o.url)
        return []
    if awin.aplicavel(o.url):  # loja da Awin em que a conta já foi aprovada (KaBuM)
        o.affiliate_url = awin.link(o.url)
        return []
    if not is_mercadolivre(o.url):
        return []
    info = mercadolivre_page(o.url, settings.ml_tag_lar if o.canal == "lar" else settings.ml_tag_tech)  # etiqueta por canal (Métricas do ML)
    if info.get("available") is False:
        raise OfferGone("produto indisponível")
    if info.get("price"):
        o.price = info["price"]
        if info.get("old_price"):
            o.old_price = info["old_price"]
        if not o.coupon and (not o.old_price or o.price >= o.old_price * (1 - settings.min_discount_pct / 100)):
            raise OfferGone(f"desconto caiu (agora R$ {o.price:.2f})")
    # foto principal = a do card da coleta (produto em destaque). Galeria só se o card veio sem foto:
    # a galeria mistura vídeos e fotos de propaganda.
    if not o.image_url and info.get("image") and "frontend-assets" not in info["image"]:
        o.image_url = info["image"]
    o.payment = info.get("installments")
    o.affiliate_url = info["link"]
    return info.get("gallery") or []


def _now_sp() -> datetime:
    return datetime.now(ZoneInfo("America/Sao_Paulo"))


def is_peak(hour: int) -> bool:
    for span in settings.peak_hours.split(","):
        a, b = (int(x) for x in span.split("-"))
        if a <= hour < b:
            return True
    return False


def next_delay_seconds(canal: str = "tech") -> float:
    """Intervalo aleatório até o próximo post (nunca fixo: intervalo fixo é assinatura de robô)."""
    if canal == "lar":
        if is_peak(_now_sp().hour):
            return random.uniform(settings.lar_peak_interval_min, settings.lar_peak_interval_max) * 60
        return random.uniform(settings.lar_interval_min, settings.lar_interval_max) * 60
    h = _now_sp().hour
    if any(int(a) <= h < int(b) for a, b in (f.split("-") for f in settings.night_hours.split(",") if "-" in f)):
        lo, hi = settings.night_interval_min, settings.night_interval_max
    elif is_peak(h):
        lo, hi = settings.peak_interval_min, settings.peak_interval_max
    else:
        lo, hi = settings.interval_min, settings.interval_max
    return random.uniform(lo, hi) * 60


def posts_today(canal: str = "tech") -> int:
    midnight = _now_sp().replace(hour=0, minute=0, second=0, microsecond=0)
    if settings.limit_reset_at:
        midnight = max(midnight, datetime.fromisoformat(settings.limit_reset_at))
    with SessionLocal() as s:
        return s.scalar(select(func.count(Offer.id)).where(Offer.status == "posted", Offer.posted_at >= midnight,
                                                           Offer.canal == canal)) or 0


def hora_ativa(h: int) -> bool:
    """Dentro do horário de posts? Fim acima de 24 = atravessa a meia-noite (6 -> 27 = das 6h às 3h do dia seguinte)."""
    ini, fim = settings.active_hour_start, settings.active_hour_end
    return ini <= h < fim if fim <= 24 else (h >= ini or h < fim - 24)


def in_active_hours() -> bool:
    return hora_ativa(datetime.now(ZoneInfo("America/Sao_Paulo")).hour)


_ml_ultimo_ok = 0.0  # última vez que um link meli.la foi gerado com sucesso (distingue falha da página de bloqueio geral/captcha do ML)
_ml_descanso_ate = 0.0  # enquanto o linkgen do ML falha (tela anti-robô), as ofertas ML sem link ficam esperando
ML_DESCANSO_SEG = 3600



def loja_de(source: str, url: str) -> str:
    """Loja REAL da oferta (pela URL, nao pela fonte): ml | shopee | ali | outra (sem afiliado)."""
    u = (url or "").lower()
    if source == "mercadolivre" or "mercadoli" in u or "meli.la" in u:
        return "ml"
    if source == "shopee" or "shopee" in u or "shp.ee" in u:
        return "shopee"
    if source == "aliexpress" or "aliexpress" in u or "s.click" in u:
        return "ali"
    return "outra"


def _cond_loja(loja: str):
    if loja == "ml":
        return or_(Offer.source == "mercadolivre", Offer.url.ilike("%mercadoli%"), Offer.url.ilike("%meli.la%"))
    if loja == "shopee":
        return or_(Offer.source == "shopee", Offer.url.ilike("%shopee%"), Offer.url.ilike("%shp.ee%"))
    return or_(Offer.source == "aliexpress", Offer.url.ilike("%aliexpress%"), Offer.url.ilike("%s.click%"))


def _melhor_loja(session, canal: str, loja: str):
    q = select(Offer).where(Offer.status == "new", Offer.canal == canal, _cond_loja(loja))
    if loja == "ml" and time.time() < _ml_descanso_ate:
        q = q.where(Offer.affiliate_url.is_not(None))
    return session.scalars(q.order_by(Offer.score.desc(), Offer.created_at.desc()).limit(1)).first()


def proximo_mix(session, canal: str, dry: dict | None = None):
    """Mix do dono (25/10/2026): Mercado Livre >= MIX_ML (50%), AliExpress <= MIX_ALI (15%), resto Shopee; lojas sem afiliado nao saem.
    Janela = ultimos MIX_JANELA posts do canal. Retorna a oferta (ou None = espera). So le o banco."""
    recentes = session.execute(select(Offer.source, Offer.url).where(Offer.status == "posted", Offer.canal == canal)
                               .order_by(Offer.posted_at.desc()).limit(settings.mix_janela)).all()
    n = len(recentes)
    cont = {"ml": 0, "shopee": 0, "ali": 0, "outra": 0}
    for src, url in recentes:
        cont[loja_de(src, url)] += 1
    share = {k: (v / n if n else 0.0) for k, v in cont.items()}
    ml_ok = time.time() >= _ml_descanso_ate
    alvos = {"ml": settings.mix_ml, "shopee": max(0.0, 1 - settings.mix_ml - settings.mix_ali), "ali": settings.mix_ali}
    ordem = sorted(alvos, key=lambda k: alvos[k] - share[k], reverse=True)
    if share["ali"] >= settings.mix_ali:
        ordem.remove("ali")
    if ml_ok and share["ml"] < settings.mix_ml:
        ordem = ["ml"] + [k for k in ordem if k != "ml"]
    piso = settings.mix_piso_ml_lar if canal == "lar" else settings.mix_piso_ml
    if dry is not None:
        dry.update(n=n, cont=cont, ordem=ordem)
    for loja in ordem:
        cand = _melhor_loja(session, canal, loja)
        if cand is None:
            continue
        if loja != "ml" and ml_ok and n >= 8 and cont["ml"] / (n + 1) < piso:
            continue  # sem oferta ML e a fatia do ML muito baixa: espera em vez de encher o grupo de Shopee/AliExpress
        return cand
    return None


def publish_next(canal: str = "tech") -> bool:
    """Publica UMA oferta do canal (tech = grupo TechHammer; lar = comunidade Meu lar, minha oferta): a de maior score
    ainda não publicada (produto sem repetir). Retorna True se publicou (o agendador usa isso para o próximo intervalo)."""
    lar = canal == "lar"
    if lar:
        if not settings.lar_enabled or not settings.lar_whatsapp_group_id:
            return False
        if not settings.lar_hour_start <= _now_sp().hour < settings.lar_hour_end:
            return False
    elif not any_channel() and not settings.simulate_posts:
        return False  # sem canal configurado: não gasta geração de link nem "queima" produtos
    elif not in_active_hours():
        return False
    limite = settings.lar_daily_limit if lar else settings.daily_post_limit
    if posts_today(canal) >= limite:
        log.info("daily_limit_reached", limit=limite, canal=canal)
        return False
    with SessionLocal() as session:
        session.execute(
            update(Offer).where(Offer.status == "new", Offer.created_at < now() - timedelta(hours=settings.queue_max_hours))
            .values(status="expired")
        )
        # rodízio de fontes: se o AliExpress saiu num dos últimos (ali_every - 1) posts, a vez é das outras fontes
        # (Pelando, Promobit...). Sem oferta das outras na fila, volta a valer só a nota.
        recentes = session.scalars(
            select(Offer.source).where(Offer.status == "posted", Offer.canal == canal).order_by(Offer.posted_at.desc())
            .limit(max(0, settings.ali_every - 1, settings.shopee_every - 1, settings.pelando_every - 1))
        ).all()
        evitar = ["aliexpress"] if "aliexpress" in recentes[:max(0, settings.ali_every - 1)] else []
        if "shopee" in recentes[:max(0, settings.shopee_every - 1)]:
            evitar.append("shopee")
        if "pelando" in recentes[:max(0, settings.pelando_every - 1)]:
            evitar.append("pelando")

        def melhor(fora: list[str]):
            q = select(Offer).where(Offer.status == "new", Offer.canal == canal)
            if time.time() < _ml_descanso_ate:
                q = q.where(~(or_(Offer.source == "mercadolivre", Offer.url.ilike("%mercadolivre.com.br%"),
                               Offer.url.ilike("%mercadolibre.com%")) & Offer.affiliate_url.is_(None)))
            if fora:
                q = q.where(Offer.source.notin_(fora))
            return session.scalars(q.order_by(Offer.score.desc(), Offer.created_at.desc()).limit(1)).first()

        for _ in range(MAX_PUBLISH_ATTEMPTS):
            o = proximo_mix(session, canal) if settings.mix_enabled else ((melhor(evitar) if evitar else None) or melhor([]))
            if o is None:
                session.commit()
                return False
            # o mesmo produto pode ter sido publicado por outra fonte desde a coleta
            since = now() - timedelta(days=settings.repeat_days)
            same_name = func.lower(func.substr(Offer.title, 1, 35)) == o.title[:35].lower()
            if session.scalar(select(Offer.id).where(
                    or_(Offer.product_key == o.product_key, same_name),
                    Offer.status == "posted", Offer.posted_at >= since)) and not queda_expressiva(session, o.product_key, o.title, o.price):
                o.status, o.reason = "rejected", "produto já publicado"
                session.commit()
                continue
            # o mesmo produto em OUTRO anúncio (outro vendedor/loja): começo do título quase igual e preço próximo
            parecido = next((t for t, p in session.execute(select(Offer.title, Offer.price).where(
                Offer.status == "posted", Offer.posted_at >= since)) if parecidos(o.title, o.price, t, p)), None)
            if parecido:
                o.status, o.reason = "rejected", f"produto parecido já publicado: {parecido[:60]}"
                session.commit()
                continue
            # busca do AliExpress: só marca conhecida e título legível (dono, 13/10: "muita marca/qualidade duvidosa")
            if o.source == "aliexpress" and settings.ali_known_brands_only:
                motivo = "marca desconhecida" if marca(o.title) is None else "título mal traduzido" if mal_traduzido(o.title) else None
                if motivo:
                    o.status, o.reason = "rejected", f"AliExpress: {motivo}"
                    session.commit()
                    continue
                # variedade: a mesma marca não sai em dois posts seguidos do AliExpress (a oferta desce na fila e volta depois)
                ultimas = session.scalars(select(Offer.title).where(Offer.status == "posted", Offer.source == "aliexpress")
                                          .order_by(Offer.posted_at.desc()).limit(3)).all()
                if marca(o.title) in {marca(t) for t in ultimas} and (o.reason or "") != "marca recente":
                    o.score, o.reason = (o.score or 0) - 15, "marca recente"
                    session.commit()
                    continue
            # Shopee: a mesma marca não sai em dois posts seguidos da Shopee (a busca devolve 20 fones QCY de uma vez)
            if o.source == "shopee":
                ultimas = session.scalars(select(Offer.title).where(Offer.status == "posted", Offer.source == "shopee")
                                          .order_by(Offer.posted_at.desc()).limit(3)).all()
                if marca(o.title) and marca(o.title) in {marca(t) for t in ultimas} and (o.reason or "") != "marca recente":
                    o.score, o.reason = (o.score or 0) - 15, "marca recente"
                    session.commit()
                    continue
            # grupo de casa (dono 14/10: "não só móveis e eletrodomésticos"): depois de 2 itens caros seguidos, a vez é de um item do dia a dia
            if lar and (o.price or 0) >= 300 and (o.reason or "") != "casa: variar":
                ultimos = session.scalars(select(Offer.price).where(Offer.status == "posted", Offer.canal == "lar")
                                          .order_by(Offer.posted_at.desc()).limit(2)).all()
                if len(ultimos) == 2 and all((p or 0) >= 300 for p in ultimos):
                    o.score, o.reason = (o.score or 0) - 25, "casa: variar"
                    session.commit()
                    continue
            # histórico de preço: "desconto" que é o preço de sempre perde a vez (e sai sem o riscado); queda real ganha destaque
            situacao, dias = pricehist.analisar(session, o.product_key, o.price)
            if situacao == "estavel" and o.old_price and (o.reason or "") != "preço de sempre":
                o.score, o.reason = (o.score or 0) - 20, "preço de sempre"
                session.commit()
                continue
            o.preco_situacao, o.preco_dias = situacao, dias
            # preço de agregador (Pelando/Promobit/Gatry) pode estar velho ou depender de cupom/app: na Amazon dá para conferir
            if o.source in ("pelando", "promobit", "gatry", "canais") and "amazon.com.br" in o.url and not o.coupon:
                agora = preco_amazon(o.url)
                if agora and agora > o.price * 1.05:
                    o.status, o.reason = "rejected", f"preço subiu na loja (agora R$ {agora:.2f})"
                    log.info("preco_mudou", offer_id=o.id, antes=o.price, agora=agora)
                    session.commit()
                    continue
                if agora and agora < o.price:
                    o.price = agora
            # AliExpress: busca tem muito ruído -> IA confere se é produto de tecnologia desejável
            if is_aliexpress(o.url):
                suspeita = verificar_ali(o.title, o.price, o.old_price)
                if suspeita:
                    o.status, o.reason = "rejected", f"AliExpress: {suspeita}"
                    log.info("ali_suspeito", offer_id=o.id, motivo=suspeita)
                    session.commit()
                    continue
                pct = round((1 - o.price / o.old_price) * 100) if o.price and o.old_price else 0
                ok, why = judge_ali(o.title, o.price, o.old_price, pct)
                if not ok:
                    if why == "IA indisponível":  # IA fora do ar: adia (a oferta continua na fila) em vez de rejeitar de vez
                        log.warning("ia_indisponivel_adia", offer_id=o.id)
                        session.commit()
                        return False
                    o.status, o.reason = "rejected", f"IA curadoria AliExpress: {why}"
                    log.info("ai_rejected", offer_id=o.id, reason=why, source="aliexpress")
                    session.commit()
                    continue
            # fora de tecnologia: a IA local decide se é "oferta absurda" de verdade
            if not is_tech(o.title) and not lar:  # canal de casa: as regras de casa já filtraram na coleta
                pct = round((1 - o.price / o.old_price) * 100) if o.price and o.old_price else 0
                ok, why = judge_offer(o.title, o.price, o.old_price, pct)
                if not ok:
                    if why == "IA indisponível":  # IA fora do ar: adia (a oferta continua na fila) em vez de rejeitar de vez
                        log.warning("ia_indisponivel_adia", offer_id=o.id)
                        session.commit()
                        return False
                    o.status, o.reason = "rejected", f"IA curadoria: {why}"
                    log.info("ai_rejected", offer_id=o.id, reason=why)
                    session.commit()
                    continue
            # foto obrigatória e validada: 1º a principal (card da coleta)
            photo = product_jpeg(o.image_url)
            jogo = parece_jogo(o.title, o.url)
            ok, why = validate_photo(photo, o.title, is_aliexpress(o.url), jogo) if photo else (False, "sem foto")
            try:
                try:
                    gallery = _ensure_link(o)
                except OfferGone as e:
                    o.status, o.reason = "rejected", str(e)
                    session.commit()
                    continue  # tenta a próxima da fila no mesmo minuto
                # 2º: se a principal foi reprovada, tenta as outras fotos da galeria do próprio anúncio
                # (lojas comuns: foto limpa da página do produto — og:image/JSON-LD; ML e AliExpress têm o seu caminho)
                # miniatura do agregador (300 px) aprovada: troca pela foto grande da página da loja, se houver uma aprovada
                if ok and foto_pequena(o.image_url) and not is_mercadolivre(o.url) and not is_aliexpress(o.url):
                    for alt in (gallery or store_photos(o.url)):
                        cand = product_jpeg(alt)
                        if cand and validate_photo(cand, o.title, False, jogo)[0]:
                            photo, o.image_url = cand, alt
                            log.info("photo_upgraded", offer_id=o.id, image=alt)
                            break
                if not ok:
                    if not gallery and not is_mercadolivre(o.url) and not is_aliexpress(o.url):
                        gallery = store_photos(o.url)
                    elif not gallery and is_aliexpress(o.url) and aliapi.configured():
                        try:  # AliExpress: a 1ª foto costuma ser propaganda; as outras do anúncio muitas vezes são limpas
                            gallery = aliapi.images(o.url)
                        except Exception as e:
                            log.warning("ali_images_failed", offer_id=o.id, error=str(e)[:120])
                    for alt in gallery:
                        cand = product_jpeg(alt)
                        if cand and validate_photo(cand, o.title, is_aliexpress(o.url), jogo)[0]:
                            photo, ok, o.image_url = cand, True, alt
                            log.info("photo_from_gallery", offer_id=o.id, image=alt)
                            break
                if not ok and why == "validação indisponível":  # IA fora do ar: adia (a oferta continua na fila) em vez de rejeitar de vez
                    log.warning("ia_indisponivel_adia", offer_id=o.id)
                    session.commit()
                    return False
                if not ok:
                    o.status, o.reason = "rejected", f"foto: {why} (galeria sem foto aprovada)"
                    log.info("photo_rejected", offer_id=o.id, reason=why, gallery=len(gallery))
                    session.commit()
                    continue
                o.post_title = short_title(o.title)
                if settings.offer_coupon_hint and not o.coupon:
                    try:
                        o.cupom_dica = sugerir_cupom(session, o.url, o.price, canal)
                    except Exception as e:
                        log.warning("cupom_dica_falhou", offer_id=o.id, error=str(e)[:120])
                publish(o, photo, canal)
                o.status, o.posted_at = "posted", now()
                if "meli.la" in (o.affiliate_url or ""):
                    globals()["_ml_ultimo_ok"] = time.time()
                log.info("posted", offer_id=o.id, source=o.source, link=o.affiliate_url or o.url, canal=canal)
                _health(session, "publicacao").consecutive_failures = 0
                session.commit()
                return True
            except Exception as e:
                global _ml_descanso_ate
                if is_mercadolivre(o.url) and not o.affiliate_url and "linkgen" in str(e):
                    if (o.reason or "").startswith("ML em descanso") and time.time() - _ml_ultimo_ok < 6 * 3600:  # 2ª falha na mesma oferta com o ML funcionando: problema da página (sem captcha geral)
                        o.status, o.reason = "rejected", "ML: página sem botão Compartilhar (linkgen)"
                        log.warning("ml_oferta_sem_link", offer_id=o.id, error=str(e)[:100])
                        session.commit()
                        return False
                    _ml_descanso_ate = time.time() + ML_DESCANSO_SEG
                    o.status, o.reason = "new", "ML em descanso (linkgen falhou)"
                    log.warning("ml_descanso", offer_id=o.id, minutos=ML_DESCANSO_SEG // 60, error=str(e)[:120])
                    session.commit()
                    _note_publish_failure(session, str(e))
                    return False
                o.status, o.reason = "failed", str(e)[:500]
                log.error("publish_failed", offer_id=o.id, error=str(e))
                session.commit()
                _note_publish_failure(session, str(e))
                return False  # não insiste no mesmo minuto


def _note_publish_failure(session, error: str) -> None:
    h = _health(session, "publicacao")
    h.consecutive_failures += 1
    h.last_error = error[:500]
    if h.consecutive_failures == ALERT_AFTER_FAILURES:
        alert(f"Publicação falhou {ALERT_AFTER_FAILURES}x seguidas (login do ML expirou?): {error[:200]}")
    session.commit()


def run_cycle() -> None:
    collect_all()
    publish_next()
