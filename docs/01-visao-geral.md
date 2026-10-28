# 01 — Visão geral

## O caminho de uma oferta (do início ao grupo)
```text
 fontes ──► coleta ──► regras ──► fila ──► (na hora de postar) ──► link de afiliado ──► foto ──► texto ──► envio ──► registro
 ML/Shopee/            desconto,   banco    ML: navegador logado     valida a foto      selo, preço,   WhatsApp   status
 AliExpress/           marca,      (status  gera o meli.la;          do anúncio         loja, cupom,   (Telegram  posted
 Pelando/...           histórico,  new)     Shopee/Ali: API                             #Anuncio       opcional)
                       repetição
```
1. **Coleta** (a cada `COLLECT_INTERVAL_MIN`, padrão 15 min): cada fonte devolve ofertas num formato único (`RawOffer`).
2. **Regras** (`engine.py`): preço válido, palavras proibidas, desconto mínimo, repetição, marca confiável, categoria (tecnologia ou casa), histórico de preço. A oferta vira `new` (aprovada), `rejected` (com o motivo) ou fica de fora.
3. **Fila:** ofertas aprovadas esperam, ordenadas por **score** (desconto, tipo de produto, votos, histórico). Ofertas velhas expiram (`QUEUE_MAX_HOURS`).
4. **Publicação:** a cada intervalo **aleatório** (menor no horário de pico) o robô pega a melhor oferta, gera o link de afiliado **na hora**, valida a foto e envia. Teto diário por canal.
5. **Depois:** a oferta vira `posted`. O mesmo produto não volta antes de `REPEAT_DAYS`, a não ser que o preço caia bastante.

## Canais de saída
| Canal | Estado | Observações |
|---|---|---|
| WhatsApp (grupo/comunidade) | principal | conector não oficial, só envia |
| Telegram | opcional | bot oficial; no autor está desligado para ofertas |
| Instagram (Stories, feed, Reels) | opcional | Graph API oficial (Meta) |
| Facebook (Página) | opcional | idem |
| Threads | opcional | API oficial |
| YouTube (Shorts e vídeos longos) | opcional | OAuth; Shorts agendados na plataforma |
| TikTok | **não implementado** | ver `07-redes-sociais.md` (exige auditoria do TikTok) |

## Dois grupos: tecnologia e casa
O robô separa as ofertas em dois canais pelo título (`engine.canal_de`): **tech** (computador, periféricos, games, celular) e **lar** (casa, cozinha, higiene, dia a dia). Cada canal tem grupo, teto diário, horário e ritmo próprios. O de casa é opcional (`LAR_ENABLED`).

## Fontes de ofertas
| Fonte | Como | Comissão |
|---|---|---|
| Mercado Livre | páginas de oferta e categorias; link meli.la gerado pelo navegador logado | sim |
| Shopee | API oficial de afiliados (palavras-chave em rodízio) | sim |
| AliExpress | API oficial (ou Portals via navegador) | sim |
| KaBuM (Awin) | só com aprovação e cupom da própria Awin | sim |
| Pelando, Promobit, Gatry | listas públicas (apoio, "bônus" sem comissão) | não |
| Canais do Telegram (opcional) | só leitura pública, **fonte de emergência** | não |

Detalhe e como se cadastrar: `05-afiliados.md`.

## Cupons
- **Cupons com código** (Mercado Livre e Shopee) coletados do Pelando e postados quando há código novo.
- **Cupom sugerido em cada oferta:** o robô escolhe, entre os cupons ativos, o mais relevante (Tech para tecnologia, "todo o site" para o resto) e mostra a economia estimada. É sempre uma **sugestão**: o robô não consegue confirmar se aquele anúncio participa, então **nunca altera o preço** do post.
- Regra de programa: em lojas como KaBuM/Samsung (Awin) só vale cupom da própria Awin.

## Conteúdo extra (opcional)
Stories 4 vezes por dia (melhor oferta do dia), carrossel educativo semanal, jogos grátis da semana, novidades de tecnologia, Reels prontos entregues por uma fila, relatórios diários. Tudo é configurável ou desligável. `08-conteudo-e-reels.md`.

## O que mantém tudo no ar
- Serviços do `systemd` com reinício automático e limite de memória.
- Vigias de disco e memória (cron) + manutenção noturna.
- Backup diário do banco, configuração e sessão do WhatsApp.
- `catchup`: se o equipamento reiniciar, posts agendados do dia que passaram sem rodar são recuperados sozinhos.
- Alertas gravados em `data/alertas.log` (e visíveis com `ctl alertas`).

## O que o robô NÃO faz
- Não burla captcha nem anti-bot.
- Não responde mensagens (o conector do WhatsApp **só envia**; não lê o que chega).
- Não promete preço, estoque ou resultado.
- Não usa IA em tempo de execução (a IA de visão/texto opcional está desligada por padrão; a validação de foto é por medidas).
