# 05 — Afiliados (como o robô ganha comissão)

O robô troca **todo link** das lojas parceiras pelo **seu** link de afiliado antes de publicar. Cada loja tem um caminho diferente. Cadastre-se primeiro; o robô só funciona com as suas contas.

## Visão geral
| Loja | Como o robô gera o link | O que você precisa |
|---|---|---|
| **Mercado Livre** | navegador logado (`linkgen`) clica em "Compartilhar" na barra de afiliados e captura o `https://meli.la/...` (~7 s por link). Não há API para isso. | conta no **Programa de Afiliados do ML** ativa + login único no navegador do robô |
| **Shopee** | API oficial (Shopee Affiliate Open API) | `SHOPEE_APP_ID` e `SHOPEE_SECRET` |
| **AliExpress** | API oficial (`ALI_APP_KEY`, `ALI_APP_SECRET`, `ALI_TRACKING_ID`); sem a API, via Portals no navegador logado | conta no **AliExpress Portals** + (opcional) aprovação da API de afiliados |
| **KaBuM** (e outras via Awin) | link `awin1.com/cread.php` | conta de publisher na **Awin**, aprovação do anunciante, `AWIN_PUBLISHER_ID`/`AWIN_TOKEN` |
| Amazon | não implementado (o autor não conseguiu ser afiliado) | — |

## Mercado Livre (o mais trabalhoso, o mais valioso)
1. Entre no programa de afiliados do ML e **crie as etiquetas** que quiser (ex.: uma por grupo). Coloque em `ML_TAG_TECH` e `ML_TAG_LAR`.
2. O link do formato antigo (`?matt_tool=...&matt_word=...`) **não** mostra a indicação do afiliado como o `meli.la`. Por isso o robô usa o navegador.
3. **Login único** no navegador do robô (refazer só se a sessão expirar):
   ```bash
   sudo systemctl start promobot-vnc          # liga a tela remota (expira sozinha em 2 h)
   ssh -L 6080:localhost:6080 promobot@IP-DO-SERVIDOR   # no SEU computador
   # abra no seu navegador: http://localhost:6080/vnc.html
   ```
   Faça o login normal do Mercado Livre na tela que aparecer (inclui verificação em duas etapas). Depois: `sudo systemctl stop promobot-vnc`.
   A porta 6080 fica **só em 127.0.0.1** do servidor: nunca exponha na rede.
4. Teste: `curl "http://127.0.0.1:8000/health"` deve mostrar `"logged_in": true`.
5. **Efeito colateral aceito:** cada link gerado adiciona o produto à lista "Minhas recomendações" do afiliado.
6. O link é gerado **só na hora de publicar** (1 por post): ritmo humano, sem chamar a atenção do firewall do ML.
7. Se o ML mostrar "Por segurança, complete esta etapa" (reCAPTCHA), o robô **não** tenta burlar: a geração de links falha, o alerta "Publicação falhou 3x seguidas" aparece e as ofertas ML esperam. Resolva à mão pelo VNC (marque a caixinha) ou aguarde — já aconteceu de liberar sozinho.
8. Se a conta de afiliado for suspensa: `ML_PAUSED_UNTIL=AAAA-MM-DD` desliga a coleta do ML até a data; `ML_BONUS_MODE=true` continua postando ofertas do ML como "bônus" (link limpo, sem comissão).

## Shopee
1. Cadastre-se no programa de afiliados da Shopee e solicite acesso à **Open API**.
2. Preencha `SHOPEE_APP_ID` e `SHOPEE_SECRET`.
3. Ajuste os filtros: `SHOPEE_MIN_PRICE`, `SHOPEE_MIN_RATING` (nota), `SHOPEE_MIN_SOLD` (vendas), `SHOPEE_MALL_ONLY` (só loja oficial — recomendado), `SHOPEE_MAX_DISCOUNT` (acima disso costuma ser falsificado).
4. As palavras buscadas rodam em rodízio (`SHOPEE_KEYWORDS`, `SHOPEE_KEYWORDS_PER_CYCLE`). Edite para o seu nicho.
5. Cupons da Shopee (com código) vêm do Pelando e o post leva **o seu** link de afiliado da central de cupons.

## AliExpress
- **Com API** (recomendado): peça acesso à API de afiliados (programa "Affiliates", conta individual) e preencha `ALI_APP_KEY`, `ALI_APP_SECRET`, `ALI_TRACKING_ID`.
- **Sem API:** o navegador logado no Portals (`linkgen` tem rotas `/ali_offers` e `/ali_link`). Mais lento e frágil; use só enquanto a API não é aprovada.
- Regras do robô: só **marcas conhecidas** (`ALI_KNOWN_BRANDS_ONLY`, lista em `titles.py`), mínimo de vendas e preço, no máximo 1 post a cada N (`ALI_EVERY`). Foto do AliExpress costuma ser propaganda: poucas passam na validação (aceito).
- O post avisa: "Compra internacional (AliExpress) · confira taxas no checkout".

## Awin (KaBuM e outras)
- Cadastre-se como publisher, peça aprovação ao anunciante e preencha `AWIN_PUBLISHER_ID`, `AWIN_TOKEN` (OAuth2) e `AWIN_MERCHANTS` (`loja:ID`).
- **Regra crítica do programa:** KaBuM e Samsung **cancelam a comissão** de venda com cupom que não veio da Awin. Por isso o robô **nunca publica cupom de terceiros nem oferta cujo preço dependa de cupom** nessas lojas (`NO_OUTSIDE_COUPON_HOSTS`). Não remova essa proteção.

## Como confirmar que está tudo certo
1. Abra um post publicado e clique no link de afiliado.
2. Confira no painel da loja que o clique apareceu para a **sua** conta/etiqueta (pode levar de minutos a horas).
3. `ctl status` mostra posts do dia; o banco guarda `monetized` (se a oferta saiu com link de afiliado).

## Boas práticas e limites
- Use **uma etiqueta por canal** para saber qual grupo converte.
- Não clique nos seus próprios links para "testar" repetidamente: os programas detectam e podem punir.
- Informe a publicidade: todo post leva `#Anuncio` (`POST_HASHTAG`).
