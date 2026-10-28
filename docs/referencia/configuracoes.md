# Referencia de configuracoes

Gerado do codigo (`src/app/config.py`). Cada campo vira uma variavel de ambiente no `.env` em MAIUSCULAS (ex.: `daily_post_limit` -> `DAILY_POST_LIMIT`).
Valores longos (listas de palavras-chave) foram resumidos: veja o padrao completo em `config.py`.


## Regras gerais, ritmo e horarios

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `DATABASE_URL` | str | `(calculado)` | Banco: SQLite local; em produção troque por postgresql+psycopg://... |
| `MIN_DISCOUNT_PCT` | int | `30` | tecnologia (foco do canal) |
| `ABSURD_DISCOUNT_PCT` | int | `60` | fora de tecnologia: só oferta absurda, e a IA ainda avalia |
| `DEDUPE_HOURS` | int | `24` | fora de tecnologia: só oferta absurda, e a IA ainda avalia |
| `COLLECT_INTERVAL_MIN` | int | `15` |  |
| `MAX_POSTS_PER_CYCLE` | int | `10` | (legado) |
| `PUBLISH_INTERVAL_SEC` | int | `60` | (legado: substituído pelo intervalo variável abaixo) |
| `INTERVAL_MIN` | float | `10` | Ritmo humano no WhatsApp: intervalo aleatório (minutos), menor nos horários de pico |
| `INTERVAL_MAX` | float | `18` |  |
| `PEAK_INTERVAL_MIN` | float | `7` |  |
| `PEAK_INTERVAL_MAX` | float | `12` |  |
| `PEAK_HOURS` | str | `11-14,19-23` | faixas [início, fim) em horário de Brasília |
| `DAILY_POST_LIMIT` | int | `50` | teto de posts de oferta por dia (cupons não contam) |
| `LIMIT_RESET_AT` | str | `` | ISO; zera a contagem do dia a partir deste momento (ex.: liberar mais posts em dia de teste) |
| `REPEAT_MIN_DROP` | float | `0.3` | dentro de REPEAT_DAYS só repete se o preço novo for >= 30% menor que o da última vez (dono, 23/10) |
| `REPEAT_DAYS` | int | `3` | mesmo produto não volta antes disso |
| `QUEUE_MAX_HOURS` | int | `6` | oferta mais velha que isso na fila expira |
| `LINKGEN_URL` | str | `http://linkgen:8000` | oferta mais velha que isso na fila expira |
| `LINKGEN_ENABLED` | bool | `True` | navegador logado (ML: meli.la e cupons gerais). False no robô leve sem navegador |
| `SIMULATE_POSTS` | bool | `False` | corta peças avulsas/acessórios minúsculos (R$) |
| `GROUP_INVITE_LINK` | str | `` | ex.: link de convite do grupo/canal do WhatsApp |
| `GROUP_INVITE_LABEL` | str | `Grupo no WhatsApp` | ex.: link de convite do grupo/canal do WhatsApp |
| `POST_HASHTAG` | str | `#Anuncio` | quando existir o canal do Telegram |
| `COUPON_REFRESH_HOURS` | int | `6` |  |
| `CONTENT_ENABLED` | bool | `True` | agenda de conteúdo (stories, feed, educativo, jogos, reels). False no robô leve (só grupos) |
| `VISION_MODEL` | str | `qwen3-vl:8b-instruct` | valida se a foto é do produto (mesmo modelo: sem troca na GPU) |
| `STORE_WHATSAPP` | str | `` | numero da loja so com digitos (5511999999999): vira o link wa.me/ dos orcamentos |
| `CONVITE_ENABLED` | bool | `False` | grupos, 1 mensagem a cada 1,5–4 min, quem já está nos grupos é pulado; texto em app/assets/convite.txt. |
| `CONVITE_POR_DIA` | int | `50` |  |
| `CONVITE_HORA` | str | `10:30` |  |
| `ACTIVE_HOUR_START` | int | `6` | publica das 6h... |
| `ACTIVE_HOUR_END` | int | `27` | ...até as 3h do dia seguinte (acima de 24 = vira a noite; 24 = até meia-noite) |
| `NIGHT_HOURS` | str | `0-3` | madrugada: ritmo mais lento para não encher o grupo de notificações |
| `NIGHT_INTERVAL_MIN` | float | `20` | madrugada: ritmo mais lento para não encher o grupo de notificações |
| `NIGHT_INTERVAL_MAX` | float | `30` |  |
| `BOT_AI_NUM_GPU` | int | `0` | 08/10/2026: SEM GPU (a RTX 4060 morreu): IA só na CPU (foto ~40 s, curadoria ~14 s). Com placa nova: 99 = todas as camadas na GPU |
| `PRICE_HISTORY_MIN_DAYS` | int | `3` | dias de histórico antes de julgar |
| `PRICE_HISTORY_WINDOW_DAYS` | int | `30` | dias de histórico antes de julgar |
| `PRICE_DROP_PCT` | float | `5.0` | abaixo do menor preço já visto em pelo menos X% = "menor preço em N dias" |
| `OFFER_COUPON_HINT` | bool | `True` | sugere no post um cupom ativo da loja (ML/Shopee) ou autorizado pela Awin (KaBuM) |
| `NO_OUTSIDE_COUPON_HOSTS` | str | `kabum.com.br,samsung.com` | aprovações informadas à mão (o token descobre sozinho) |
| `CODE_POST_GAP_HOURS` | float | `3` | cupons com código (Pelando): no máx. 1 post a cada N horas, só se houver código novo |
| `COUPON_POST_HOUR` | int | `6` | post diário de cupons gerais |
| `BRAND_NAME` | str | `Ofertas Tech` | Identidade do canal (artes das redes sociais) |
| `BRAND_COLOR` | str | `#1E2A78` |  |
| `ACCENT_COLOR` | str | `#FF3D57` |  |
| `GAMES_DAY` | str | `thu` | oferta no feed só nesses dias (feed = vitrine da loja) |
| `EDU_DAY` | str | `tue` | carrossel educativo da loja (app/content.py) |
| `EDU_TIME` | str | `19:00` | carrossel educativo da loja (app/content.py) |
| `GAMES_TIME` | str | `13:00` | Epic libera grátis qui 12h |
| `GAMES2_DAY` | str | `mon` | 2ª edição: ofertas semanais da Steam começam na segunda |
| `GAMES2_TIME` | str | `19:00` | 2ª edição: ofertas semanais da Steam começam na segunda |
| `STATUS_ENABLED` | bool | `False` |  |
| `FEED_VENDAS_ENABLED` | bool | `False` | 14/10: oferta do dia, radar e top 5 fora do feed (dono: feed é conteúdo, venda vai p/ Stories) |
| `PEXELS_API_KEY` 🔒 | str | `` | foto livre de fundo da capa das novidades (opcional; sem chave = ícone da editoria) |
| `STATUS_TIMES` | str | `12:30,20:00` | alterna: 1º horário = divulgação do grupo, 2º = oferta do dia |
| `PRIORITY_KEYWORDS` | str | `notebook,computador,pc gamer,desktop,monitor,...` | foco do dono (03/10): computador, peças, periféricos, games e celular |
| `PRIORITY_BONUS` | int | `25` | tecnologia primeiro (pedido do dono)  # coleta de cupons gerais do ML  # true = publica em data/outbox.log mesmo sem Telegram |
| `BANNED_WORDS` | str | `recondicionado,usado,réplica` | tecnologia primeiro (pedido do dono)  # coleta de cupons gerais do ML  # true = publica em data/outbox.log mesmo sem Telegram |
| `REQUIRE_APPROVAL` | bool | `False` |  |

## Telegram

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` 🔒 | str | `` | Telegram (vazio = modo simulação, posts vão para data/outbox.log) |
| `TELEGRAM_CHANNEL_ID` 🔒 | str | `` |  |
| `TELEGRAM_POST_ENABLED` | bool | `True` | false = não posta ofertas no canal do Telegram (pedido do dono 22/10) |
| `TELEGRAM_ADMIN_CHAT_ID` 🔒 | str | `` | false = não posta ofertas no canal do Telegram (pedido do dono 22/10) |
| `TELEGRAM_INVITE_LINK` | str | `` | quando existir o canal do Telegram |

## Shopee (afiliado)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `SHOPEE_TRENDING_PER_CYCLE` | int | `3` | palavras 'quentes' (app/trending.py) buscadas na Shopee a cada ciclo |
| `SHOPEE_APP_ID` 🔒 | str | `` | Afiliados |
| `SHOPEE_SECRET` 🔒 | str | `` |  |
| `SHOPEE_KEYWORDS` | str | `mouse gamer redragon,teclado mecanico redrago...` |  |
| `SHOPEE_KEYWORDS_PER_CYCLE` | int | `3` | palavras por coleta (rodízio); a API permite 2000 chamadas/hora |
| `SHOPEE_LIMIT` | int | `30` | palavras por coleta (rodízio); a API permite 2000 chamadas/hora |
| `SHOPEE_MIN_PRICE` | float | `30.0` |  |
| `SHOPEE_MIN_RATING` | float | `4.7` |  |
| `SHOPEE_MIN_SOLD` | int | `20` |  |
| `SHOPEE_MALL_ONLY` | bool | `True` | só loja oficial (Shopee Mall): loja indicada ainda vendia Logitech G304 falso a R$ 58 |
| `SHOPEE_MAX_DISCOUNT` | int | `70` | desconto acima disso em marca famosa costuma ser falsificado |
| `SHOPEE_EVERY` | int | `3` | no máximo 1 Shopee a cada N posts (como o AliExpress) |
| `SHOPEE_COUPONS_ENABLED` | bool | `True` | cupons com código da Shopee (Pelando), igual ao do Mercado Livre |
| `SHOPEE_CODE_POST_GAP_HOURS` | float | `1` | cupom da Shopee esgota em ~1 h: avisa rápido |

## Pelando (fonte de apoio)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `PELANDO_EVERY` | int | `5` | Pelando no máx. 1 a cada N posts do canal (apoio; foco é Shopee/ML) |
| `PELANDO_ENABLED` | bool | `True` | ofertas votadas do Pelando (só AliExpress/ML) |
| `PELANDO_MIN_TEMP` | int | `100` | temperatura (votos) mínima |
| `PELANDO_BONUS_MIN_TEMP` | int | `100` | outras lojas (sem comissão, mantém o grupo movimentado): tecnologia votada |
| `PELANDO_BONUS_ANY_TEMP` | int | `400` | qualquer categoria se bombando (passa pela IA de curadoria) |
| `PELANDO_MAX_AGE_H` | int | `12` | 14/10: 48 h trazia preço que já tinha mudado na loja   # só ofertas postadas nas últimas N horas |
| `PELANDO_SEARCH_TERMS` | str | `ssd,ssd nvme,ssd externo,hd externo,placa de ...` | 14/10: 48 h trazia preço que já tinha mudado na loja   # só ofertas postadas nas últimas N horas |
| `PELANDO_SEARCH_PER_CYCLE` | int | `16` | termos buscados por coleta (rodízio): ~1 s cada |
| `PELANDO_SEARCH_MIN_TEMP` | int | `40` | na busca por palavra de tecnologia o voto mínimo é menor (a busca já filtra o assunto) |

## Mercado Livre (afiliado)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `ML_BONUS_MODE` | bool | `False` | com ML_PAUSED_UNTIL ativo: segue coletando ML e posta como BÔNUS (link limpo, sem comissão, sem abrir a página do produto) |
| `ML_PAUSED_UNTIL` | str | `` | AAAA-MM-DD: até esta data não coleta/posta ML (conta de afiliado suspensa) |
| `ML_TAG_TECH` | str | `` | etiqueta do afiliado ML por canal (Administrar etiquetas) |
| `ML_TAG_LAR` | str | `` | etiqueta do afiliado ML por canal (Administrar etiquetas) |

## Canais do Telegram (fonte de emergencia)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `TG_CHANNELS` | str | `` | canais publicos do Telegram lidos so como FONTE DE EMERGENCIA (t.me/s/<canal>, sem login); vazio = desligado |
| `TG_EMERGENCY_QUEUE` | int | `8` | só lê os canais se a fila tiver MENOS que isso (0 = nunca) |
| `TG_MAX_AGE_H` | int | `3` | oferta de canal vence rápido |
| `TG_MAX_LINKS_PER_CYCLE` | int | `25` | encurtadores abertos por coleta (1 por segundo) |
| `TG_TEMP` | int | `120` | peso no score (equivale a uma oferta morna do Pelando) |

## AliExpress (afiliado)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `ALI_ENABLED` | bool | `True` | na busca por palavra de tecnologia o voto mínimo é menor (a busca já filtra o assunto) |
| `ALI_EVERY` | int | `3` | no máximo 1 post do AliExpress a cada N (a nota dele é inflada pelo "preço antigo" e tomava a fila toda) |
| `ALI_APP_KEY` 🔒 | str | `` | API oficial de afiliados (app/aliapi.py). Com as chaves preenchidas o navegador (linkgen) não é usado para o AliExpress. |
| `ALI_APP_SECRET` 🔒 | str | `` |  |
| `ALI_TRACKING_ID` | str | `default` | Portals > Account > Tracking ID |
| `ALI_CATEGORY_IDS` | str | `7,44,509,502` | informática, eletrônicos, celulares, componentes (vazio = todas) |
| `ALI_KEYWORDS` | str | `gamesir controller,8bitdo controller,qcy earb...` | buscas por MARCA conhecida (13/10: a busca genérica trazia placa X99/memória/fonte sem procedência) |
| `ALI_KNOWN_BRANDS_ONLY` | bool | `True` | busca do AliExpress só publica marca da lista app/titles.MARCAS |
| `ALI_KEYWORDS_PER_CYCLE` | int | `5` | palavras buscadas por coleta (rodízio): ~1 s cada pela API (~25 s no Portals) |
| `ALI_MIN_SOLD` | int | `10` | mínimo de vendas para confiar no produto |
| `ALI_MIN_PRICE` | float | `40.0` | corta peças avulsas/acessórios minúsculos (R$) |

## Mix de lojas

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `MIX_ENABLED` | bool | `True` | dono 25/10/2026: Mercado Livre >= 50%, AliExpress <= 15%, resto Shopee; lojas sem afiliado nao saem (false = rodizio antigo) |
| `MIX_ML` | float | `0.5` | meta de Mercado Livre nos ultimos MIX_JANELA posts do canal |
| `MIX_ALI` | float | `0.15` | teto de AliExpress |
| `MIX_PISO_ML` | float | `0.3` | abaixo disso (tech) e sem oferta ML na fila, o grupo espera em vez de encher de Shopee/AliExpress |
| `MIX_PISO_ML_LAR` | float | `0.2` | idem na casa (o ML tem menos oferta de casa) |
| `MIX_JANELA` | int | `20` | idem na casa (o ML tem menos oferta de casa) |

## WhatsApp

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `WHATSAPP_GROUP_NAME` | str | `` | vazio = WhatsApp desligado |
| `WHATSAPP_NUMBER` | str | `` | número do robô (só dígitos, com 55) para gerar código de pareamento |
| `WA_URL` | str | `http://wa:3000` | número do robô (só dígitos, com 55) para gerar código de pareamento |

## IA local (opcional)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `OLLAMA_URL` | str | `http://ollama:11434` |  |
| `AI_ENABLED` | bool | `True` |  |
| `AI_MODEL` | str | `qwen3-vl:8b-instruct` | modelo ÚNICO (texto+visão+comandos), 100% na RTX 4060 |

## Grupo de CASA (segundo canal)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `LAR_ENABLED` | bool | `False` | numero da loja so com digitos (5511999999999): vira o link wa.me/ dos orcamentos |
| `LAR_WHATSAPP_GROUP_ID` 🔒 | str | `` | id do grupo de avisos (termina em @g.us); o conector wa lista os grupos em /groups |
| `LAR_INVITE_LINK` | str | `` | convite do grupo/comunidade de casa (chat.whatsapp.com/...) |
| `LAR_NOME` | str | `Ofertas para casa` | convite do grupo/comunidade de casa (chat.whatsapp.com/...) |
| `LAR_HOUR_START` | int | `7` | público de casa: sem notificação de madrugada |
| `LAR_HOUR_END` | int | `23` | público de casa: sem notificação de madrugada |
| `LAR_DAILY_LIMIT` | int | `40` | começo conservador (número pessoal + conector não oficial = risco de bloqueio) |
| `LAR_PEAK_INTERVAL_MIN` | float | `2.5` | casa: intervalo nos horários de pico (PEAK_HOURS) |
| `LAR_PEAK_INTERVAL_MAX` | float | `3.5` | casa: intervalo nos horários de pico (PEAK_HOURS) |
| `LAR_INTERVAL_MIN` | float | `12` |  |
| `LAR_INTERVAL_MAX` | float | `20` |  |
| `LAR_MIN_DISCOUNT_PCT` | int | `30` |  |
| `LAR_MIN_PRICE` | float | `8.0` | grupo de casa aceita "coisinha" barata (potes, utensílios) — pedido do grupo, 14/10 |
| `LAR_PELANDO_MIN_TEMP` | int | `100` | páginas gerais do Pelando: oferta de casa votada |
| `LAR_KEYWORDS` | str | `cozinha,panela,frigideira,caçarola,assadeira,...` | páginas gerais do Pelando: oferta de casa votada |
| `LAR_PELANDO_TERMS` | str | `air fryer,jogo de panelas,frigideira,potes he...` |  |
| `LAR_SHOPEE_KEYWORDS` | str | `jogo de toalhas,toalha de banho,jogo de cama,...` |  |
| `LAR_SHOPEE_POR_CICLO` | int | `4` | palavras de casa por coleta (era 2: o grupo ficava com a fila vazia) |
| `LAR_PELANDO_POR_CICLO` | int | `8` | palavras de casa por coleta (era 2: o grupo ficava com a fila vazia) |
| `LAR_BASICOS` | str | `chinelo,chinelos,sandália,sandalia,rasteirinh...` | dia a dia (higiene, beleza, roupa, fitness, pet, utilidades): classifica como CASA |
| `LAR_BUSCA_SHOPEE_BASICOS` | str | `chinelo slide,sandalia feminina,camiseta dry ...` | dia a dia (higiene, beleza, roupa, fitness, pet, utilidades): classifica como CASA |
| `LAR_BUSCA_PELANDO_BASICOS` | str | `chinelo,sandalia,camiseta,legging,roupa de ac...` |  |

## Awin (afiliado, KaBuM)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `AWIN_PUBLISHER_ID` 🔒 | str | `` | Awin (app/awin.py): conta do publisher (AWIN_PUBLISHER_ID). Samsung (25539) fica FORA do mapa: só pode promoção vinda da própria Awin. |
| `AWIN_TOKEN` 🔒 | str | `` | token OAuth2 da API (atalho "Gravar token Awin"); sem ele vale só AWIN_APPROVED_MIDS |
| `AWIN_MERCHANTS` | str | `kabum.com.br:17729` | loja:ID do anunciante |
| `AWIN_APPROVED_MIDS` | str | `` | aprovações informadas à mão (o token descobre sozinho) |

## Redes sociais

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `SOCIAL_CTA` | str | `LINK DO GRUPO NA BIO` |  |
| `SOCIAL_ENABLED` | bool | `True` | Meta: Página + Instagram (app/social.py) |
| `SOCIAL_STORY_TIMES` | str | `11:00,14:00,18:00,21:00` | 4/dia (dono: sem poluição visual) |
| `SOCIAL_FEED_TIME` | str | `19:30` | 4/dia (dono: sem poluição visual) |
| `SOCIAL_FEED_DAYS` | str | `mon,wed,fri` | oferta no feed só nesses dias (feed = vitrine da loja) |

## Voz (opcional)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `VOICE_ENABLED` | bool | `False` | narração com a voz do dono nos Reels (serviço /opt/apps/voicelab); ligar após aprovação do dono |
| `VOICE_URL` | str | `http://voice:8300` | narração com a voz do dono nos Reels (serviço /opt/apps/voicelab); ligar após aprovação do dono |
| `VOICE_STYLE` | str | `neutro` | neutro / solto / animado / vibrante (estilos medidos em voicelab/lab/expressivo.py) |

## Threads

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `THREADS_ENABLED` | bool | `True` | Threads (app/threads.py) |
| `THREADS_TOKEN` 🔒 | str | `` | Threads (app/threads.py) |

## Meta (Instagram e Facebook)

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `META_PAGE_ID` 🔒 | str | `` | Meta: Página + Instagram (app/social.py) |
| `META_IG_ID` 🔒 | str | `` |  |
| `META_PAGE_TOKEN` 🔒 | str | `` |  |

## Reels

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `REELS_ENABLED` | bool | `False` | 14/10/2026: Wyse sem vídeo/voz; Reels só voltam com máquina maior |
| `REEL_OFERTAS_ENABLED` | bool | `True` | Reel diário de ofertas (só na aba Reels, fora da grade do perfil) |
| `REEL_OFERTAS_HORA` | str | `20:00` | Reel diário de ofertas (só na aba Reels, fora da grade do perfil) |
| `REEL_LEVE` | bool | `True` | Wyse: sem zoom, música de arquivo (/srv/cache/music) |

## Estudio de noticias

| Variavel | Tipo | Padrao | O que faz |
|---|---|---|---|
| `ESTUDIO_ENABLED` | bool | `True` | ESTÚDIO (14/10/2026): novidades de tecnologia escritas pela IA do PC do dono (app/estudio.py) |
| `ESTUDIO_FOTO_MATERIA` | bool | `False` | capa com a foto da própria matéria (crédito na imagem); decisão do dono |
| `ESTUDIO_SIMPLES` | bool | `False` | True = novidades sem IA e sem o PC do dono (manchete + resumo do feed + fontes) |
| `ESTUDIO_ESTOQUE_ALVO` | int | `3` | posts prontos + tarefas esperando o PC |
| `ESTUDIO_VALIDADE_DIAS` | int | `4` | notícia mais velha que isso é descartada |
| `ESTUDIO_DIAS` | str | `wed,fri,sat` | notícia mais velha que isso é descartada |
| `ESTUDIO_HORA` | str | `12:30` |  |

🔒 = segredo: so no `.env`, nunca no codigo nem no Git.
