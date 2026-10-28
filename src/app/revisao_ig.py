"""Revisão semanal do Instagram (28/10/2026): lê os posts do @ pela Graph API (SÓ LEITURA) e diz o que funcionou e o que repetir ou parar.

- Sem IA e sem notificação: escreve data/revisao_instagram/ultima.md (+ uma cópia por data) e guarda os seguidores em seguidores.json.
- Usa só curtidas e comentários (instagram_basic): alcance/visualizações exigem a permissão instagram_manage_insights, que o token não tem.
- `ctl revisao-ig [dias]` mostra o relatório; roda sozinho todo domingo (catchup.schedule).
"""
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import DATA_DIR, settings
from app.log import log

G = "https://graph.facebook.com/v21.0"
TZ = ZoneInfo("America/Sao_Paulo")
PASTA = DATA_DIR / "revisao_instagram"
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
TEMAS = [  # ordem importa: o primeiro que bater vale
    ("limpeza/manutenção", ("limpeza", "poeira", "esquentando", "superaquec", "pasta térmica", "sufocad", "fluxo de ar", "manutenção")),
    ("montagem de PC", ("montei", "montagem", "do zero")),
    ("jogos", ("jogo", "game pass", "steam", "epic", "ps plus", "grátis")),
    ("ofertas", ("oferta", "desconto", "cupom", "r$", "promoção")),
    ("dica", ("dica", "antes de trocar", "lento")),
]
MIN_AMOSTRA = 3  # abaixo disso o grupo é só curiosidade, não vira recomendação


def _formato(m: dict) -> str:
    if m.get("media_product_type") == "REELS":
        return "Reel"
    return "Carrossel" if m.get("media_type") == "CAROUSEL_ALBUM" else "Foto"


def _tema(legenda: str) -> str:
    t = legenda.lower()
    return next((nome for nome, chaves in TEMAS if any(c in t for c in chaves)), "outros")


def _gancho(legenda: str) -> str:
    return (legenda.strip().splitlines() or [""])[0].strip()


def _tipo_gancho(g: str) -> str:
    if "?" in g:
        return "pergunta"
    if any(c.isdigit() for c in g):
        return "com número"
    if g.lstrip("📰🔥⚡🎮").upper() == g.lstrip("📰🔥⚡🎮") and len(g) > 8:
        return "CAIXA ALTA"
    return "afirmação"


def coletar(dias: int = 60) -> tuple[dict, list[dict]]:
    pt, iid = settings.meta_page_token, settings.meta_ig_id
    if not (pt and iid):
        raise RuntimeError("sem META_PAGE_TOKEN/META_IG_ID")
    perfil = httpx.get(f"{G}/{iid}", timeout=30, params={"fields": "username,followers_count,media_count", "access_token": pt}).json()
    if "username" not in perfil:
        raise RuntimeError(str(perfil.get("error", perfil))[:200])
    corte = datetime.now(TZ) - timedelta(days=dias)
    posts, url, params = [], f"{G}/{iid}/media", {"fields": "id,caption,media_type,media_product_type,timestamp,like_count,comments_count,permalink", "limit": 50, "access_token": pt}
    while url and len(posts) < 300:
        r = httpx.get(url, timeout=30, params=params).json()
        for m in r.get("data", []):
            quando = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")).astimezone(TZ)
            if quando < corte:
                url = None
                break
            posts.append({**m, "quando": quando, "formato": _formato(m), "tema": _tema(m.get("caption") or ""), "gancho": _gancho(m.get("caption") or ""),
                          "likes": int(m.get("like_count") or 0), "coments": int(m.get("comments_count") or 0)})
        else:
            url, params = (r.get("paging", {}).get("next"), None)
    for p in posts:
        p["nota"] = p["likes"] + 3 * p["coments"]  # comentário vale mais que curtida
    return perfil, posts


def _media(xs: list[float]) -> float:
    return round(statistics.mean(xs), 1) if xs else 0.0


def _grupos(posts: list[dict], chave) -> list[tuple[str, int, float]]:
    g = defaultdict(list)
    for p in posts:
        g[chave(p)].append(p["nota"])
    return sorted(((k, len(v), _media(v)) for k, v in g.items()), key=lambda x: -x[2])


def _seguidores(perfil: dict) -> str:
    arq = PASTA / "seguidores.json"
    try:
        hist = json.loads(arq.read_text())
    except (OSError, ValueError):
        hist = {}
    hoje = datetime.now(TZ).strftime("%Y-%m-%d")
    antes = [d for d in sorted(hist) if d < hoje]
    hist[hoje] = perfil.get("followers_count")
    PASTA.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(hist, indent=1))
    atual = perfil.get("followers_count")
    if not antes:
        return f"{atual} seguidores (primeira medição; a próxima revisão mostra a variação)"
    d0 = antes[-1]
    return f"{atual} seguidores ({atual - hist[d0]:+d} desde {d0})"


def relatorio(dias: int = 60) -> str:
    dias = int(dias)
    perfil, posts = coletar(dias)
    if not posts:
        return f"Nenhum post do @{perfil['username']} nos últimos {dias} dias."
    mediana = statistics.median(p["nota"] for p in posts)
    L = [f"# Revisão do Instagram @{perfil['username']} — {datetime.now(TZ):%d/%m/%Y}", "",
         f"- {_seguidores(perfil)}", f"- {len(posts)} posts nos últimos {dias} dias; nota mediana {mediana:g} (nota = curtidas + 3 × comentários)",
         "- Só curtidas e comentários (alcance e visualizações exigem a permissão `instagram_manage_insights`). Amostra pequena: use como pista, não como lei.", ""]
    por_formato = {k: statistics.median([p["nota"] for p in posts if p["formato"] == k]) for k in {p["formato"] for p in posts}}

    def forca(p: dict) -> float:  # quantas vezes acima/abaixo do normal DO MESMO FORMATO (Reel não compete com foto)
        base = por_formato[p["formato"]] or 1
        return p["nota"] / base
    ordem = sorted(posts, key=forca, reverse=True)
    L += ["## Os 5 que mais se destacaram (vs. o normal do próprio formato)", ""]
    L += [f"- {p['quando']:%d/%m} {p['formato']} | {p['likes']} curtidas, {p['coments']} coment. | {forca(p):.1f}× | “{p['gancho'][:70]}” | {p['permalink']}" for p in ordem[:5]]
    L += ["", "## Os 5 que menos funcionaram", ""]
    L += [f"- {p['quando']:%d/%m} {p['formato']} | {p['likes']} curtidas, {p['coments']} coment. | {forca(p):.1f}× | “{p['gancho'][:70]}”" for p in ordem[-5:][::-1]]
    blocos = [("Por formato", _grupos(posts, lambda p: p["formato"])), ("Por tema", _grupos(posts, lambda p: p["tema"])),
              ("Por tipo de gancho (1ª linha)", _grupos(posts, lambda p: _tipo_gancho(p["gancho"]))),
              ("Por dia da semana", _grupos(posts, lambda p: DIAS[p["quando"].weekday()])),
              ("Por faixa de horário", _grupos(posts, lambda p: f"{p['quando'].hour // 6 * 6:02d}h–{p['quando'].hour // 6 * 6 + 5:02d}h"))]
    for titulo, g in blocos:
        L += ["", f"## {titulo} (nota média)", ""]
        L += [f"- {k}: {m:g}  ({n} posts{'' if n >= MIN_AMOSTRA else ', amostra pequena'})" for k, n, m in g]
    L += ["", "## O que fazer na próxima semana", ""]
    fortes = [(k, n, m) for k, n, m in blocos[1][1] if n >= MIN_AMOSTRA]
    media_geral = _media([p["nota"] for p in posts])
    if fortes:
        k, n, m = fortes[0]
        L.append(f"- **Repetir:** tema “{k}” é o melhor com amostra boa (média {m:g} em {n} posts, geral {media_geral:g}).")
        k, n, m = fortes[-1]
        if len(fortes) > 1 and m < media_geral * 0.6:
            L.append(f"- **Mudar a abordagem ou reduzir:** tema “{k}” (média {m:g} em {n} posts, bem abaixo da geral {media_geral:g}).")
    f_fortes = [(k, n, m) for k, n, m in blocos[0][1] if n >= MIN_AMOSTRA]
    if len(f_fortes) > 1:
        L.append(f"- **Formato que mais rende:** {f_fortes[0][0]} (média {f_fortes[0][2]:g}) contra {f_fortes[-1][0]} ({f_fortes[-1][2]:g}).")
    g_fortes = [(k, n, m) for k, n, m in blocos[2][1] if n >= MIN_AMOSTRA]
    if g_fortes:
        L.append(f"- **Gancho que mais funcionou:** {g_fortes[0][0]} (média {g_fortes[0][2]:g}); teste o mesmo estilo nos próximos Reels.")
    sem_coment = sum(1 for p in posts if p["coments"] == 0)
    L.append(f"- {sem_coment} de {len(posts)} posts não tiveram nenhum comentário: feche cada Reel com UMA pergunta simples ou um pedido de resposta (ex.: “qual placa você quer ver limpa?”).")
    return "\n".join(L) + "\n"


def gerar(dias: int = 60) -> str:
    """Escreve o relatório em data/revisao_instagram/ (ultima.md + cópia datada) e devolve o texto. Chamado pelo ctl e pela agenda de domingo."""
    texto = relatorio(dias)
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / "ultima.md").write_text(texto, encoding="utf-8")
    (PASTA / f"{datetime.now(TZ):%Y-%m-%d}.md").write_text(texto, encoding="utf-8")
    log.info("revisao_instagram_gerada", linhas=texto.count("\n"))
    return texto


def agendada() -> None:
    """Gancho da agenda (domingo): gera e guarda; falha só vai para o log, nunca derruba outro post."""
    try:
        gerar()
    except Exception as e:  # noqa: BLE001
        log.warning("revisao_instagram_falhou", error=str(e)[:200])
