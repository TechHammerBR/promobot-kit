"""Conteúdo da LOJA TechHammer para o feed (06/10) — o feed é vitrine de manutenção/montagem, não só ofertas.

1) Post de SERVIÇO (antes/depois) a partir de fotos do dono pelo WhatsApp:
   O Claude guarda as fotos em data/wa/inbox -> `ctl servico "<o que foi feito>"` monta o carrossel (capa + fotos + CTA)
   e a legenda (IA local) e salva a PRÉVIA em data/service_post -> o Claude mostra ao dono
   -> `ctl aprovar` publica no Instagram + Página | `ctl cancelar` descarta.
2) Carrosséis EDUCATIVOS prontos (texto revisado, sem IA inventando): rodízio em EDU_SERIES, toda EDU_DAY/EDU_TIME.
"""
import base64
import io
import json
import shutil
import textwrap
import time

import httpx
from PIL import Image, ImageDraw, ImageOps

from app import gpu
from app.config import DATA_DIR, settings
from app.log import log
from app.social import _api, _upload_hidden
from app.social_art import BG, MUTED, TEXT, _brand, _font, _hex

W, H = 1080, 1350
INBOX = DATA_DIR / "wa" / "inbox"
PENDING = DATA_DIR / "service_post"
EDU_STATE = DATA_DIR / "edu_index"
CTA_LINES = ["Orçamento sem compromisso", "Atendemos na loja e EM DOMICÍLIO", "Chama no direct ou no WhatsApp"]
TAGS = "#manutençãodecomputadores #pcgamer #notebook #assistênciatécnica #techhammer"


def _jpeg(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _base() -> tuple[Image.Image, ImageDraw.ImageDraw, tuple]:
    accent = _hex(settings.accent_color)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand(d, W, 90, accent)
    return im, d, accent


def _text_slide(title: str, body: str | None = None, kicker: str | None = None, footer: str | None = None,
                big: bool = False) -> bytes:
    im, d, accent = _base()
    y = 430 if big else 520
    if kicker:
        d.text((W / 2, y - 110), kicker.upper(), font=_font(34), fill=accent, anchor="mm")
    lines = textwrap.wrap(title, 16 if big else 20)
    size = 96 if big else 76
    for ln in lines:
        d.text((W / 2, y), ln, font=_font(size), fill=TEXT, anchor="mm")
        y += size + 22
    if body:
        y += 40
        for ln in textwrap.wrap(body, 34):
            d.text((W / 2, y), ln, font=_font(40, "regular"), fill=MUTED, anchor="mm")
            y += 58
    if footer:
        d.text((W / 2, H - 90), footer, font=_font(28, "regular"), fill=MUTED, anchor="mm")
    return _jpeg(im)


def _cta_slide(linha1: str = "SEU PC TAMBÉM", linha2: str = "PRECISA?", linhas: list[str] | None = None, botao: str = "CHAMA NO DIRECT") -> bytes:
    im, d, accent = _base()
    d.text((W / 2, 420), linha1, font=_font(84), fill=TEXT, anchor="mm")
    d.text((W / 2, 520), linha2, font=_font(84), fill=accent, anchor="mm")
    y = 700
    for ln in (linhas or CTA_LINES):
        d.text((W / 2, y), ln, font=_font(42, "regular"), fill=TEXT, anchor="mm")
        y += 80
    d.rounded_rectangle((W / 2 - 260, 1080, W / 2 + 260, 1170), radius=45, outline=accent, width=4)
    d.text((W / 2, 1125), botao, font=_font(36), fill=TEXT, anchor="mm")
    return _jpeg(im)


def _photo_slide(jpeg: bytes, label: str) -> bytes:
    im, d, accent = _base()
    ph = ImageOps.exif_transpose(Image.open(io.BytesIO(jpeg))).convert("RGB")
    ph = ImageOps.fit(ph, (960, 1060))
    mask = Image.new("L", ph.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *ph.size), radius=40, fill=255)
    im.paste(ph, (60, 170), mask)
    if label:
        f = _font(44)
        tw = d.textlength(label, font=f)
        d.rounded_rectangle((90, 200, 90 + tw + 56, 280), radius=40, fill=accent)
        d.text((118, 240), label, font=f, fill=(255, 255, 255), anchor="lm")
    return _jpeg(im)


def _ai_text(desc: str) -> dict:
    prompt = f"""Você é social media de uma loja de manutenção e montagem de computadores (TechHammer).
Serviço feito (descrição do técnico): "{desc}"
Crie em PORTUGUÊS DO BRASIL, tom profissional e próximo, SEM inventar dados que não estão na descrição:
- "titulo": chamada curta para a capa (máx. 6 palavras, sem emoji)
- "legenda": legenda do Instagram com 3 a 5 frases curtas contando o problema e a solução, com 2 ou 3 emojis.
Responda SÓ em JSON: {{"titulo": "...", "legenda": "..."}}"""
    try:
        r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=180, json={
            "model": settings.ai_model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0.5, "num_predict": 400, "num_gpu": settings.bot_ai_num_gpu},
            "messages": [{"role": "user", "content": prompt}]})
        out = json.loads(r.json()["message"]["content"])
        if out.get("titulo") and out.get("legenda"):
            return out
    except Exception as e:
        log.warning("ai_failed", error=str(e)[:200])
    return {"titulo": "Mais um na bancada", "legenda": desc}


def _send_owner(text: str, image: bytes | None = None) -> None:
    """Sem chat com o dono (07/10/2026): a prévia fica em data/service_post (imagens + caption.txt + previa.txt)."""
    if text:
        PENDING.mkdir(parents=True, exist_ok=True)
        with open(PENDING / "previa.txt", "a", encoding="utf-8") as f:
            f.write(text + "\n\n")


def preview_service(desc: str) -> str:
    photos = sorted(INBOX.glob("*.jpg"))[:8] if INBOX.exists() else []
    if not photos:
        return "📸 Não achei fotos em data/wa/inbox. Guarde as fotos (antes → depois) lá e rode de novo."
    t = _ai_text(desc)
    n = len(photos)
    labels = ["ANTES"] + [""] * (n - 2) + ["DEPOIS"] if n >= 2 else [""]
    slides = [_text_slide(t["titulo"], kicker="Na bancada da TechHammer", big=True, footer="arraste →")]
    slides += [_photo_slide(p.read_bytes(), labels[i]) for i, p in enumerate(photos)]
    slides.append(_cta_slide())
    caption = f"{t['legenda']}\n\n🔧 " + " • ".join(CTA_LINES) + f"\n\n{TAGS}"
    shutil.rmtree(PENDING, ignore_errors=True)
    PENDING.mkdir(parents=True)
    for i, s in enumerate(slides):
        (PENDING / f"{i:02d}.jpg").write_bytes(s)
    (PENDING / "caption.txt").write_text(caption)
    _send_owner(f"👀 PRÉVIA do post ({len(slides)} imagens). Legenda:\n\n{caption}", slides[0])
    for s in slides[1:]:
        _send_owner("", s)
    return f"✅ Prévia salva em data/service_post ({len(slides)} imagens). Publicar no Instagram + Facebook: `ctl aprovar`. Descartar: `ctl cancelar`."


def publish_carousel(slides: list[bytes], caption: str, first_comment: str | None = None, fb_caption: str | None = None) -> list[str]:
    ids, urls = zip(*(_upload_hidden(s) for s in slides))
    done = []
    try:
        _api("POST", f"{settings.meta_page_id}/feed", message=fb_caption or caption,
             **{f"attached_media[{n}]": f'{{"media_fbid":"{i}"}}' for n, i in enumerate(ids)})
        done.append("facebook")
    except Exception as e:
        log.error("carousel_failed", net="facebook", error=str(e)[:300])
    try:
        kids = [_api("POST", f"{settings.meta_ig_id}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
        c = _api("POST", f"{settings.meta_ig_id}/media", media_type="CAROUSEL", caption=caption, children=",".join(kids))
        for _ in range(30):
            if _api("GET", c["id"], fields="status_code").get("status_code") == "FINISHED":
                break
            time.sleep(4)
        m = _api("POST", f"{settings.meta_ig_id}/media_publish", creation_id=c["id"])["id"]
        if first_comment:
            _api("POST", f"{m}/comments", message=first_comment)
        done.append("instagram")
    except Exception as e:
        log.error("carousel_failed", net="instagram", error=str(e)[:300])
    from app import threads
    if threads.enabled():
        try:
            threads.post((fb_caption or caption)[:500], list(urls))
            done.append("threads")
        except Exception as e:
            log.error("carousel_failed", net="threads", error=str(e)[:300])
    return done


def approve_service() -> str:
    if not (PENDING / "caption.txt").exists():
        return "Não há post pendente."
    slides = [p.read_bytes() for p in sorted(PENDING.glob("*.jpg"))]
    done = publish_carousel(slides, (PENDING / "caption.txt").read_text())
    if done:
        shutil.rmtree(PENDING, ignore_errors=True)
        shutil.rmtree(INBOX, ignore_errors=True)
        return f"🚀 Post publicado em: {', '.join(done)}."
    return "⚠️ Não consegui publicar agora (veja `ctl alertas`). A prévia continua guardada: rode `ctl aprovar` de novo."


def cancel_service() -> str:
    shutil.rmtree(PENDING, ignore_errors=True)
    shutil.rmtree(INBOX, ignore_errors=True)
    return "🗑️ Post e fotos descartados."


# ---------------------------------------------------------------- carrosséis educativos (conteúdo revisado)
EDU_SERIES = [
    {"titulo": "5 sinais de que seu PC precisa de manutenção", "kicker": "Fica a dica",
     "slides": [("Barulho alto", "Ventoinha gritando é sinal de poeira acumulada e esforço extra."),
                ("Esquenta demais", "Pasta térmica seca e poeira fazem a temperatura disparar."),
                ("Desliga sozinho", "É a proteção contra superaquecimento agindo. Não ignore!"),
                ("Lento sem motivo", "Calor reduz o desempenho e o sistema acumula lixo com o tempo."),
                ("Tela azul ou travamentos", "Pode ser driver, memória ou temperatura. Vale um diagnóstico.")],
     "legenda": "Seu PC deu algum desses sinais? 👀 Manutenção preventiva evita prejuízo e devolve desempenho."},
    {"titulo": "Mito ou verdade?", "kicker": "Edição notebook",
     "slides": [("Usar notebook na cama estraga?", "VERDADE. O tecido bloqueia a entrada de ar e o notebook superaquece."),
                ("Pasta térmica dura para sempre?", "MITO. Ela resseca com o tempo. O ideal é trocar a cada 1–2 anos."),
                ("Deixar na tomada vicia a bateria?", "MITO (na maioria). Os notebooks atuais controlam a carga sozinhos."),
                ("Formatar deixa o PC mais rápido?", "DEPENDE. Ajuda se o sistema está cheio de lixo, mas não resolve calor nem peça fraca."),
                ("Limpar com aspirador resolve?", "MITO. Pode gerar estática e não tira a poeira de dentro do dissipador.")],
     "legenda": "Qual desses você achava que era verdade? 🤔 Conta aqui nos comentários!"},
    {"titulo": "SSD ou HD: vale a troca?", "kicker": "Upgrade que mais compensa",
     "slides": [("Liga em segundos", "Com SSD o Windows inicia muito mais rápido do que com HD."),
                ("Programas voando", "Abrir navegador, jogos e arquivos fica bem mais ágil."),
                ("Mais resistente", "Sem partes móveis: aguenta melhor batidas e quedas."),
                ("Custo-benefício", "É o upgrade mais barato que mais muda o dia a dia."),
                ("A gente migra tudo", "Trocamos o HD pelo SSD e passamos seus arquivos e sistema.")],
     "legenda": "PC ou notebook lento? Antes de trocar de máquina, considere um SSD 🚀"},
    {"titulo": "Como cuidar do seu PC gamer", "kicker": "Dure mais, rode melhor",
     "slides": [("Limpeza a cada 6 meses", "Poeira é a inimiga número 1 da temperatura."),
                ("Fluxo de ar certo", "Ventoinhas puxando ar pela frente e soltando por trás/cima."),
                ("Drivers em dia", "Atualize os drivers da placa de vídeo para mais desempenho."),
                ("Fonte de qualidade", "Fonte ruim derruba o PC e pode queimar peças."),
                ("Fique de olho na temperatura", "CPU e GPU muito acima de 85 °C pedem atenção.")],
     "legenda": "Salva esse post pra não esquecer 💾 Precisa de uma limpeza? A gente faz!"},
    # ---- 12 séries novas (14/10/2026), revisadas: só informação geral e segura, sem números de mercado
    {"titulo": "Quando trocar a pasta térmica?", "kicker": "Manutenção",
     "slides": [("O que ela faz", "Preenche as falhas entre o processador e o cooler para o calor sair melhor."),
                ("Ela resseca", "Com o tempo e o calor, perde a eficiência e a temperatura sobe."),
                ("Sinais de troca", "Ventoinha sempre acelerada, travadas em jogos e PC desligando sozinho."),
                ("De quanto em quanto?", "Em geral a cada 1 a 2 anos, ou antes se o PC fica em lugar quente."),
                ("Junto com a limpeza", "Vale aproveitar a limpeza interna para trocar a pasta.")],
     "legenda": "Faz quanto tempo que você não troca a pasta térmica? 🤔"},
    {"titulo": "Como escolher a fonte do PC", "kicker": "Não economize aqui",
     "slides": [("Potência certa", "Some o consumo das peças e deixe uma folga. Fonte no limite sofre."),
                ("Selo 80 Plus", "Indica eficiência: desperdiça menos energia em calor."),
                ("Marca confiável", "Fonte genérica pode queimar peças caras junto com ela."),
                ("Proteções", "Procure proteções contra sobrecarga, curto e superaquecimento."),
                ("Pensou em upgrade?", "Placa de vídeo nova costuma pedir mais da fonte. Confira antes.")],
     "legenda": "A fonte é a peça que protege todas as outras ⚡ Salva pra lembrar na hora de montar!"},
    {"titulo": "SSD NVMe ou SATA?", "kicker": "Entenda a diferença",
     "slides": [("Os dois são SSD", "Ambos são bem mais rápidos que HD. A diferença está na conexão."),
                ("SATA", "Formato de 2,5 polegadas ou M.2 SATA. Ótimo para PCs e notebooks mais antigos."),
                ("NVMe", "Usa o slot M.2 com PCIe: bem mais rápido em cópia de arquivos grandes."),
                ("Veja a compatibilidade", "Nem todo slot M.2 aceita NVMe. Confira o manual da placa."),
                ("No dia a dia", "Para uso comum, os dois deixam o PC muito mais ágil que um HD.")],
     "legenda": "Seu PC aceita NVMe? Se não souber, chama no direct que a gente confere 🔍"},
    {"titulo": "Quanto de memória RAM você precisa?", "kicker": "Depende do uso",
     "slides": [("Uso básico", "Navegar, estudar e ver vídeos: 8 GB já ajudam, 16 GB dão folga."),
                ("Jogos", "Hoje 16 GB é o ponto ideal para a maioria dos jogos."),
                ("Edição e trabalho pesado", "Vídeo, 3D e muitas abas abertas pedem 32 GB ou mais."),
                ("Dual channel", "Dois pentes iguais rendem mais do que um pente só do mesmo tamanho."),
                ("Compatibilidade", "Veja o tipo (DDR4 ou DDR5) e o limite que a placa-mãe aceita.")],
     "legenda": "Quantos GB tem o seu PC hoje? Conta aqui 👇"},
    {"titulo": "Windows lento? 5 dicas", "kicker": "Antes de formatar",
     "slides": [("Programas ao iniciar", "Desative no Gerenciador de Tarefas o que não precisa abrir com o PC."),
                ("Espaço livre", "Disco cheio deixa tudo lento. Libere espaço e esvazie a lixeira."),
                ("Atualizações", "Mantenha Windows e drivers atualizados."),
                ("Antivírus em dia", "Vírus e programas indesejados consomem memória e processador."),
                ("HD antigo?", "Se ainda usa HD, um SSD é a melhora que mais se sente.")],
     "legenda": "Testou e continua lento? Pode ser hardware ou temperatura: a gente faz o diagnóstico 🔧"},
    {"titulo": "Sinais de que o HD vai falhar", "kicker": "Proteja seus arquivos",
     "slides": [("Barulhos estranhos", "Cliques ou estalos repetidos são sinal de alerta."),
                ("Muito lento do nada", "Arquivos demorando para abrir e travamentos frequentes."),
                ("Arquivos corrompidos", "Fotos e documentos que não abrem mais."),
                ("Erros ao iniciar", "Mensagens de disco ou Windows que não carrega."),
                ("Faça backup JÁ", "Ao primeiro sinal, copie o que é importante antes de qualquer coisa.")],
     "legenda": "Backup é o seguro dos seus arquivos 💾 Precisa recuperar ou trocar o disco? Chama a gente."},
    {"titulo": "Upgrade ou PC novo?", "kicker": "Antes de gastar",
     "slides": [("Lento no dia a dia", "Muitas vezes um SSD e mais memória resolvem."),
                ("Jogos travando", "A placa de vídeo costuma ser o upgrade que mais rende em jogos."),
                ("Plataforma antiga", "Se processador, placa-mãe e memória são muito antigos, pode valer trocar a base."),
                ("Faça as contas", "Some o preço das peças novas e compare com um PC novo equivalente."),
                ("Peça uma avaliação", "Um diagnóstico mostra onde está o gargalo antes de comprar.")],
     "legenda": "Na dúvida entre upgrade e PC novo? Traz o seu que a gente avalia 🔍"},
    {"titulo": "Como fazer backup dos seus arquivos", "kicker": "Não perca nada",
     "slides": [("Regra simples", "Tenha seus arquivos importantes em pelo menos dois lugares."),
                ("HD ou SSD externo", "Prático e barato para copiar fotos e documentos."),
                ("Nuvem", "Google Drive, OneDrive e afins guardam fora de casa."),
                ("Com frequência", "Backup antigo protege pouco. Crie o hábito de atualizar."),
                ("Teste a cópia", "De vez em quando, abra os arquivos do backup para garantir que funcionam.")],
     "legenda": "Quando foi seu último backup? 😅 Salva esse post como lembrete!"},
    {"titulo": "Cuidados com o seu console", "kicker": "PlayStation • Xbox • Switch",
     "slides": [("Espaço para respirar", "Deixe as saídas de ar livres, longe de paredes e de estantes fechadas."),
                ("Poeira", "Ela entra e entope o cooler. Limpeza interna periódica ajuda muito."),
                ("Barulho alto", "Ventoinha gritando é sinal de poeira ou pasta térmica seca."),
                ("Tomada e energia", "Use filtro de linha ou estabilizador de qualidade."),
                ("Não deixe no chão", "No chão junta mais poeira e pelo de animais.")],
     "legenda": "Seu console está barulhento? A gente faz a limpeza completa 🎮"},
    {"titulo": "Notebook esquentando?", "kicker": "Entenda o porquê",
     "slides": [("Saídas tapadas", "Usar na cama ou no colo bloqueia a entrada de ar."),
                ("Poeira no cooler", "Ela vai se acumulando e o ar não passa."),
                ("Pasta térmica seca", "Com o tempo perde eficiência e a temperatura sobe."),
                ("Base com ventilação", "Ajuda, mas não substitui a limpeza interna."),
                ("Fique atento", "Desligamentos e lentidão em uso pesado pedem uma revisão.")],
     "legenda": "Seu notebook parece uma chapa quente? 🔥 A limpeza interna resolve na maioria dos casos."},
    {"titulo": "Montar PC: o que ver antes", "kicker": "Checklist rápido",
     "slides": [("Processador + placa-mãe", "O soquete precisa ser o mesmo (ex.: AM4, AM5, LGA1700)."),
                ("Memória", "DDR4 ou DDR5: a placa-mãe aceita só um tipo."),
                ("Placa de vídeo cabe?", "Confira o comprimento suportado pelo gabinete."),
                ("Fonte com folga", "Potência suficiente e conectores para a placa de vídeo."),
                ("Refrigeração", "Cooler compatível com o soquete e com a altura do gabinete.")],
     "legenda": "Montar é fácil quando tudo é compatível ✅ Quer que a gente monte pra você? Chama no direct."},
    {"titulo": "Por que limpar o PC por dentro", "kicker": "Manutenção preventiva",
     "slides": [("Temperatura menor", "Sem poeira, o ar circula e as peças trabalham mais frias."),
                ("Menos barulho", "Ventoinhas não precisam girar no máximo o tempo todo."),
                ("Mais vida útil", "Calor constante desgasta as peças mais rápido."),
                ("Desempenho estável", "Peças frias não reduzem a velocidade para se proteger."),
                ("Com que frequência", "Em média a cada 6 a 12 meses, ou menos com pets e poeira.")],
     "legenda": "Abre o seu gabinete e conta: tá muito empoeirado? 😬"},
]


def post_edu() -> None:
    from app.social import enabled
    if not enabled():
        return
    i = int(EDU_STATE.read_text()) if EDU_STATE.exists() else 0
    s = EDU_SERIES[i % len(EDU_SERIES)]
    total = len(s["slides"])
    slides = [_text_slide(s["titulo"], kicker=s["kicker"], big=True, footer="arraste →")]
    slides += [_text_slide(t, b, kicker=f"{k + 1}/{total}") for k, (t, b) in enumerate(s["slides"])]
    slides.append(_cta_slide())
    from app.templates import chamada_grupos
    caption = f"{s['legenda']}\n\n🔧 " + " • ".join(CTA_LINES) + f"\n{chamada_grupos(False)}\n\n{TAGS}"
    orcamento = f"💬 Orçamento: https://wa.me/{settings.store_whatsapp}" if settings.store_whatsapp else ""
    fb = f"{s['legenda']}\n\n🔧 " + " • ".join(CTA_LINES) + f"\n{orcamento}\n\n{chamada_grupos(True)}"
    done = publish_carousel(slides, caption, fb_caption=fb)
    if done:
        EDU_STATE.write_text(str(i + 1))
    log.info("edu_posted", serie=s["titulo"], nets=done)


# ---------------------------------------------------------------- educativo NOVO escrito pela IA local (com aprovação)
EDU_PROMPT = """Você é social media de uma loja de manutenção e montagem de computadores em São Paulo (TechHammer).
Crie um carrossel EDUCATIVO para Instagram sobre: "{topic}".
Regras: português do Brasil, frases curtas, tom próximo e confiável. NÃO invente números, preços, marcas ou estatísticas.
Só dicas corretas e conhecidas de manutenção/hardware. Se não tiver certeza de algo, não coloque.
Responda SÓ em JSON:
{{"titulo": "título da capa (máx. 7 palavras)", "kicker": "subtítulo curto (máx. 4 palavras)",
  "slides": [["título curto", "explicação de até 18 palavras"], ... exatamente 5 itens],
  "legenda": "2 frases para a legenda com 1 ou 2 emojis e uma pergunta para gerar comentários"}}"""
EDU_TOPICS = ["por que o notebook esquenta", "quando trocar a pasta térmica", "como escolher uma fonte para PC",
              "SSD NVMe x SATA", "quanto de memória RAM você precisa", "como deixar o Windows mais rápido",
              "cuidados com o console", "sinais de que o HD vai falhar", "upgrade ou PC novo?",
              "como fazer backup dos seus arquivos"]


def draft_edu(topic: str = "") -> str:
    if not topic:
        i = int(EDU_STATE.read_text()) if EDU_STATE.exists() else 0
        topic = EDU_TOPICS[i % len(EDU_TOPICS)]
    try:
        r = gpu.post(f"{settings.ollama_url}/api/chat", timeout=240, json={
            "model": settings.ai_model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0.4, "num_predict": 900, "num_gpu": settings.bot_ai_num_gpu},
            "messages": [{"role": "user", "content": EDU_PROMPT.format(topic=topic)}]})
        s = json.loads(r.json()["message"]["content"])
        items = [(str(a), str(b)) for a, b in s["slides"]][:5]
        assert s.get("titulo") and len(items) >= 3
    except Exception as e:
        log.warning("edu_ai_failed", error=str(e)[:200])
        return "⚠️ A IA não conseguiu montar o post agora. Tente de novo em instantes."
    total = len(items)
    slides = [_text_slide(s["titulo"], kicker=s.get("kicker") or "Fica a dica", big=True, footer="arraste →")]
    slides += [_text_slide(t, b, kicker=f"{k + 1}/{total}") for k, (t, b) in enumerate(items)]
    slides.append(_cta_slide())
    caption = f"{s.get('legenda', '')}\n\n🔧 " + " • ".join(CTA_LINES) + f"\n\n{TAGS}"
    shutil.rmtree(PENDING, ignore_errors=True)
    PENDING.mkdir(parents=True)
    for i, sl in enumerate(slides):
        (PENDING / f"{i:02d}.jpg").write_bytes(sl)
    (PENDING / "caption.txt").write_text(caption)
    texto = "\n".join(f"{k + 1}. {t} — {b}" for k, (t, b) in enumerate(items))
    _send_owner(f"👀 PRÉVIA educativo: *{s['titulo']}*\n\n{texto}\n\nLegenda:\n{caption}", slides[0])
    for sl in slides[1:]:
        _send_owner("", sl)
    return "✅ Prévia salva em data/service_post. Confira se as dicas estão CORRETAS: `ctl aprovar` publica | `ctl cancelar` descarta."
