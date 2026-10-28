# Mapa dos modulos (`src/app`)

Resumo de uma linha de cada arquivo, tirado do cabecalho dele.

| Arquivo | Para que serve |
|---|---|
| `affiliate.py` | Limpeza de links e conversão para links de afiliado do dono. |
| `ai.py` | IA local (Ollama, qwen3:4b): título curto do post. Se falhar, usa o título original. |
| `aliapi.py` | AliExpress — API oficial de afiliados (Open Platform, categoria "Affiliates API"). |
| `alicheck.py` | Validação ANTI-GOLPE das ofertas do AliExpress (pedido do dono, 07/10/2026: "sempre valide a qualidade, configuração e afins"). |
| `awin.py` | Awin (rede de afiliados): link comissionado das lojas em que o dono foi APROVADO (13/10/2026: KaBuM pendente). |
| `catchup.py` | Recuperação AUTOMÁTICA de posts agendados que perderam o horário (servidor desligado, reinício do robô, falta de luz...). |
| `config.py` | (sem descricao) |
| `content.py` | Conteúdo da LOJA TechHammer para o feed (06/10) — o feed é vitrine de manutenção/montagem, não só ofertas. |
| `control.py` | Painel de controle compartilhado entre o bot e o serviço `ops` (ações seguras da IA local). |
| `convites.py` | Convite diário dos contatos do dono para os grupos (decisão do dono em 14/10/2026, ciente do risco de bloqueio do número). |
| `coupon_codes.py` | Cupons COM CÓDIGO (ex.: CARRINHOML, SITETODO0310), lidos do Pelando (página pública de cupons de cada loja). |
| `coupons.py` | Cupons gerais do Mercado Livre (página /cupons, lida pelo navegador logado — serviço linkgen). |
| `ctl.py` | Controle do robô pela linha de comando — uso do Claude/administrador (sem servidor HTTP e sem IA de conversa). |
| `db.py` | (sem descricao) |
| `diagnose.py` | Diagnóstico em linguagem simples: POR QUE o robô não está postando e o que fazer (06/10). |
| `engine.py` | Motor de regras: decide se uma oferta deve ser publicada. |
| `estudio.py` | ESTÚDIO: posts de NOVIDADES de tecnologia/IA para o feed, escritos pela IA do PC do dono (14/10/2026). |
| `fila_reels.py` | Fila de Reels PRONTOS (15/10/2026, pedido do dono): o PC do dono FABRICA o vídeo (voz, trailers, IA local) e o Wyse só ENTREGA na hora marcada. |
| `game_reels.py` | Reels de JOGOS sem narração (06/10, pedido do dono). Formato de celular: trailer INTEIRO no centro + fundo desfocado. |
| `games.py` | Carrossel semanal "Promoções da semana em jogos" (pedido do dono 06/10) — Instagram + Página. |
| `gpu.py` | Coordena a GPU de 8 GB com o laboratório de voz (/opt/apps/voicelab). |
| `health.py` | Guardião: checa a saúde de tudo a cada 5 min (chamado por scripts/guardian.sh no host). |
| `log.py` | (sem descricao) |
| `main.py` | Ponto de entrada: `python -m app.main` (contínuo) ou `python -m app.main --once`. |
| `media.py` | Foto do post: baixa, normaliza (JPEG fundo branco) e VALIDA que é foto do produto. |
| `musica.py` | Música dos Reels com RODÍZIO: não repete as últimas faixas usadas por nenhum Reel/Story/carrossel e começa num ponto diferente da faixa. |
| `noticia_art.py` | Arte das NOVIDADES de tecnologia (14/10/2026): visual de canal de notícias feito só com Pillow (leve para o Wyse). |
| `photocheck.py` | Avaliador de foto SEM IA (robô leve): decide por medidas da própria imagem se ela é "foto de catálogo". |
| `pipeline.py` | Coleta (a cada COLLECT_INTERVAL_MIN) e publicação cadenciada (1 oferta por PUBLISH_INTERVAL_SEC). |
| `pricehist.py` | Histórico de preço por produto (13/10/2026) — detector de DESCONTO FALSO sem IA. |
| `prices.py` | Tabela de preços da loja (carrossel) — editável pelo WhatsApp do dono, sem precisar do Claude. |
| `publisher.py` | Envio para todos os canais configurados: Telegram (Bot API) e WhatsApp (conector próprio `wa`). |
| `reels.py` | Reels automáticos (06/10) — o formato que mais traz seguidores novos. Instagram (Reels) + Página (vídeo) + Threads. |
| `reels2.py` | Reels no estilo do @quantoquevaicustar (referência do dono, 08/10/2026): narração CONTÍNUA com a voz do dono, legendas palavra a palavra, |
| `report.py` | Relatório diário (13/10/2026): posts por loja e por fonte, quantos com comissão, vendas/comissões da Shopee e da Awin. |
| `revisao_ig.py` | Revisão semanal do Instagram (28/10/2026): lê os posts do @ pela Graph API (SÓ LEITURA) e diz o que funcionou e o que repetir ou parar. |
| `schemas.py` | (sem descricao) |
| `semanal.py` | Carrosséis semanais com DADOS PRÓPRIOS do robô (14/10/2026, pedido do dono; sem IA, cabem no Wyse): |
| `slideshow.py` | Slides (imagens) -> REEL em vídeo com música de fundo (15/10/2026, ideia do dono: "reel propaga mais que foto"). |
| `social.py` | Redes da Meta (06/10): Página TechHammer (Facebook) + Instagram @techhammer.br via Graph API. |
| `social_art.py` | Artes para redes sociais (Stories 1080x1920 e feed 1080x1350) — visual minimalista/premium. |
| `status_posts.py` | Status (stories) do WhatsApp, recorrente e automático — sem gastar créditos do Claude. |
| `storephoto.py` | Fotos alternativas direto da página da loja (og:image, JSON-LD, galeria da Amazon). |
| `story_video.py` | Stories em VÍDEO (até 60 s, 9:16): Instagram (media_type=STORIES, upload direto) + Página do Facebook (video_stories, 3 fases). |
| `templates.py` | Texto dos posts (padrão dos canais de referência do dono: GPCR Promo, GalgoPromo, Ofertas Adrenaline). |
| `threads.py` | Threads @techhammer.br (06/10) — no Threads os LINKS SÃO CLICÁVEIS (diferente do Instagram). |
| `titles.py` | Título, marca e "produto parecido" SEM IA (robô leve do Wyse, 13/10/2026 — pedido do dono). |
| `trending.py` | Produtos quentes do dia (23/10/2026, pedido do dono: 'grupo de ofertas mais interessante'). |
| `voz.py` | Narração com a VOZ DO DONO nos vídeos: chama o serviço de voz do servidor (/opt/apps/voicelab, http://voice:8300). |
| `watchdog.py` | Vigia do WhatsApp: avisa o dono (alert → Telegram admin) quando a conexão cai e quando volta. |
| `youtube.py` | YouTube Shorts (22/10/2026, pedido do dono: "sempre traga conteúdo também no YouTube"). Upload resumable com OAuth do dono (canal Tech Hammer). |
| `collectors/aliexpress.py` | AliExpress — ofertas de tecnologia por palavra-chave (rodízio de ALI_KEYWORDS_PER_CYCLE por coleta), em reais. |
| `collectors/base.py` | Interface comum dos coletores, com retry e detecção de bloqueio. |
| `collectors/bonus.py` | Fontes bônus (atração): agregadores usados para DESCOBRIR ofertas. |
| `collectors/canais.py` | Canais públicos de promoção do Telegram como FONTE (pedido do dono, 13/10/2026). |
| `collectors/mercadolivre.py` | Mercado Livre — página pública de ofertas (principal, monetizável). |
| `collectors/pelando.py` | Pelando — ofertas votadas pela comunidade (página pública). |
| `collectors/shopee.py` | Shopee — API oficial de Afiliados (GraphQL). O site bloqueia leitura direta; a API já devolve o link com comissão (offerLink). |

## Outros componentes

| Pasta | O que e |
|---|---|
| `src/wa/` | Conector do WhatsApp (Node + Baileys, **nao oficial**): so ENVIA mensagens. |
| `src/linkgen/` | Navegador (Playwright) logado nas contas de afiliado: gera links meli.la do Mercado Livre e cupons. |
| `src/ferramentas/` | Scripts de operacao (backup, espelho, vigias de disco/memoria, status web). |
| `src/tests/` | Testes automaticos (pytest). |
| `deploy/systemd/` | Unidades do systemd que mantem tudo no ar. |
