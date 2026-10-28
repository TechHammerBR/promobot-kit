"""Pagina de status do robo e do Wyse (somente leitura, 100% local): http://<ip-do-wyse>:8088  (liberada so para a rede de casa pelo UFW).
Usa so a biblioteca padrao; le o banco em modo somente leitura, /proc, /sys e arquivos de log. Sem segredos, sem links de afiliado.
Uma thread amostra CPU, memoria e IO dos discos a cada 10 s (historico de 30 min para os mini-graficos). Servico: promobot-status.service (MemoryMax 80M)."""
import collections
import glob
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DB = "/opt/promobot/data/promobot.db"
DATA = Path("/opt/promobot/data")
FILA = Path("/srv/cache/reels-prontos/fila")
BRT = timezone(timedelta(hours=-3))
LIMITE = 200
_cache = {"t": 0.0, "html": ""}
HIST = collections.deque(maxlen=180)  # (t, cpu%, ram_usada_MB, {disco: (lido MB/s, gravado MB/s)})
_lock = threading.Lock()
_extra = {"lsblk": (0.0, None), "smart": (0.0, None)}


# ---------------------------------------------------------------- amostragem (thread)
def _cpu():
    p = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    v = [int(x) for x in p]
    return v[3] + v[4], sum(v)  # idle+iowait, total


def _discos():
    out = {}
    for l in Path("/proc/diskstats").read_text().splitlines():
        f = l.split()
        if re.match(r"^(sd[a-z]|mmcblk\d+|zram\d+)$", f[2]):
            out[f[2]] = (int(f[5]) * 512, int(f[9]) * 512)  # bytes lidos, gravados
    return out


def _mem_usada():
    m = {}
    for l in Path("/proc/meminfo").read_text().splitlines():
        k, v = l.split(":")
        m[k] = int(v.split()[0]) // 1024
    return m["MemTotal"] - m["MemAvailable"]


def amostrar():
    idle0, tot0 = _cpu()
    d0 = _discos()
    t0 = time.time()
    while True:
        time.sleep(10)
        try:
            idle1, tot1 = _cpu()
            d1 = _discos()
            t1 = time.time()
            dt = max(t1 - t0, 0.1)
            cpu = 100.0 * (1 - (idle1 - idle0) / max(tot1 - tot0, 1))
            io = {k: ((d1[k][0] - d0.get(k, d1[k])[0]) / dt / 1e6, (d1[k][1] - d0.get(k, d1[k])[1]) / dt / 1e6) for k in d1}
            with _lock:
                HIST.append((t1, cpu, _mem_usada(), io))
            idle0, tot0, d0, t0 = idle1, tot1, d1, t1
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- utilidades
def q(sql, args=()):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def brt(utc_txt):
    try:
        return datetime.fromisoformat(utc_txt).replace(tzinfo=timezone.utc).astimezone(BRT).strftime("%H:%M")
    except Exception:  # noqa: BLE001
        return "?"


_sh_cache = {}


def sh(cmd, t=8, ttl=45):
    """Executa um comando e guarda a resposta por ttl segundos (cada processo novo custa CPU no Wyse)."""
    k = tuple(cmd)
    agora = time.time()
    if k in _sh_cache and agora - _sh_cache[k][0] < ttl:
        return _sh_cache[k][1]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception:  # noqa: BLE001
        out = ""
    _sh_cache[k] = (agora, out)
    return out


def esc(x):
    return html.escape(str(x))


def card(titulo, corpo):
    return f"<section><h2>{esc(titulo)}</h2>{corpo}</section>"


def tabela(linhas, cab=None):
    t = "<table>"
    if cab:
        t += "<tr>" + "".join(f"<th>{esc(c)}</th>" for c in cab) + "</tr>"
    for l in linhas:
        t += "<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>"
    return t + "</table>"


def barra(n, tot):
    pct = min(100, int(100 * n / tot)) if tot else 0
    return f'<div class="barra"><div style="width:{pct}%"></div></div>'


def spark(vals, maxv=None, w=150, h=28):
    if len(vals) < 2:
        return ""
    mx = maxv if maxv else max(max(vals), 0.001)
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 2 - min(v, mx) / mx * (h - 4):.1f}" for i, v in enumerate(vals))
    return f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline fill="none" stroke="var(--ac)" stroke-width="1.6" points="{pts}"/></svg>'


def ok(txt, bom=True):
    return f'<span class="{"ok" if bom else "ruim"}">{esc(txt)}</span>'


# ---------------------------------------------------------------- discos
def lsblk():
    t, v = _extra["lsblk"]
    if time.time() - t > 30 or v is None:
        try:
            v = json.loads(sh(["lsblk", "-J", "-b", "-o", "NAME,LABEL,MODEL,SIZE,TRAN,MOUNTPOINT,FSTYPE,TYPE"]) or "{}").get("blockdevices", [])
        except Exception:  # noqa: BLE001
            v = []
        _extra["lsblk"] = (time.time(), v)
    return v


def usb_vel(dev):
    try:
        p = Path(os.path.realpath(f"/sys/block/{dev}/device"))
        for _ in range(9):
            if (p / "speed").exists():
                s = int((p / "speed").read_text())
                return f"USB 3.0 · {s // 1000} Gbps" if s >= 5000 else f"USB 2.0 · {s} Mbps"
            p = p.parent
    except Exception:  # noqa: BLE001
        pass
    return "interno"


PAPEL = {"/": "sistema + robô", "/srv/cache": "armazenamento principal (cache)", "/srv/cache-copia": "cópia do cache (hora em hora)",
         "/srv/backup": "backups e imagem do Wyse", "/srv/espelho": "espelho dos itens críticos", "/boot/efi": "boot"}


def smart_ssd(dev):
    t, v = _extra["smart"]
    if time.time() - t > 300 or v is None:
        v = {}
        out = sh(["sudo", "-n", "smartctl", "-A", "-d", "sntrealtek", f"/dev/{dev}"], t=15)
        for k, rx in (("temp", r"^Temperature:\s+(\d+)"), ("uso", r"Percentage Used:\s+(\d+)"), ("reserva", r"Available Spare:\s+(\d+)"),
                      ("erros", r"Media and Data Integrity Errors:\s+(\d+)")):
            m = re.search(rx, out, re.M)
            v[k] = int(m.group(1)) if m else None
        _extra["smart"] = (time.time(), v)
    return v


def sec_discos():
    with _lock:
        h = list(HIST)
    io_atual, io_serie = {}, {}
    ult = [x for x in h if x[0] > time.time() - 60]
    for x in ult:
        for k, (r, w) in x[3].items():
            a = io_atual.setdefault(k, [0.0, 0.0, 0])
            a[0] += r
            a[1] += w
            a[2] += 1
    for k, a in io_atual.items():
        io_atual[k] = (a[0] / a[2], a[1] / a[2])
    for x in h:
        for k, (r, w) in x[3].items():
            io_serie.setdefault(k, []).append(r + w)
    total_gravado = _discos()
    linhas, ssd_dev = [], None
    for d in lsblk():
        if d.get("type") != "disk" or d["name"].startswith("zram"):
            continue
        nome, tam = d["name"], int(d.get("size") or 0) / 1e9
        modelo = (d.get("model") or "").strip() or "eMMC interno"
        filhos = d.get("children") or []
        pts = [(c.get("mountpoint"), c.get("label")) for c in filhos if c.get("mountpoint")]
        papeis, uso = [], ""
        for mp, lab in pts:
            if mp and mp != "[SWAP]":
                papeis.append(f"<b>{esc(mp)}</b> — {esc(PAPEL.get(mp, lab or ''))}")
        if any(c.get("label") == "SSD" for c in filhos):
            ssd_dev = nome
        for c in filhos:
            if c.get("mountpoint") == "[SWAP]":
                papeis.append("swap de emergência")
        mp_main = next((mp for mp, _ in pts if mp in PAPEL and mp != "/boot/efi"), None)
        if mp_main:
            try:
                u = shutil.disk_usage(mp_main)
                uso = f"{u.used / 1e9:.1f} / {u.total / 1e9:.0f} GB" + barra(u.used, u.total)
            except Exception:  # noqa: BLE001
                uso = "?"
        r, w = io_atual.get(nome, (0.0, 0.0))
        ativo = ok("em uso agora") if (r + w) > 0.2 else '<span class="peq">ocioso</span>'
        gravado = total_gravado.get(nome, (0, 0))[1] / 1e6
        linhas.append([f"<b>{esc(modelo)}</b><br><span class='peq'>{tam:.0f} GB · {esc(usb_vel(nome) if d.get('tran') == 'usb' else 'interno')}</span>",
                       "<br>".join(papeis) or "<span class='peq'>sem uso</span>", uso,
                       f"{ativo}<br><span class='peq'>lê {r:.1f} · grava {w:.1f} MB/s</span>{spark(io_serie.get(nome, [])[-90:])}",
                       f"{gravado:,.0f} MB".replace(",", ".")])
    extra = ""
    if ssd_dev:
        s = smart_ssd(ssd_dev)
        if s.get("temp") is not None:
            extra = (f"<p class='peq'>SSD: {s['temp']} °C · desgaste {s['uso']}% (já passou do previsto, por isso há cópia) · reserva {s['reserva']}% · "
                     f"erros de dados {s['erros']}</p>")
    failover = '<p class="ruim">ATENÇÃO: robô rodando pela CÓPIA (SSD fora do ar)</p>' if (DATA / "FAILOVER_CACHE").exists() else ""
    emmc = ""
    for f in glob.glob("/sys/class/mmc_host/mmc0/mmc0:*/life_time"):
        try:
            a, b = Path(f).read_text().split()
            emmc = f"<p class='peq'>Disco interno (eMMC): vida usada {int(a, 16) * 10 - 10}–{int(a, 16) * 10}% (zona normal)</p>"
        except Exception:  # noqa: BLE001
            pass
    return card("Discos e uso (qual está trabalhando)", failover + tabela(linhas, ["Disco", "Papel", "Espaço", "Atividade (último min)", "Gravado desde o boot"]) + extra + emmc)


# ---------------------------------------------------------------- sistema
def sec_sistema():
    with _lock:
        h = list(HIST)
    cpu_ser = [x[1] for x in h]
    cpu_agora = sum(cpu_ser[-6:]) / len(cpu_ser[-6:]) if cpu_ser else 0.0
    cpu_5 = sum(x[1] for x in h if x[0] > time.time() - 300) / max(1, len([x for x in h if x[0] > time.time() - 300]))
    mem = {}
    for l in Path("/proc/meminfo").read_text().splitlines():
        k, v = l.split(":")
        mem[k] = int(v.split()[0]) // 1024
    usada = mem["MemTotal"] - mem["MemAvailable"]
    ram_ser = [x[2] for x in h]
    swaps = []
    for l in Path("/proc/swaps").read_text().splitlines()[1:]:
        f = l.split()
        nome = "zram (memória comprimida)" if "zram" in f[0] else "SSD (emergência)"
        swaps.append(f"{nome}: {int(f[3]) // 1024} MB usados de {int(f[2]) // 1024} MB")
    zr = ""
    try:
        mm = Path("/sys/block/zram0/mm_stat").read_text().split()
        if int(mm[1]):
            zr = f" · compressão {int(mm[0]) / int(mm[1]):.1f}x"
    except Exception:  # noqa: BLE001
        pass
    temps = []
    for f in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            temps.append(int(Path(f).read_text()) / 1000)
        except Exception:  # noqa: BLE001
            pass
    up = float(Path("/proc/uptime").read_text().split()[0])
    load = Path("/proc/loadavg").read_text().split()[:3]
    nproc = os.cpu_count() or 1
    linhas = [
        ["Processador", f"{cpu_agora:.0f}% agora · {cpu_5:.0f}% média 5 min · {nproc} núcleos · carga {' '.join(load)}" + spark(cpu_ser, 100)],
        ["Memória RAM", f"{usada} MB usados de {mem['MemTotal']} MB · <b>{mem['MemAvailable']} MB disponíveis</b>" + barra(usada, mem["MemTotal"]) + spark(ram_ser, mem["MemTotal"])],
        ["Swap", esc(" · ".join(swaps)) + esc(zr)],
        ["Temperatura do processador", f"{max(temps):.0f} °C" if temps else "—"],
        ["Ligado há", f"{int(up // 86400)}d {int(up % 86400 // 3600)}h {int(up % 3600 // 60)}min"],
    ]
    # memoria por servico
    sv = []
    for s in ("bot", "linkgen", "wa", "tela", "status"):
        try:
            mb = int(Path(f"/sys/fs/cgroup/system.slice/promobot-{s}.service/memory.current").read_text()) // 1048576
        except Exception:  # noqa: BLE001
            mb = None
        st = sh(["systemctl", "is-active", f"promobot-{s}"])
        sv.append([esc(s), ok(st, st == "active"), f"{mb} MB" if mb is not None else "—"])
    sv.append(["fila de Reels (timer)", ok(sh(["systemctl", "is-active", "promobot-fila-reels.timer"]), True), "—"])
    # programas que mais usam memoria (agrupados)
    grupos = collections.defaultdict(lambda: [0, 0.0])
    for l in sh(["ps", "-eo", "rss,pcpu,comm"]).splitlines()[1:]:
        f = l.split(None, 2)
        if len(f) == 3:
            grupos[f[2]][0] += int(f[0]) // 1024
            grupos[f[2]][1] += float(f[1])
    top = sorted(grupos.items(), key=lambda kv: -kv[1][0])[:6]
    tp = [[esc(n), f"{v[0]} MB", f"{v[1]:.0f}%"] for n, v in top]
    return (card("Sistema do Wyse", tabela(linhas)) + card("Serviços do robô", tabela(sv, ["Serviço", "Estado", "Memória"]))
            + card("Programas que mais usam memória", tabela(tp, ["Programa", "Memória", "CPU"])))


# ---------------------------------------------------------------- pagina
def montar():
    agora = datetime.now(BRT)
    ini_utc = agora.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    partes = []
    por_canal = dict(q("select canal, count(*) from offers where status='posted' and posted_at >= ? group by canal", (ini_utc,)))
    fila = dict(q("select canal, count(*) from offers where status='new' group by canal"))
    linhas = []
    for canal, nome in (("tech", "Tecnologia"), ("lar", "Casa")):
        n = por_canal.get(canal, 0)
        linhas.append([esc(nome), f"<b>{n}</b> / {LIMITE}" + barra(n, LIMITE), fila.get(canal, 0)])
    partes.append(card("Posts de hoje", tabela(linhas, ["Grupo", "Postados", "Na fila"])))
    lojas = q("select source, count(*) from offers where status='posted' and posted_at >= ? group by source order by 2 desc", (ini_utc,))
    partes.append(card("Postados hoje por loja", tabela([[esc(s), n] for s, n in lojas]) if lojas else "<p>nada ainda</p>"))
    fontes = []
    for src, last_ok, falhas, bloq, erro in q("select source, last_ok, consecutive_failures, blocked_until, last_error from source_health order by source"):
        if src == "publicacao":
            continue
        quando = brt(last_ok) if last_ok else "—"
        if falhas and falhas > 0:
            estado, det = ok("com erro", False), esc((erro or "")[:90])
        else:
            estado, det = ok("ok"), '<span class="peq">funcionando</span>'
        fontes.append([esc(src), estado, quando, det])
    partes.append(card("Fontes de ofertas (coleta)", tabela(fontes, ["Fonte", "Estado", "Última coleta ok", "Detalhe"])))
    partes.append(sec_sistema())
    partes.append(sec_discos())
    ult = q("select posted_at, source, canal, substr(coalesce(post_title,title),1,58), price from offers where status='posted' order by posted_at desc limit 10")
    partes.append(card("Últimos posts", tabela([[brt(a), esc(b), esc(c), esc(d), f"R$ {p:.2f}".replace(".", ",") if p else ""] for a, b, c, d, p in ult])))
    reels = []
    if FILA.exists():
        for d in sorted(FILA.iterdir()):
            try:
                m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                reels.append((m.get("quando") or "", m.get("id", d.name), m.get("tipo", ""), "sim" if m.get("aprovado") else "não"))
            except Exception:  # noqa: BLE001
                continue
    reels.sort()
    linhas = []
    for quando, rid, tipo, ap in reels:
        try:
            qd = datetime.fromisoformat(quando).astimezone(BRT).strftime("%d/%m %H:%M")
        except Exception:  # noqa: BLE001
            qd = quando
        linhas.append([esc(qd), esc(rid), esc(tipo), esc(ap)])
    partes.append(card("Reels na fila", tabela(linhas, ["Quando", "Reel", "Tipo", "Aprovado"]) if linhas else "<p>fila vazia</p>"))
    try:
        linhas_a = (DATA / "alertas.log").read_text(encoding="utf-8").strip().splitlines()[-8:]
        al = []
        for l in reversed(linhas_a):
            try:
                j = json.loads(l.rstrip(","))
                al.append([esc(str(j.get("quando", ""))[5:16].replace("T", " ")), esc(str(j.get("msg", ""))[:140])])
            except Exception:  # noqa: BLE001
                continue
        partes.append(card("Alertas recentes", tabela(al, ["Quando", "Mensagem"]) if al else "<p>nenhum</p>"))
    except Exception:  # noqa: BLE001
        pass

    css = """:root{--bg:#f6f7f9;--fg:#15171a;--card:#fff;--mut:#6b7280;--ok:#1a7f37;--ruim:#c62828;--ac:#ff6a00;--bd:#e5e7eb}
@media(prefers-color-scheme:dark){:root{--bg:#0e1013;--fg:#e8eaed;--card:#171a1f;--mut:#9aa0a6;--ok:#4cc16b;--ruim:#ff6b6b;--bd:#2a2f36}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif;padding:16px}
h1{font-size:20px;margin:0 0 4px}h1 span{color:var(--ac)}.sub{color:var(--mut);margin:0 0 14px;font-size:13px}
section{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:12px 14px;margin:0 0 12px;overflow-x:auto}
h2{font-size:14px;margin:0 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:5px 6px;border-bottom:1px solid var(--bd);vertical-align:top}th{color:var(--mut);font-weight:600;font-size:12px}
.ok{color:var(--ok);font-weight:600}.ruim{color:var(--ruim);font-weight:700}.peq{color:var(--mut);font-size:12px;margin:8px 0 0}td .peq{margin:0}
.barra{height:6px;background:var(--bd);border-radius:3px;margin-top:3px;min-width:70px}.barra div{height:6px;background:var(--ac);border-radius:3px}
.spark{display:block;margin-top:3px;max-width:100%}
@media(min-width:900px){body{max-width:1000px;margin:0 auto}}"""
    cab = (f'<h1>🔨 Tech<span>Hammer</span> — status do robô e do Wyse</h1><p class="sub">Atualizado {agora.strftime("%d/%m %H:%M:%S")} (Brasília) · '
           'somente leitura · atualiza sozinho a cada 30 s · gráficos = últimos 30 min</p>')
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="refresh" content="30"><title>Status TechHammer</title><style>' + css + '</style></head><body>' + cab + "".join(partes) + "</body></html>")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/status"):
            self.send_error(404)
            return
        if time.time() - _cache["t"] > 15:
            try:
                _cache["html"] = montar()
            except Exception as e:  # noqa: BLE001
                _cache["html"] = f"<pre>erro ao montar a pagina: {esc(e)}</pre>"
            _cache["t"] = time.time()
        b = _cache["html"].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):  # sem log de acesso
        pass


if __name__ == "__main__":
    threading.Thread(target=amostrar, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8088), H).serve_forever()
