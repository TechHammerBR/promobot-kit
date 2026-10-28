"""Fila de Reels PRONTOS (15/10/2026, pedido do dono): o PC do dono FABRICA o vídeo (voz, trailers, IA local) e o Wyse só ENTREGA na hora marcada.

Contrato (pasta /srv/cache/reels-prontos):
  fila/<id>/video.mp4 + meta.json   <- o PC copia para fila/<id>.tmp e renomeia (atômico); o Wyse ignora *.tmp
  publicados/<id>/ | falhou/<id>/ | expirados/<id>/   <- destino final (nunca publica duas vezes)
  tipos-aprovados.json              <- tipos que o dono já aprovou ("ofertas", ...); outro tipo só sai com "aprovado": true no meta.json

meta.json: {"id", "tipo": "gratis|promo|ofertas|dono|...", "legenda", "legenda_threads"?, "quando": "2026-10-16T13:00:00-03:00"?,
            "valido_ate"?: ISO (padrão: quando + 36 h), "na_grade": true, "aprovado"?: bool, "simular"?: bool (teste: não publica, só marca),
            "jogos"?: [{name, store?, price?, url?}] (vai para o histórico anti-repetição)}

Dois jeitos de sair: (1) o timer `promobot-fila-reels` publica o que tem "quando" vencido; (2) a tarefa agendada do próprio Wyse (ex.: reel_ofertas 20h)
chama publicar_tipo(): se há item pronto do tipo, publica o do PC; se não, o Wyse monta o Reel simples (plano B). Nunca publica o mesmo item duas vezes (trava + pasta final)."""
import fcntl
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import DATA_DIR, settings
from app.log import log

TZ = ZoneInfo("America/Sao_Paulo")
PASTA = Path(os.getenv("FILA_REELS_DIR", "/srv/cache/reels-prontos"))
FILA, PUBLICADOS, FALHOU, EXPIRADOS = PASTA / "fila", PASTA / "publicados", PASTA / "falhou", PASTA / "expirados"
APROVADOS = PASTA / "tipos-aprovados.json"
MAX_TENTATIVAS = 3
VALIDADE_PADRAO_H = 36
YT_ANTECEDENCIA_H = 48  # o Short sobe agendado até 48 h antes do horário (cota da API: ~6 envios/dia; 1 por rodada)
YT_MAX_TENTATIVAS = 3


def _garantir() -> None:
    for p in (FILA, PUBLICADOS, FALHOU, EXPIRADOS):
        p.mkdir(parents=True, exist_ok=True)


def _agora() -> datetime:
    return datetime.now(TZ)


def _iso(txt: str | None) -> datetime | None:
    if not txt:
        return None
    try:
        d = datetime.fromisoformat(str(txt))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=TZ)


def _meta(pasta: Path) -> dict | None:
    try:
        m = json.loads((pasta / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (pasta / "video.mp4").exists():
        return None
    m["_dir"] = pasta
    m.setdefault("id", pasta.name)
    return m


def _validade(m: dict) -> datetime:
    v = _iso(m.get("valido_ate"))
    if v:
        return v
    base = _iso(m.get("quando")) or datetime.fromtimestamp((m["_dir"] / "meta.json").stat().st_mtime, TZ)
    return base + timedelta(hours=VALIDADE_PADRAO_H)


def _tipos_aprovados() -> set[str]:
    try:
        return set(json.loads(APROVADOS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def aprovado(m: dict) -> bool:
    return bool(m.get("aprovado")) or m.get("tipo") in _tipos_aprovados()


def listar() -> list[dict]:
    """Itens na fila (sem *.tmp), pelo horário."""
    _garantir()
    itens = [m for p in FILA.iterdir() if p.is_dir() and not p.name.endswith((".tmp", ".publicando")) for m in [_meta(p)] if m]
    return sorted(itens, key=lambda m: _iso(m.get("quando")) or _agora())


class _Trava:
    def __init__(self) -> None:
        _garantir()
        self.f = open(PASTA / ".trava", "w")

    def __enter__(self) -> bool:
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def __exit__(self, *a) -> None:
        try:
            fcntl.flock(self.f, fcntl.LOCK_UN)
        finally:
            self.f.close()


def _mover(m: dict, destino: Path, **extra) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    final = destino / m["id"]
    if final.exists():
        shutil.rmtree(final)
    estado = {k: v for k, v in m.items() if not k.startswith("_")}
    estado.update(extra, movido_em=_agora().isoformat(timespec="seconds"))
    (m["_dir"] / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.move(str(m["_dir"]), str(final))


def _alerta(msg: str) -> None:
    try:
        from app.publisher import alert
        alert(msg)
    except Exception:  # noqa: BLE001
        log.warning("fila_reels_alerta", msg=msg)


def com_grupos(legenda: str, threads: str) -> tuple[str, str]:
    """Garante os grupos de promoção na descrição (regra do dono): bloco com os 3 grupos antes das hashtags e, no Threads, as 3 linhas dos grupos."""
    from app.templates import chamada_grupos, grupos_threads
    if "chat.whatsapp.com" not in legenda:
        linhas = legenda.rstrip().split("\n")
        bloco = chamada_grupos(True) + "\n(grátis • link também na bio)"
        if linhas and linhas[-1].lstrip().startswith("#"):
            legenda = "\n".join(linhas[:-1]).rstrip() + "\n\n" + bloco + "\n\n" + linhas[-1]
        else:
            legenda = legenda.rstrip() + "\n\n" + bloco
    if "chat.whatsapp.com" not in threads:
        g = grupos_threads()
        threads = threads[: max(0, 495 - len(g) - 2)].rstrip() + "\n" + g
    return legenda, threads


def _publicar(m: dict) -> bool:
    """Publica UM item (já sob a trava). True = saiu (ou simulado)."""
    if m.get("simular"):
        log.info("fila_reels_simulado", id=m["id"], tipo=m.get("tipo"))
        _mover(m, PUBLICADOS, redes=["simulado"])
        return True
    video = (m["_dir"] / "video.mp4").read_bytes()
    legenda = m.get("legenda", "")
    if m.get("formato") == "story":  # Story em vídeo (Instagram + Página)
        from app import story_video
        done = story_video.publicar(video)
    else:
        from app.reels import _publish
        legenda, texto_threads = com_grupos(legenda, m.get("legenda_threads") or legenda[:480])
        capa = (m["_dir"] / "capa.jpg").read_bytes() if (m["_dir"] / "capa.jpg").exists() else None
        done = _publish(video, legenda, texto_threads, na_grade=bool(m.get("na_grade", True)), marcar=m.get("marcar") or None, capa=capa)
        if done and m.get("youtube_id"):  # o Short já está AGENDADO na plataforma (agendar_youtube): não subir de novo
            done = list(done) + ["youtube(agendado)"]
        elif done:  # YouTube Shorts (pedido do dono 22/10): só depois de sair em alguma rede, falha aqui não afeta as outras
            try:
                from app import youtube
                if youtube.enabled() and youtube.publicar_short(video, legenda, capa):
                    done = list(done) + ["youtube"]
            except Exception as e:  # noqa: BLE001
                log.warning("youtube_short_falhou", error=str(e)[:200])
    if done:
        log.info("fila_reels_publicado", id=m["id"], tipo=m.get("tipo"), redes=done, mb=round(len(video) / 1e6, 1))
        if m.get("jogos") and m.get("tipo") in ("gratis", "promo"):
            try:
                from app.games import registrar_destaques
                registrar_destaques(m["jogos"], "gratis" if m["tipo"] == "gratis" else "reel")
            except Exception as e:  # noqa: BLE001
                log.warning("fila_reels_historico", error=str(e)[:150])
        _mover(m, PUBLICADOS, redes=done)
        return True
    tent = int(m.get("tentativas", 0)) + 1
    m["tentativas"] = tent
    try:
        meta = json.loads((m["_dir"] / "meta.json").read_text(encoding="utf-8"))
        meta["tentativas"] = tent
        (m["_dir"] / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    except (OSError, ValueError):
        pass
    if tent >= MAX_TENTATIVAS:
        _mover(m, FALHOU, motivo="3 tentativas sem rede publicada")
        _alerta(f"Reel pronto {m['id']} ({m.get('tipo')}) falhou {tent}x e foi para falhou/")
    return False


def _bloqueado() -> bool:
    return (DATA_DIR / "MAINTENANCE").exists()


def _pode_publicar(m: dict) -> bool:
    if not aprovado(m):
        return False
    if m.get("simular"):
        return True
    from app.social import enabled
    return enabled()


def _expirar(agora: datetime) -> None:
    for m in listar():
        if _validade(m) < agora:
            log.info("fila_reels_expirado", id=m["id"], tipo=m.get("tipo"))
            _mover(m, EXPIRADOS, motivo="passou da validade")


def agendar_youtube(agora: datetime | None = None) -> int:
    """Pedido do dono (27/10): o Short do YouTube fica AGENDADO na própria plataforma. Até YT_ANTECEDENCIA_H antes do horário do Reel o vídeo sobe como privado com
    publishAt; na hora, _publicar vê meta["youtube_id"] e não sobe de novo. No máximo 1 envio por rodada (cota). A API não edita nem apaga: só agenda item já aprovado."""
    if _bloqueado():
        return 0
    try:
        from app import youtube
        if not youtube.enabled():
            return 0
    except Exception:  # noqa: BLE001
        return 0
    agora = agora or _agora()
    with _Trava() as ok:
        if not ok:
            return 0
        for m in listar():
            if m.get("youtube_id") or m.get("simular") or m.get("formato") == "story" or not aprovado(m):
                continue
            q = _iso(m.get("quando"))
            if q is None or q < agora + timedelta(minutes=20) or q > agora + timedelta(hours=YT_ANTECEDENCIA_H):
                continue
            if int(m.get("youtube_tentativas", 0)) >= YT_MAX_TENTATIVAS:
                continue
            arq = m["_dir"] / "meta.json"
            try:
                meta = json.loads(arq.read_text(encoding="utf-8"))
                meta["youtube_tentativas"] = int(meta.get("youtube_tentativas", 0)) + 1
                arq.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                legenda, _ = com_grupos(m.get("legenda", ""), m.get("legenda_threads") or m.get("legenda", "")[:480])
                capa = (m["_dir"] / "capa.jpg").read_bytes() if (m["_dir"] / "capa.jpg").exists() else None
                vid = youtube.publicar_short((m["_dir"] / "video.mp4").read_bytes(), legenda, capa, publicar_em=q)
                if vid:
                    meta["youtube_id"] = vid
                    arq.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                    log.info("fila_reels_youtube_agendado", id=m["id"], youtube_id=vid, quando=q.isoformat(timespec="minutes"))
                    return 1
            except Exception as e:  # noqa: BLE001
                log.warning("youtube_agendar_falhou", id=m["id"], error=str(e)[:200])
                return 0
    return 0


def processar(agora: datetime | None = None) -> int:
    """Chamado pelo timer: publica os itens COM horário vencido. Devolve quantos saíram."""
    if _bloqueado():
        return 0
    agora = agora or _agora()
    feitos = 0
    with _Trava() as ok:
        if not ok:
            return 0
        _expirar(agora)
        for m in listar():
            q = _iso(m.get("quando"))
            if q is None or q > agora or not _pode_publicar(m):
                continue
            if _publicar(m):
                feitos += 1
    try:  # depois de publicar o que venceu: agenda o próximo Short no YouTube (se faltar até 48 h)
        agendar_youtube(agora)
    except Exception as e:  # noqa: BLE001
        log.warning("youtube_agendar_erro", error=str(e)[:150])
    return feitos


def publicar_tipo(tipo: str, folga_min: int = 15) -> bool:
    """Gancho das tarefas agendadas do Wyse: True = o Reel pronto do PC saiu (ou está saindo) -> NÃO montar o do Wyse; False = montar o plano B."""
    if _bloqueado():
        return False
    agora = _agora()
    with _Trava() as ok:
        if not ok:
            return True  # o timer está publicando agora: não duplicar
        _expirar(agora)
        for m in listar():
            if m.get("tipo") != tipo or not _pode_publicar(m):
                continue
            q = _iso(m.get("quando"))
            if q is not None and q > agora + timedelta(minutes=folga_min):
                continue
            if _publicar(m):
                return True
    return False


def resumo() -> dict:
    _garantir()
    return {"fila": [{"id": m["id"], "tipo": m.get("tipo"), "quando": m.get("quando"), "aprovado": aprovado(m), "simular": bool(m.get("simular")),
                      "valido_ate": _validade(m).isoformat(timespec="minutes")} for m in listar()],
            "publicados": len(list(PUBLICADOS.iterdir())), "falhou": len(list(FALHOU.iterdir())), "expirados": len(list(EXPIRADOS.iterdir())),
            "tipos_aprovados": sorted(_tipos_aprovados()), "bloqueado": _bloqueado()}
