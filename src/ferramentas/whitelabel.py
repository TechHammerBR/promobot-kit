"""White-label: troca a marca do autor pela SUA marca em todos os arquivos de texto do projeto.

Uso (na raiz do repositorio):
  python src/ferramentas/whitelabel.py --listar                       # mostra onde a marca do autor aparece (nao altera nada)
  python src/ferramentas/whitelabel.py --config brand.json            # SIMULA: mostra o que mudaria
  python src/ferramentas/whitelabel.py --config brand.json --aplicar  # aplica (faca commit antes: git diff mostra tudo)

brand.json = {"substituicoes": {"TechHammer": "Sua Marca", "techhammer": "suamarca", "@techhammer.br": "@seu_instagram", ...}}
As trocas rodam das mais LONGAS para as mais curtas (para "@techhammer.br" ganhar de "techhammer"). Ignora .git, node_modules, data, binarios.
Depois leia docs/13-white-label.md: tem itens que nao se resolvem com troca de texto (logos, servicos da loja, cores, textos de CTA)."""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
EXT = {".py", ".md", ".txt", ".sh", ".mjs", ".js", ".json", ".service", ".example", ".yml", ".yaml", ".env"}
PULAR = {".git", "node_modules", "data", "__pycache__", "venv", ".venv"}
MARCA_AUTOR = ["@techhammer.br", "TechHammer", "TECHHAMMER", "techhammer", "Tech Hammer", "Zona Sul"]


def arquivos():
    for f in RAIZ.rglob("*"):
        if f.is_file() and not (set(f.relative_to(RAIZ).parts) & PULAR) and (f.suffix.lower() in EXT or f.name.startswith(".env")):
            yield f


def listar() -> None:
    total = 0
    for f in arquivos():
        t = f.read_text(encoding="utf-8", errors="ignore")
        achados = {m: t.count(m) for m in MARCA_AUTOR if m in t}
        if achados:
            total += sum(achados.values())
            print(f"{f.relative_to(RAIZ)}: {achados}")
    print(f"\n{total} ocorrencias. Troque com --config brand.json.")


def trocar(config: Path, aplicar: bool) -> None:
    pares = json.loads(config.read_text(encoding="utf-8"))["substituicoes"]
    ordem = sorted(pares.items(), key=lambda kv: -len(kv[0]))
    mudou = 0
    for f in arquivos():
        if f == Path(__file__).resolve():
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        novo, n = t, 0
        for velho, nov in ordem:
            c = novo.count(velho)
            if c:
                novo = novo.replace(velho, nov)
                n += c
        if n:
            mudou += n
            print(f"{'APLICADO' if aplicar else 'mudaria '} {f.relative_to(RAIZ)}: {n}")
            if aplicar:
                f.write_text(novo, encoding="utf-8")
    print(f"\n{mudou} trocas {'aplicadas' if aplicar else '(simulacao: nada foi alterado)'}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--config", type=Path)
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.listar:
        listar()
    elif a.config:
        trocar(a.config, a.aplicar)
    else:
        ap.print_help()
        sys.exit(1)
