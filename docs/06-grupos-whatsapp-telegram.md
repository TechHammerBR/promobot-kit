# 06 — WhatsApp e Telegram

## WhatsApp: como funciona
O conector `src/wa/` (Node + biblioteca **Baileys**) conecta ao WhatsApp como um "aparelho vinculado" (igual ao WhatsApp Web) e **só envia** mensagens. Ele **não lê** nada que chega. O robô fala com ele por uma API local (porta 3000, só no servidor):

| Rota | Função |
|---|---|
| `GET /status` | `{connected, me}` — está conectado? |
| `GET /pair?number=55DDD...` | gera o **código de pareamento** de 8 caracteres (alternativa ao QR) |
| `GET /groups` | lista os grupos onde o número participa (`id`, `name`) |
| `POST /send {to, text, image\|image_b64}` | envia foto+legenda (ou só texto) |
| `POST /ephemeral` | liga/ajusta mensagens temporárias do grupo |

A sessão fica em `data/wa/` (permissão 700, **entra no backup**). Se perder a sessão, é só parear de novo.

## Passo a passo: conectar
1. **Use um número só para o robô** (chip pré-pago barato), não o seu pessoal. Instale o WhatsApp nesse número num celular.
2. Crie o **grupo** (ou comunidade) de ofertas com esse número como **administrador**. Configure "somente admins enviam mensagens".
3. Suba o conector: `sudo systemctl start promobot-wa`.
4. Gere o código de pareamento:
   ```bash
   curl "http://127.0.0.1:3000/pair?number=5511999999999"
   ```
   No celular: **WhatsApp → Dispositivos conectados → Conectar um dispositivo → Conectar com número de telefone** e digite o código de 8 caracteres.
5. Confirme: `curl http://127.0.0.1:3000/status` → `{"connected":true,...}`.
6. Descubra o nome exato do grupo: `curl http://127.0.0.1:3000/groups`.
7. No `.env`: `WHATSAPP_GROUP_NAME=Nome Exato do Grupo` e `WHATSAPP_NUMBER=5511999999999`. Reinicie o robô.

## Grupo de casa (segundo canal)
Para o grupo de casa dentro de uma **comunidade**, o nome se repete (comunidade e grupo de avisos). Por isso use o **ID** do grupo de avisos: `LAR_ENABLED=true`, `LAR_WHATSAPP_GROUP_ID=...@g.us` (veja em `/groups`), `LAR_INVITE_LINK=https://chat.whatsapp.com/...`.

## Risco de bloqueio (leia)
- Baileys **não é oficial**. A Meta pode bloquear números que automatizam o WhatsApp, principalmente se enviarem muito, sempre no mesmo ritmo ou para muita gente que não pediu.
- O robô reduz o risco: intervalo **aleatório** entre posts, teto diário, silêncio na madrugada, **somente grupos** onde as pessoas entraram por vontade própria.
- **Evite** o recurso de convite em massa a contatos (`CONVITE_ENABLED`, desligado por padrão): é o que mais derruba número.
- Comece devagar: `DAILY_POST_LIMIT=30` na primeira semana e aumente se não houver problema.
- Tenha plano B: guarde os links de convite e uma lista de transmissão/Telegram para migrar a audiência se o número cair.
- Se quiser **zero risco**, use a API oficial do WhatsApp Business (custa por conversa e não permite o mesmo uso em grupo). Não está implementada neste kit.

## Mensagens temporárias
O WhatsApp só oferece 24 h, 7 dias ou 90 dias. O autor usa 7 dias no grupo de ofertas. Rota `POST /ephemeral` do conector.

## Vigia do WhatsApp
`app/watchdog.py` e o guardião conferem `/status`. ~10 min desconectado gera alerta (`ctl alertas`). O `promobot-wa` reinicia sozinho (`Restart=always`).

## Telegram (opcional)
1. No Telegram, converse com **@BotFather** → `/newbot` → guarde o **token**.
2. Crie o canal, adicione o bot como **administrador** e anote o **ID do canal** (começa com `-100`).
3. `.env`: `TELEGRAM_BOT_TOKEN=...`, `TELEGRAM_CHANNEL_ID=-100...`, `TELEGRAM_POST_ENABLED=true`.
4. `TELEGRAM_ADMIN_CHAT_ID`: seu chat com o bot (mande "oi" ao bot e descubra o ID) — recebe alertas.
5. Sem token o robô entra em **modo simulação** e escreve em `data/outbox.log`.

## Formato dos posts
Texto único em dois dialetos: Telegram (HTML) e WhatsApp (`*negrito*`, `~riscado~`). Estrutura:
```text
🔥💻 *-47% | Título curto do produto*

💰 Por: *R$ 17,00*  (~R$ 32,08~)
💳 ou 10x de R$ 1,99 sem juros          (quando a loja informa)
🎟️ Tente o cupom CODIGO: ... (economia de até R$ X)   (sugestão)

🏪 Vendido na Shopee
🛒 Link do produto: https://...
⚠️ Oferta válida enquanto durarem os estoques. Preço pode variar.

📲 Conheça também:
🏠 Ofertas para casa: <link do outro grupo>

#Anuncio
```
O selo `-47% |` só aparece com desconto de 35% ou mais; abaixo disso o desconto fica na linha do preço. Desligue o formato novo com `CHAMADA_V2=0`.
