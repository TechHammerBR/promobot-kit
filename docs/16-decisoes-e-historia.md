# 16 — Decisões e história do projeto

Registro do **porquê** de cada escolha (útil para o Claude e para você não repetir erros). Datas de 2026. Acrescente suas decisões no fim.

## Princípios que o autor fixou
- **Tudo roda sozinho no servidor.** Nada em tempo de execução depende de IA paga nem do Claude: coleta, regras, foto, posts, backup e vigilância são determinísticos. O Claude constrói e mantém.
- **Sem chatbot, sem notificações ao dono** (07/10): alertas só em arquivo (`data/alertas.log`); quem opera usa o `ctl` (e o Claude lê os alertas).
- **Preferir API oficial; nunca burlar captcha** (princípio desde o início).
- **Aprovar antes de postar** qualquer tipo novo de conteúdo.
- **Simplicidade:** sem Celery/Redis/Docker no servidor pequeno.

## Linha do tempo (resumida)
| Data | Decisão / evento | Por quê |
|---|---|---|
| 01–02/10 | MVP de coleta + publicação; servidor Linux com Docker; WhatsApp + Telegram | começar simples |
| 02/10 | Link do ML por **navegador logado** (`meli.la`) | o ML não tem API de afiliado; o link antigo não mostra a indicação |
| 02/10 | Publicação **1 oferta por vez**, ritmo aleatório, horário 6h–0h | parecer humano, evitar bloqueio |
| 02–03/10 | Foco em **tecnologia**; IA local julgava foto/título | dono queria nicho forte |
| 05–06/10 | AliExpress via Portals; Pelando como fonte | volume de ofertas |
| 06/10 | Redes sociais (Meta, Threads) por API oficial; Reels de jogos | audiência |
| 07/10 | **Sem chatbot/notificações**; servidor desligava à noite (energia) → backup "catch-up" | decisão do dono |
| 08/10 | **GPU morreu** → tudo sem IA de visão; validação de foto por medidas | robustez |
| 13/10 | Robô **leve** (Wyse 3040, sem Docker, sem IA): `photocheck.py` por medidas; calibrado com 144 fotos | custo e simplicidade |
| 13/10 | Awin/KaBuM: **nunca** cupom de terceiros | regra do programa (comissão cancelada) |
| 14/10 | Segundo canal: **casa** (comunidade WhatsApp) | mais volume |
| 15/10 | **Fila de Reels prontos** (PC fabrica, Wyse entrega) | servidor pequeno não faz vídeo |
| 22/10 | Telegram **sem ofertas** (canal pequeno); Shorts automáticos no YouTube | foco |
| 23/10 | Comparação com 8 canais de referência: mais cupons, hardware, ticket alto; `trending.py`; repetição só com queda ≥ 30% | qualidade |
| 25/10 | **Mix de lojas:** ML ≥ 50%, AliExpress ≤ 15%, resto Shopee; lojas sem afiliado não saem | maximizar comissão |
| 27/10 | Queda de energia → o ML pediu reCAPTCHA; não burlado, liberou sozinho | regra "nunca burlar" |
| 28/10 | **Foto:** regra "sem produto em destaque" (textura de madeira passou); **chamada v2** (selo -N% no título, sem repetir %, linha da loja); **cupom relevante** (VALETECH para tech, sem "Meli+"/"carro"); **Shorts agendados** na plataforma | qualidade |
| 28/10 | **Sem dicas/conteúdo educativo nos grupos de WhatsApp**: só melhorar a chamada | decisão do dono |
| 28/10 | **Este kit (v0.1 → v0.4 no mesmo dia)**, distribuído para testes (sem venda por enquanto) | testar com um grupo pequeno antes de qualquer venda |
| 28/10 | **Teste de instalação em VM** (mínimo do Wyse): achou 9 problemas do kit (padrões herdados do Docker, scripts com caminhos do autor, permissão +x, API do WhatsApp em todas as interfaces, `diag` com falso alarme, 2 testes-bomba-relógio…), todos corrigidos | ver `18-teste-de-instalacao.md` |

## Lições técnicas (para não repetir)
- **Barras invertidas em heredoc/`bash -c`**: o shell come as barras (`\b` vira backspace invisível). Para patches com regex, **escreva o script num arquivo** e rode; valide com `grep -c $'\x08'` e `py_compile`.
- **Reiniciar o Chromium** derruba o login do ML: o `linkgen` salva/restaura cookies (`session_cookies.json`), mas pode precisar de login/captcha.
- **A API do YouTube não edita nem apaga** com os escopos de upload: planeje (agende só perto da data).
- **Instagram exige upload direto** de vídeo (`resumable`); URL dá erro.
- **Contagem de "cupons nas ofertas"** deve incluir a **sugestão** (`cupom_dica`), não só o campo `coupon` do banco: a primeira medida (1,3%) estava errada; a real era ~64%.
- **Alguns testes leem o `.env` real**; falham se o ritmo foi alterado (esperado).
- **Estimar antes de medir engana:** sempre meça com dados reais das últimas 24 h antes de concluir.

## Como acrescentar uma decisão
Uma linha na tabela (data, decisão, por quê). Se for regra do negócio, atualize também `10-regras-de-negocio.md`.
