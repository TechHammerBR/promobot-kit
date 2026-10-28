# 02 — Arquitetura

## Visão de blocos
```text
                    ┌──────────────────────────── servidor pequeno (Debian) ───────────────────────────┐
  Internet          │                                                                                  │
  (lojas, APIs) ◄───┤  promobot-bot  (Python, APScheduler)  ──► SQLite (data/promobot.db)             │
                    │     │ coleta · regras · fila · publica · cupons · conteúdo · relatórios          │
                    │     ├──► promobot-wa       (Node/Baileys)  ──► WhatsApp  (só envia)              │
                    │     ├──► promobot-linkgen  (Playwright)    ──► Mercado Livre logado (meli.la)  │
                    │     │         └─ promobot-tela (Xvfb) [+ promobot-vnc só no login]               │
                    │     ├──► APIs: Telegram, Shopee, AliExpress, Awin, Meta, Threads, YouTube        │
                    │     └──► fila de Reels prontos (pasta) ◄── PC potente (vídeos) [opcional]        │
                    │  promobot-status (página local, somente leitura, porta 8088)                     │
                    │  cron: vigias, manutenção 04:20, backup 03:40, espelho, imagem semanal           │
                    └──────────────────────────────────────────────────────────────────────────────────┘
```

## Serviços (systemd)
| Serviço | O que faz | Limite de memória (exemplo) |
|---|---|---|
| `promobot-bot` | o robô: coleta, regras, fila, publicação, agenda de conteúdo | alto 350 MB / máx. 500 MB |
| `promobot-wa` | conector do WhatsApp (porta 3000 só local) | 300 / 400 MB |
| `promobot-linkgen` | navegador logado que gera links de afiliado do ML (porta 8000 só local) | alto 1,1 GB |
| `promobot-tela` | tela virtual (Xvfb) para o navegador | 150 MB |
| `promobot-vnc` | ver a tela do navegador **só durante o login** (acesso por túnel SSH, expira em 2 h) | 200 MB |
| `promobot-status` | página de status local, somente leitura | 80 MB |
| `promobot-fila-reels` (timer a cada 5 min) | entrega os Reels prontos da fila na hora marcada | 450 MB |

Os arquivos `.service` estão em `deploy/systemd/`. Todos têm `Restart=always` e limite de memória: num equipamento de 2 GB isso evita que um serviço derrube os outros.

## Fluxo interno (código)
- `main.py` registra os jobs no APScheduler: `collect_all` (a cada 15 min), `publish_tick` (reagendado a cada post com intervalo aleatório), `control_watch` (30 s; lê `data/control.json` com pedidos do `ctl`), cupons (a cada 10 min e 6 h), `catchup.run/recover` (conteúdo agendado), relatórios (23:00 e 23:50).
- `pipeline.collect_all()` chama cada coletor registrado em `collectors/__init__.py`, passa pelo `engine.evaluate` e grava no banco.
- `pipeline.publish_next(canal)` escolhe a próxima oferta (`proximo_mix` aplica a proporção de lojas), gera o link (`_ensure_link`), valida a foto (`media.validate_photo` → `photocheck`), monta o texto (`templates.render`) e envia (`publisher.publish`).
- Falhas por fonte são registradas em `SourceHealth`; 3 seguidas geram alerta; bloqueio (403/429/captcha) pausa a fonte com recuo crescente.

## Banco de dados
SQLite por padrão (arquivo único, backup fácil); PostgreSQL opcional (`DATABASE_URL`). Tabelas principais (`db.py`):
| Tabela | Conteúdo |
|---|---|
| `Offer` | cada oferta: fonte, título, URLs, preço e preço antigo, cupom, pagamento, foto, `status` (`new`, `rejected`, `pending`, `posted`, `failed`), motivo, canal (`tech`/`lar`), datas |
| `SourceHealth` | saúde de cada fonte (falhas seguidas, pausa até quando) |
| `Coupon` | cupons com código por loja (código, título, mínimo, última vez visto) |
| histórico de preço | para detectar "menor preço em N dias" e desconto falso (`pricehist.py`) |

Estado auxiliar em `data/*.json` e arquivos pequenos (índices de rodízio de palavras-chave, último post de cupons, estado dos agendamentos `schedule_state.json`, `control.json`).

## Por que sem Docker, Celery ou Redis
- O equipamento mínimo (Wyse 3040) tem 4 núcleos a 1,44 GHz, 2 GB de RAM e 24 GB de armazenamento no total: cada camada a mais custa memória. `systemd` + `venv` resolvem.
- Se o volume crescer (vários clientes, milhares de ofertas por hora), `docker compose` + Postgres + uma fila são o próximo passo natural (ver `15-roadmap-e-ideias.md`).

## Ritmo e horários
- Horário ativo padrão: das 6h às 3h do dia seguinte (`ACTIVE_HOUR_START=6`, `ACTIVE_HOUR_END=27`); madrugada com ritmo mais lento (`NIGHT_*`).
- Intervalo entre posts **aleatório** (`INTERVAL_MIN/MAX`, `PEAK_INTERVAL_MIN/MAX` nos horários de pico) — parece humano e reduz risco de bloqueio.
- Teto diário (`DAILY_POST_LIMIT`, `LAR_DAILY_LIMIT`).

## Estrutura de pastas (no servidor)
```text
/opt/promobot/            código (esta pasta src/ copiada para cá)
  .env                    segredos e configurações (chmod 600)
  venv/                   ambiente Python
  data/                   banco, sessão do WhatsApp, estado, logs (NÃO versionar)
  wa/                     conector (node_modules instalados aqui)
/srv/backup/              backups (pendrive)  [ou backup-local no disco interno]
/srv/cache/               cache grande e fila de Reels (pendrive/SSD)
```
Os caminhos `/srv/backup` e `/srv/cache` são do ambiente do autor; troque por qualquer disco extra ou deixe tudo em `/opt/promobot/data`.
