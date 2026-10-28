# 10 — Regras de negócio (o que decide o que vai ao ar)

Valores são os **padrões** de `config.py`; todos ajustáveis no `.env`.

## 1. Entrada na fila (`engine.evaluate`)
| Regra | Padrão |
|---|---|
| Preço válido (> 0) | — |
| Palavras proibidas no título | `BANNED_WORDS=recondicionado,usado,réplica` |
| Desconto mínimo (tecnologia) | `MIN_DISCOUNT_PCT=30` |
| Fora de tecnologia | só com desconto absurdo (`ABSURD_DISCOUNT_PCT=60`) |
| Casa | `LAR_MIN_DISCOUNT_PCT=30`, `LAR_MIN_PRICE=8` |
| Foco | `PRIORITY_KEYWORDS` dão `+PRIORITY_BONUS` no score (padrão: computador, peças, periféricos, games, celular) |
| Duplicata | mesma oferta (`fingerprint`) dentro de `DEDUPE_HOURS=24` é ignorada |
| Marca confiável (AliExpress) | só marcas da lista em `titles.py` (`ALI_KNOWN_BRANDS_ONLY`) |
| Qualidade Shopee | nota ≥ 4,7, ≥ 20 vendas, só loja oficial (Mall), desconto ≤ 70% (acima disso costuma ser falsificação) |

## 2. Repetição
Um **produto** (`product_key`: MLB…/ASIN etc.) não volta antes de `REPEAT_DAYS=3`, **a menos que** o preço novo seja pelo menos `REPEAT_MIN_DROP=30%` menor que o da última vez (`engine.queda_expressiva`).

## 3. Fila e score
Maior **score** primeiro (desconto, categoria prioritária, votos/temperatura da fonte, hardware, ticket alto, histórico de preço). Oferta com mais de `QUEUE_MAX_HOURS=6` expira.

## 4. Mix de lojas (`MIX_*`)
Meta: Mercado Livre ≥ `MIX_ML=50%` dos últimos `MIX_JANELA=20` posts, AliExpress ≤ 15%, o resto Shopee. Lojas **sem afiliado** não saem. Se o ML estiver abaixo do piso (`MIX_PISO_ML`) e não houver oferta ML na fila, o grupo **espera** em vez de encher de Shopee/AliExpress.

## 4b. Histórico de preço (`pricehist.py`)
Depois de `PRICE_HISTORY_MIN_DAYS=3` dias de histórico: preço ≥ `PRICE_DROP_PCT=5%` abaixo do menor já visto → "📉 Menor preço dos últimos N dias (pelo nosso histórico)". Preço igual ao de sempre → sem selo de desconto.

## 5. Ritmo
- Horário ativo 6h–3h; madrugada (`NIGHT_HOURS=0-3`) mais lenta.
- Intervalo aleatório: normal 10–18 min, pico (`PEAK_HOURS`) 7–12 min (o autor usa 5–8 min).
- Teto diário `DAILY_POST_LIMIT` (cupons não contam). Casa tem ritmo e teto próprios (`LAR_*`).

## 6. Foto (`photocheck.py`, sem IA)
A foto precisa parecer **catálogo**: um produto em destaque sobre fundo uniforme. Reprova:
- fundo irregular (cena/banner), arte escura/colorida, "quase vazia" ou sem fundo livre;
- **selo promocional** no canto, **texto de propaganda** (muitas letras/linhas);
- **colagem** (vários objetos) — exceto kit de unidades iguais;
- **textura / quadro de vídeo vertical sem produto** (regra de 28/10: muitos pedaços e nenhum objeto grande);
- foto menor que 200 px.
Ordem: foto do card → fotos da **galeria do próprio anúncio** (até 8) → foto da página da loja. Nunca busca foto fora do anúncio/loja. Sem foto aprovada, a oferta é rejeitada e o robô pula para a próxima.

## 7. Texto do post (`templates.render`) — "chamada v2"
- Selo `-N% |` no começo do título **só com desconto ≥ 35%** (`SELO_MIN_PCT`).
- O desconto aparece **uma vez** (no selo ou na linha do preço), nunca duas.
- Linha da loja ("Vendido na Shopee") quando a fonte é a própria loja.
- Sem urgência inventada, sem "últimas unidades".
- Desliga com `CHAMADA_V2=0`.

## 8. Cupons
- **Posts de cupom:** códigos do Pelando por loja; só frescos; no máximo 1 post a cada `CODE_POST_GAP_HOURS=3` (Shopee: `1`) e só com código novo.
- **Cupom sugerido na oferta** (`coupon_codes.sugerir`): ML/Shopee; escolhe 1º o cupom da categoria do canal (Tech para tecnologia; Casa para casa), depois o de **maior economia estimada**, respeitando o **valor mínimo**. Descarta cupom de marca/categoria errada, "exclusivo Meli+", "só quem resgatou", "loja oficial", "internacional", etc. Mostra "economia de até R$ X". **Nunca muda o preço** do post: é sugestão.
- **Regra de programa (Awin):** KaBuM/Samsung só com cupom da Awin; ofertas cujo preço depende de cupom de terceiro nem entram.

## 9. Segurança de conteúdo
- Preço antigo falso (inflado) é tratado pelo histórico e por `SHOPEE_MAX_DISCOUNT`.
- Marketplace de terceiros suspeito (marca desconhecida) é barrado no AliExpress.
- Todo post leva `#Anuncio` (`POST_HASHTAG`).

## 10. Saúde das fontes
Cada fonte tem contador de falhas; 3 seguidas geram alerta. Bloqueio (403/429/captcha) pausa a fonte com recuo (30 min, 1 h, 2 h… até 12 h). Coleta vazia (0 itens) em fonte que costuma ter → "provável mudança de layout".
