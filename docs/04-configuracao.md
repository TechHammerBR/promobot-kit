# 04 — Configuração (o essencial)

Toda a configuração vive em **um arquivo**: `/opt/promobot/.env`. Cada linha é `NOME=valor`. O nome é o do campo em `src/app/config.py` em MAIÚSCULAS. A lista completa (170 campos) está em `referencia/configuracoes.md` e `.env.example`.

**Regra de ouro:** comece com poucas coisas ligadas. Cada recurso extra é mais uma conta para manter.

## Perfil mínimo (só WhatsApp + Shopee, em simulação)
```env
SIMULATE_POSTS=true
SHOPEE_APP_ID=        # da sua conta Shopee Affiliate
SHOPEE_SECRET=
WHATSAPP_GROUP_NAME=  # deixe vazio na simulação
CONTENT_ENABLED=false # sem Stories/feed/Reels: só grupos
SOCIAL_ENABLED=false
THREADS_ENABLED=false
ESTUDIO_ENABLED=false
```

## Perfil recomendado (grupo de tecnologia no ar)
```env
WHATSAPP_GROUP_NAME=Nome Exato do Seu Grupo
WHATSAPP_NUMBER=5511999999999     # número do robô, só dígitos com 55
STORE_WHATSAPP=5511999999999      # número da loja (link de orçamento nos posts de serviço)
SHOPEE_APP_ID=...
SHOPEE_SECRET=...
ML_TAG_TECH=sua-etiqueta-tech     # etiqueta do afiliado ML (Administrar etiquetas)
DAILY_POST_LIMIT=60
MIN_DISCOUNT_PCT=30
LINKGEN_ENABLED=true              # precisa do navegador logado (ver 05)
```

## Grupos de variáveis (mais usadas)
| Assunto | Variáveis principais | Para que servem |
|---|---|---|
| Ritmo | `INTERVAL_MIN/MAX`, `PEAK_INTERVAL_MIN/MAX`, `PEAK_HOURS`, `DAILY_POST_LIMIT`, `ACTIVE_HOUR_START/END`, `NIGHT_*` | quando e com que frequência posta |
| Qualidade | `MIN_DISCOUNT_PCT`, `ABSURD_DISCOUNT_PCT`, `BANNED_WORDS`, `REPEAT_DAYS`, `REPEAT_MIN_DROP`, `QUEUE_MAX_HOURS` | o que entra, o que repete, quanto tempo fica na fila |
| Foco | `PRIORITY_KEYWORDS`, `PRIORITY_BONUS` | tecnologia (ou outro nicho) sobe na fila |
| Mix de lojas | `MIX_ENABLED`, `MIX_ML`, `MIX_ALI`, `MIX_JANELA` | proporção entre ML, Shopee e AliExpress |
| Shopee | `SHOPEE_*` (chaves, palavras, preço, nota, vendas, só loja oficial) | busca e filtros da Shopee |
| AliExpress | `ALI_*` | API e filtros |
| Casa | `LAR_*` | segundo grupo (casa e dia a dia) |
| Texto do post | `POST_HASHTAG`, `GROUP_INVITE_LINK`, `GROUP_INVITE_LABEL`, `BRAND_NAME` | rodapé, hashtag, marca |
| Redes | `SOCIAL_*`, `META_*`, `THREADS_*` | Instagram, Facebook, Threads |
| Cupons | `OFFER_COUPON_HINT`, `CODE_POST_GAP_HOURS`, `SHOPEE_COUPONS_ENABLED` | cupom nas ofertas e posts de cupom |

## Como mudar sem editar arquivo
O `ctl` altera os principais em tempo real (`desconto 30`, `limite 80`, `intervalo 5 8`, `pausar 60`, `retomar`). Mudou o `.env`? Reinicie: `sudo systemctl restart promobot-bot`.

## Cuidados
- **Nunca** versione o `.env` (o `.gitignore` já bloqueia). `chmod 600 .env`.
- Não cole chaves no chat. Use `ferramentas/gravar_meta.sh` e `ferramentas/gravar_awin.sh` (leem sem mostrar na tela).
- Valores com vírgula (listas) vão **sem aspas** e sem espaço depois da vírgula.
- Depois de qualquer mudança grande, rode `ctl diag` e acompanhe `ctl alertas`.
