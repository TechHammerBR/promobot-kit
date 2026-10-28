# PromoBot Kit — instruções para o Claude Code

Este arquivo é lido automaticamente pelo Claude Code quando você abre esta pasta. Ele descreve o projeto, as regras de trabalho e onde achar cada coisa.

## Conceito
Sistema que **monitora, coleta, filtra, enriquece e publica automaticamente** ofertas e cupons de e-commerce em canais de público (WhatsApp primeiro; Telegram e redes sociais opcionais).
- **Monetização (afiliado):** Mercado Livre, Shopee e AliExpress (e KaBuM via Awin). Todo link dessas lojas é convertido para o link de afiliado **do dono do robô** ANTES de publicar.
- **Atração (curadoria):** fontes de apoio (agregadores) só para manter o grupo movimentado, sem comissão.
- Arquitetura pensada para ser **leve** (roda num computador de 2 GB de RAM), **robusta** (se cai, volta sozinho) e **fácil de fazer backup**.

## Como trabalhar com o dono do robô
- O dono pode não ser técnico. **Explique em português simples, passo a passo**, e faça você mesmo tudo que der.
- Autonomia alta: só consulte o dono para **credenciais**, **decisões de escopo** e **ações destrutivas** (apagar dados, mexer em firewall/SSH, reinstalar, mudar contas).
- **Nunca** peça nem imprima segredos no chat. Credenciais vão no `.env` (nunca versionado) — use os scripts `src/ferramentas/gravar_*.sh`, que leem a chave sem eco.
- **Nunca** coloque segredos, IDs pessoais, telefones ou links de convite no código ou no Git.
- Antes de publicar algo novo (tipo de post, rede, formato) mostre uma **prévia em texto** e espere o OK.

## Regras do projeto (não negociáveis)
1. **Não burlar captcha nem anti-bot.** Se aparecer, o robô pausa a fonte e o dono resolve à mão.
2. Preferir **APIs oficiais e feeds** a raspagem de página.
3. **Respeitar os termos dos programas de afiliado.** Ex.: KaBuM/Samsung (Awin) cancelam comissão de venda com cupom que não veio da Awin → o robô nunca publica cupom de terceiros nessas lojas.
4. **Transparência de publicidade:** todo post de oferta leva `#Anuncio` (configurável).
5. **Foto só do próprio anúncio** (ou da página da loja). Nunca buscar imagem em outro lugar.
6. **Só afirmar fatos que o robô sabe** (desconto calculado, menor preço do histórico, cupom). Sem "últimas unidades", sem urgência inventada, sem prometer resultado.
7. O WhatsApp usa um conector **não oficial** (Baileys): existe risco de bloqueio. Mantém ritmo humano e teto diário. Leia `docs/12-riscos-e-termos.md`.
8. Falha de uma fonte **nunca derruba as outras**: HTTP com retry exponencial; 403/429/captcha → `BlockedError` → fonte pausada com recuo (30 min, 1 h, 2 h… até 12 h).

## Stack
Python 3.12+, httpx + tenacity (retry), selectolax (parsing), Pydantic v2, SQLAlchemy 2, APScheduler, structlog (logs JSON). Banco: SQLite (leve) ou PostgreSQL. Conector WhatsApp: Node 20 + Baileys. Navegador de afiliado: Playwright + Chromium em tela virtual (Xvfb).
Sem Celery/Redis de propósito (simplicidade). Adicionar só se o volume exigir.

## Estrutura
```text
src/app/config.py        todas as configurações (pydantic-settings, lê o .env)
src/app/main.py          agenda (APScheduler): coleta, publicação, cupons, conteúdo, relatórios
src/app/pipeline.py      coletar → avaliar → afiliar → salvar → publicar; saúde por fonte
src/app/engine.py        regras: preço válido, palavras proibidas, desconto, repetição, score, canal tech/casa
src/app/templates.py     texto dos posts (WhatsApp/Telegram): título com selo, preço, loja, cupom, link
src/app/publisher.py     envio (WhatsApp, Telegram) com retry; modo simulação em data/outbox.log
src/app/affiliate.py     limpa afiliados de terceiros e gera o link do dono
src/app/collectors/      um coletor por fonte (registrar em __init__.py)
src/app/photocheck.py    avalia a foto por medidas (sem IA)
src/app/coupon_codes.py  cupons com código e a sugestão do cupom certo para cada oferta
src/app/fila_reels.py    fila de vídeos prontos (feitos no PC) entregues na hora marcada
src/app/catchup.py       agenda única de conteúdo + recuperação de horários perdidos
src/app/ctl.py           controle por linha de comando (status, pausar, postar, desconto…)
src/wa/                  conector do WhatsApp (só envia)
src/linkgen/             navegador logado (gera meli.la, cupons)
```
Mapa completo dos módulos: `docs/referencia/modulos.md`. Todas as configurações: `docs/referencia/configuracoes.md`.

## Comandos úteis
```bash
cd /opt/promobot
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl status        # estado (leitura)
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl diag          # por que não está postando
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl alertas 20    # últimos alertas
PYTHONPATH=/opt/promobot venv/bin/python -m pytest -q tests       # testes
sudo systemctl restart promobot-bot                                 # reiniciar o robô
journalctl -u promobot-bot -f                                       # logs ao vivo
```
Atenção: `ctl postar`, `ctl cupons`, `ctl pausar`… são **ações** (mudam o que vai ao ar). Para só olhar use `status`, `diag`, `alertas`, `fila`.

## Ao começar uma sessão
1. Rode `ctl status` e `ctl alertas 20`.
2. Leia `docs/16-decisoes-e-historia.md` (o que foi decidido e por quê).
3. Se for mexer em código: rode os testes antes e depois. Faça **backup do arquivo** antes de alterar em produção.
4. Anote decisões novas em `docs/16-decisoes-e-historia.md`.

## Armadilhas conhecidas
- **Barras invertidas em heredoc/`bash -c`** são comidas: para patches com regex, escreva o script num arquivo e execute; depois valide com `grep` e `py_compile`.
- Alguns testes leem o `.env` real (ex.: intervalos) e falham se você mudou a configuração: é esperado.
- Reiniciar o robô é seguro (o guardião e o `catchup` retomam o que faltou).
- O navegador do ML (`linkgen`) perde a sessão se o Chromium reiniciar: o login é refeito por túnel SSH + VNC (`docs/05-afiliados.md`).
