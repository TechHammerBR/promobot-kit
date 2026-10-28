"""API interna que usa o navegador logado para gerar links de afiliado do ML.

GET /health            -> {"ok": true, "logged_in": bool}
GET /debug?url=...     -> inspeciona a página do produto (descoberta do botão de afiliado)
GET /link?url=...      -> {"link": "https://meli.la/..."}

Single-thread de propósito: uma requisição por vez = cadência natural.
"""
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

DATA = os.environ.get("LINKGEN_DATA", "/data")
PROFILE = DATA + "/profile"

pw = sync_playwright().start()
_ctx = None
_closed = True


def _on_close(_):
    global _closed
    _closed = True


def browser():
    """Contexto persistente; reabre se o dono fechou a janela (o login fica salvo no perfil)."""
    global _ctx, _closed
    if _ctx is None or _closed:
        _ctx = pw.chromium.launch_persistent_context(
            PROFILE, headless=False, locale="pt-BR", timezone_id="America/Sao_Paulo",
            executable_path=os.environ.get("LINKGEN_CHROMIUM") or None,  # Wyse: Chromium do sistema (sem baixar o do Playwright)
            viewport={"width": 1366, "height": 820},
            # --restore-last-session: reabre as abas (e sessões) que estavam abertas antes do reinício
            args=["--disable-blink-features=AutomationControlled", "--no-first-run", "--restore-last-session",
                  "--window-position=0,0", "--window-size=1366,880", "--disk-cache-size=41943040",
                  "--renderer-process-limit=3", "--disable-background-networking", "--disable-component-update",
                  # Wyse (1,9 GB, sem GPU): sem GPU por software, sem isolamento de sites (menos processos), heap do JS limitado
                  "--disable-gpu", "--disable-software-rasterizer", "--disable-extensions", "--disable-sync", "--mute-audio",
                  "--disable-features=Translate,BackForwardCache,MediaRouter,OptimizationHints,IsolateOrigins,site-per-process",
                  "--js-flags=--max-old-space-size=320"],
        )
        _closed = False
        _ctx.on("close", _on_close)
        _ctx.on("request", _netlog)
        home = _ctx.pages[0] if _ctx.pages else _ctx.new_page()
        if home.url in ("about:blank", ""):
            home.goto("https://www.mercadolivre.com.br/afiliados")
    return _ctx


NETLOG: list = []  # chamadas de escrita do painel do ML (diagnostico: descobrir como listas funcionam); nunca guarda cookies/headers


def _netlog(r) -> None:
    try:
        if r.method != "GET" and "mercadoli" in r.url and "melidata" not in r.url and "notifications" not in r.url:
            NETLOG.append({"m": r.method, "u": r.url[:230], "b": (r.post_data or "")[:500]})
            del NETLOG[:-60]
    except Exception:
        pass


COOKIES_FILE = DATA + "/session_cookies.json"
KEEP_DOMAINS = ("aliexpress", "alibaba", "alipay")  # sessões que o Chromium NÃO grava sozinho


def _save_cookies() -> None:
    """Guarda os cookies de sessão do AliExpress (somem quando o navegador reinicia)."""
    try:
        keep = [c for c in browser().cookies() if any(d in c["domain"] for d in KEEP_DOMAINS)]
        if keep:
            with open(COOKIES_FILE, "w") as f:
                json.dump(keep, f)
            os.chmod(COOKIES_FILE, 0o600)
    except Exception as e:
        print("linkgen: falha ao salvar cookies:", e, flush=True)


def _restore_cookies() -> None:
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE) as f:
                browser().add_cookies(json.load(f))
            print("linkgen: sessão do AliExpress restaurada", flush=True)
        except Exception as e:
            print("linkgen: falha ao restaurar cookies:", e, flush=True)


def _tab(match: str):
    """Aba já aberta cuja URL contém `match` (abre uma se não houver)."""
    pages = [p for p in browser().pages if match and match in p.url]
    if pages:
        return pages[-1]
    p = browser().new_page()
    return p


browser()
for _p in list(browser().pages):  # só o Mercado Livre fica aberto (economiza ~300 MB)
    if "aliexpress" in _p.url or "alibaba" in _p.url:
        try:
            _p.close()
        except Exception:
            pass


_ali_checked = {"t": 0.0, "ok": None}


def ali_logged_in() -> bool | None:
    """Login do AliExpress Portals. DESLIGADO no Wyse (14/10): o AliExpress usa a API oficial; abrir o Portals gastava memória."""
    return None
    if time.time() - _ali_checked["t"] < 1800:
        return _ali_checked["ok"]
    try:
        p = _tab("portals.aliexpress")
        p.goto("https://portals.aliexpress.com/affiportals/web/home.htm", wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        _ali_checked["ok"] = not p.get_by_text("Sign in", exact=True).count()
        if _ali_checked["ok"]:
            _save_cookies()
    except Exception as e:
        print("linkgen: checagem AliExpress falhou:", e, flush=True)
        _ali_checked["ok"] = None
    _ali_checked["t"] = time.time()
    return _ali_checked["ok"]


def logged_in() -> bool:
    return any(c["name"] in ("ssid", "orgnickp", "orguseridp") for c in browser().cookies("https://www.mercadolivre.com.br"))


def debug(url: str) -> dict:
    p = browser().new_page()
    reqs = []
    p.on("request", lambda r: reqs.append(f"{r.method} {r.url[:200]}") if re.search(r"affiliat|afiliad|meli\.la|social|share", r.url, re.I) else None)
    try:
        p.goto(url, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        texts = p.eval_on_selector_all(
            "button, a, [role=button]",
            "els => els.map(e => (e.innerText||e.getAttribute('aria-label')||'').trim()).filter(t => /compart|afilia|link|ganh|indic/i.test(t)).slice(0,30)",
        )
        html = p.content()
        hints = sorted(set(re.findall(r'(?:class|data-testid)="([^"]*(?:affiliat|afiliad|share|social)[^"]*)"', html, re.I)))[:40]
        stripe = p.evaluate(
            """() => { const el = [...document.querySelectorAll('*')].reverse()
                 .find(e => /GANHE/.test(e.innerText||'') && e.querySelector('button, a'));
               return el ? el.closest('div[class*=stripe], div[id*=stripe], header, div').outerHTML.slice(0, 4000) : null }"""
        )
        return {"url": p.url, "buttons": texts, "hints": hints, "requests": reqs[:40], "stripe": stripe}
    finally:
        p.close()


MELI_LA = re.compile(r"https://meli\.la/[A-Za-z0-9]+")


PAGE_INFO_JS = """() => {
  const num = el => el ? parseFloat((el.querySelector('.andes-money-amount__fraction')?.innerText || '').replace(/\\./g, '')
      + '.' + (el.querySelector('.andes-money-amount__cents')?.innerText || '00')) : null;
  const og = document.querySelector('meta[property="og:image"]');
  return {
    price: num(document.querySelector('.ui-pdp-price__second-line')),
    old_price: num(document.querySelector('.ui-pdp-price__original-value')),
    // foto da galeria do produto (o og:image às vezes é a logo do ML)
    // maior foto de produto da página (fotos de produto do ML têm "/D_" na URL; og:image às vezes é a logo)
    image: (() => {
      // só dentro da galeria do próprio produto (fora dela há fotos de anúncios relacionados)
      const gal = document.querySelector('[class*="ui-pdp-gallery"]');
      if (!gal) return null;
      const imgs = [...gal.querySelectorAll('img')]
        .map(i => ({ u: i.getAttribute('data-zoom') || i.currentSrc || i.src || '', a: i.naturalWidth * i.naturalHeight }))
        .filter(x => /mlstatic\\.com\\/D_/.test(x.u))
;  // ordem da galeria: a 1ª é a foto principal (a maior costuma ser vídeo/propaganda)
      return imgs.length ? imgs[0].u : (og && /\\/D_/.test(og.content) ? og.content : null);
    })(),
    // todas as fotos da galeria do produto, na ordem (reserva quando a principal é reprovada)
    gallery: (() => {
      const gal = document.querySelector('[class*="ui-pdp-gallery"]') || document.querySelector('[class*="ui-pdp-thumbnail"]')?.parentElement;
      if (!gal) return [];
      const seen = new Set(), out = [];
      for (const i of gal.querySelectorAll('img')) {
        const u = i.getAttribute('data-zoom') || i.getAttribute('data-src') || i.currentSrc || i.src || '';
        const id = (u.match(/D_[A-Z_0-9]*?(\\d{5,}-ML[AB]\\d+)/) || [])[1];
        if (id && !seen.has(id)) { seen.add(id); out.push(u); }
      }
      return out.slice(0, 8);
    })(),
    // cupons/benefícios mostrados na própria página do produto (valem para quem abrir o link)
    coupons: [...document.querySelectorAll('[class*=coupon], [class*=Coupon], .ui-pdp-promotions-pill-label')]
      .map(e => (e.innerText || '').trim()).filter(t => /OFF|cupom|desconto/i.test(t) && t.length < 200)
      .filter((t, i, a) => a.indexOf(t) === i).slice(0, 5),
    title: document.querySelector('h1.ui-pdp-title')?.innerText || null,
    // condição de pagamento mostrada abaixo do preço (ex.: "em 10x R$ 98,90 sem juros")
    installments: (document.querySelector('.ui-pdp-price__subtitles, [class*="price__subtitles"], [class*="installments"]')
      ?.innerText || '').replace(/\\s+/g, ' ').trim() || null,
    available: !document.querySelector('.ui-pdp-stock-information__title--paused, .ui-pdp-message--paused'),
  };
}"""


COUPON_CARDS_JS = """() => {
  // card de cupom = menor elemento que contém o desconto ("OFF") e o vencimento ("Vence")
  const all = [...document.querySelectorAll('div, li, article')]
    .filter(e => /OFF/.test(e.innerText || '') && /Vence/.test(e.innerText || ''));
  const cards = all.filter(e => !all.some(o => o !== e && e.contains(o)));
  return cards.map(c => {
    const sec = c.closest('section, div[class*=section], div[class*=carousel]');
    const h = sec ? sec.querySelector('h2, h3') : null;
    return {text: c.innerText.trim(), section: h ? h.innerText.trim() : null};
  });
}"""


def coupons(url: str, scrolls: int) -> list[dict]:
    p = browser().new_page()
    try:
        p.goto(url, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        for _ in range(scrolls):  # rolagem lenta, como uma pessoa
            p.mouse.wheel(0, 1400)
            p.wait_for_timeout(1200)
        return p.evaluate(COUPON_CARDS_JS)
    finally:
        p.close()


ALI_GENERATOR = "https://portals.aliexpress.com/affiportals/web/link_generator.htm"


def ali_link(url: str) -> dict:
    """Tenta 2x (o Portals às vezes não responde na 1ª)."""
    try:
        return _ali_link_once(url)
    except RuntimeError as e:
        if "sem login" in str(e):
            raise
        print("linkgen: ali_link 2a tentativa:", e, flush=True)
        return _ali_link_once(url)


def _ali_link_once(url: str) -> dict:
    """Link de afiliado AliExpress pelo Link Generator do Portals, NA ABA JÁ LOGADA. Ship to = Brazil."""
    p = _tab("portals.aliexpress")
    p.goto(ALI_GENERATOR, wait_until="domcontentloaded", timeout=45000)
    if "login" in p.url or p.get_by_text("Sign in", exact=True).count():
        raise RuntimeError("Portals sem login (dono precisa entrar pelo atalho Navegador do Servidor)")
    p.get_by_text("Get Tracking Link").first.wait_for(timeout=20000)
    # Ship to: adiciona Brazil e tira Canada (padrão do gerador)
    ship = p.locator("text=Ship to").locator("xpath=following::*[@role='combobox' or contains(@class,'select')][1]").first
    try:
        ship.click(timeout=5000)
        p.keyboard.type("Brazil", delay=60)
        p.wait_for_timeout(800)
        p.get_by_text("Brazil", exact=True).last.click(timeout=5000)
        p.keyboard.press("Escape")
        for tag in p.locator("span", has_text="Canada").all():
            close = tag.locator("xpath=following-sibling::*[1] | ..//*[contains(@class,'close') or local-name()='svg']").first
            if close.count():
                close.click(timeout=3000)
                break
    except Exception as e:
        print("linkgen: ship-to não ajustado:", e, flush=True)
    p.locator("textarea").first.fill(url)
    p.locator("textarea").nth(1).evaluate("e => e.value = ''")
    p.get_by_text("Get Tracking Link").first.click()
    for _ in range(40):
        p.wait_for_timeout(500)
        out = p.locator("textarea").nth(1).input_value()
        if out.startswith("https://s.click.aliexpress.com"):
            ship_to = p.evaluate("() => document.body.innerText.includes('Brazil')")
            _save_cookies()
            return {"link": out, "ship_to_brazil": ship_to}
    raise RuntimeError("Portals não devolveu o link de afiliado")


ALI_AD_CENTER = "https://portals.aliexpress.com/affiportals/web/ad_center.htm"

ALI_CARDS_JS = """() => {
  const out = [];
  for (const a of document.querySelectorAll('a[href*="/item/"]')) {
    let c = a;
    for (let i = 0; i < 8 && c && !/Max\\. ea/i.test(c.innerText || ''); i++) c = c.parentElement;
    if (!c) continue;
    const img = a.querySelector('img');
    out.push({href: a.href, text: c.innerText, image: img ? img.src : null});
  }
  return out;
}"""


def _ali_set_region(p, region: str = "Brazil") -> str:
    """Troca o seletor de região/moeda do Ad Center (ex.: 'Canada/USD' -> 'Brazil/BRL')."""
    current = p.locator("em").filter(has_text="/").first
    label = current.inner_text(timeout=5000) if current.count() else ""
    if region.lower() in label.lower():
        return label
    # o seletor abre um painel com 2 campos: "Ship to" (país) e "Currency" (moeda)
    current.locator("xpath=ancestor::span[contains(@class,'next-select-values')]//input[@role='combobox']").first.click(timeout=5000)
    p.wait_for_timeout(1200)
    panel = p.locator(".next-overlay-wrapper").filter(has_text="Currency").last

    def pick(field_label: str, value: str) -> None:
        field = panel.locator(f"xpath=.//*[normalize-space(text())='{field_label}']/following::*[contains(@class,'next-select')][1]").first
        field.click(timeout=5000)
        p.wait_for_timeout(800)
        p.keyboard.type(value, delay=50)  # campos com busca filtram enquanto digita
        p.wait_for_timeout(1000)
        opt = p.locator(".next-overlay-wrapper li, [role=option]").filter(has_text=re.compile(rf"^\s*{value}\b", re.I)).first
        if opt.count():
            opt.click(timeout=5000)
        else:
            p.keyboard.press("Enter")
        p.wait_for_timeout(1000)

    pick("Ship to", region)
    pick("Currency", "BRL")
    p.keyboard.press("Escape")
    p.mouse.click(5, 300)  # fecha o painel; a lista recarrega com a nova região/moeda
    p.wait_for_timeout(5000)
    return p.locator("em").filter(has_text="/").first.inner_text(timeout=5000)


def ali_offers(query: str = "", scrolls: int = 3) -> dict:
    """Produtos do Ad Center (aba Search com palavra-chave, ou Hot Deals), região Brasil, na aba logada."""
    p = _tab("portals.aliexpress")
    p.goto(ALI_AD_CENTER, wait_until="domcontentloaded", timeout=45000)
    p.get_by_text("Hot Deals", exact=True).first.wait_for(timeout=20000)
    if query:
        p.get_by_text("Search", exact=True).first.click(timeout=10000)
        p.wait_for_timeout(2500)
        box = p.locator("input[placeholder*='earch'], input[placeholder*='keyword'], input[placeholder*='URL'], input[type=text]").first
        box.fill(query, timeout=10000)
        box.press("Enter")
        p.wait_for_timeout(6000)
    region = _ali_set_region(p)
    for _ in range(scrolls):  # rolagem lenta (carrega mais cards)
        p.mouse.wheel(0, 1600)
        p.wait_for_timeout(1500)
    cards = p.evaluate(ALI_CARDS_JS)
    _save_cookies()
    return {"region": region, "cards": cards}


def generate(url: str, tag: str | None = None) -> dict:
    """Abre o produto, lê preço/foto atuais, clica em Compartilhar (barra de afiliados) e captura o meli.la."""
    p = browser().new_page()
    seen: list[str] = []
    calls: list[str] = []

    def on_response(r):
        if re.search(r"affiliate|afiliad|meli\.la|stripe|share", r.url, re.I):
            calls.append(f"{r.request.method} {r.status} {r.url[:180]}")
            try:
                seen.extend(MELI_LA.findall(r.text()))
            except Exception:
                pass

    p.on("response", on_response)
    try:
        p.goto(url, wait_until="domcontentloaded", timeout=45000)
        # barra preta de afiliados no topo: botão azul "Compartilhar" -> modal "Gerar link / ID de produto"
        btn = p.get_by_text("Compartilhar", exact=True).first
        btn.wait_for(state="visible", timeout=20000)
        p.wait_for_timeout(1500)
        info = p.evaluate(PAGE_INFO_JS)
        if tag:  # caminho rápido: a mesma chamada do botão, com a etiqueta do canal (sem abrir modal)
            try:
                res = p.evaluate("""async ([u, t]) => {
                    const r = await fetch('/affiliate-program/api/v2/stripe/user/links', {method: 'POST', credentials: 'include',
                        headers: {'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json'},
                        body: JSON.stringify({tag: t, url: u})});
                    const j = await r.json().catch(() => null);
                    return {status: r.status, short: j && j.short_url, tag: j && j.tag};
                }""", [p.url.split("#")[0], tag])
                if res.get("status") == 200 and res.get("short") and res.get("tag") == tag:
                    return {"link": res["short"], "tag": tag, **info}
                print(f"linkgen: chamada rápida sem link ({res}); usando o modal", flush=True)
            except Exception as e:  # noqa: BLE001
                print("linkgen: chamada rápida falhou:", str(e)[:120], "; usando o modal", flush=True)
        btn.click(timeout=10000)
        p.get_by_text("Gerar link").first.wait_for(timeout=15000)
        for _ in range(20):
            p.wait_for_timeout(500)
            seen.extend(MELI_LA.findall(p.content()))
            for el in p.locator("input, textarea").all():
                try:
                    seen.extend(MELI_LA.findall(el.input_value(timeout=500)))
                except Exception:
                    pass
            if seen:
                return {"link": seen[0], **info}
        raise RuntimeError(f"meli.la não apareceu. chamadas: {calls[-12:]}")
    finally:
        p.close()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/health":
                return self._send(200, {"ok": True, "logged_in": logged_in(), "ali_logged_in": ali_logged_in()})
            if u.path == "/open":  # abre uma aba visível (para o dono fazer login pela tela)
                p = browser().new_page()
                p.goto(q["url"][0], wait_until="domcontentloaded", timeout=45000)
                p.bring_to_front()
                return self._send(200, {"opened": p.url})
            # ---- operar numa aba JÁ ABERTA (ex.: Portals logado), sem abrir outra ----
            if u.path in ("/tab_goto", "/tab_click", "/tab_fill", "/tab_eval"):
                p = _tab(q.get("match", [""])[0])
                if u.path == "/tab_goto":
                    p.goto(q["url"][0], wait_until="domcontentloaded", timeout=45000)
                elif u.path == "/tab_click":
                    p.get_by_text(q["text"][0], exact=q.get("exact", ["0"])[0] == "1").first.click(timeout=15000)
                elif u.path == "/tab_fill":
                    p.locator(q["selector"][0]).first.fill(q["value"][0], timeout=15000)
                else:
                    return self._send(200, {"result": p.evaluate(q["js"][0]), "url": p.url})
                p.wait_for_timeout(int(q.get("wait", ["2500"])[0]))
                _save_cookies()
                return self._send(200, {"url": p.url})
            if u.path == "/tab_upload":  # envia um arquivo para um <input type=file> da aba JA ABERTA (foto de perfil)
                p = _tab(q.get("match", [""])[0])
                p.locator(q["selector"][0]).first.set_input_files(q["path"][0], timeout=20000)
                p.wait_for_timeout(int(q.get("wait", ["2500"])[0]))
                return self._send(200, {"url": p.url, "enviado": q["path"][0]})
            if u.path == "/netlog":
                if q.get("clear"):
                    NETLOG.clear()
                return self._send(200, {"calls": list(NETLOG)})
            if u.path == "/ali_offers":
                return self._send(200, ali_offers(q.get("q", [""])[0], int(q.get("scrolls", ["3"])[0])))
            if u.path == "/ali_link":
                return self._send(200, ali_link(q["url"][0]))
            if u.path == "/tabs":  # abas abertas (sem abrir nada novo)
                _save_cookies()
                return self._send(200, {"tabs": [{"i": i, "url": p.url, "title": p.title()} for i, p in enumerate(browser().pages)]})
            if u.path == "/screen":  # print de uma aba JÁ ABERTA (ex.: ?match=portals.aliexpress), sem navegar
                match = q.get("match", [""])[0]
                pages = [p for p in browser().pages if match in p.url] or browser().pages
                p = pages[-1]
                p.screenshot(path=DATA + "/shot.png")
                return self._send(200, {"saved": DATA + "/shot.png", "url": p.url})
            if u.path == "/coupons":
                return self._send(200, {"coupons": coupons(q["url"][0], int(q.get("scrolls", ["6"])[0]))})
            if u.path == "/shot":  # print da página (diagnóstico) em /data/shot.png
                p = browser().new_page()
                try:
                    p.goto(q["url"][0], wait_until="domcontentloaded", timeout=45000)
                    p.wait_for_timeout(6000)
                    if "click" in q:
                        p.get_by_text(q["click"][0]).first.click(timeout=10000)
                        p.wait_for_timeout(4000)
                    p.screenshot(path=DATA + "/shot.png")
                    frames = [f.url[:150] for f in p.frames]
                finally:
                    p.close()
                return self._send(200, {"saved": DATA + "/shot.png", "frames": frames})
            if u.path == "/debug":
                return self._send(200, debug(q["url"][0]))
            if u.path == "/link":
                t = time.time()
                return self._send(200, {**generate(q["url"][0], q.get("tag", [None])[0]), "secs": round(time.time() - t, 1)})
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        print("linkgen:", fmt % args, flush=True)


print("linkgen pronto na porta 8000", flush=True)
HTTPServer((os.environ.get("LINKGEN_BIND", "0.0.0.0"), 8000), Handler).serve_forever()
