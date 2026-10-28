# 03 — Instalação passo a passo

> **Testado em 28/10/2026** numa VM Debian 13 com o **mínimo do Wyse** (4 núcleos, 2 GB de RAM, 4 GB de swap): os passos 1 a 10 funcionaram do zero (relatório e correções em `18-teste-de-instalacao.md`). **Não foi possível testar:** parear o WhatsApp (precisa de um número real) e o login do Mercado Livre. O **passo 12 (redes sociais)** teve as ferramentas testadas com as contas do autor (verificação só de leitura e prévia das artes); o caminho completo de conectar do zero com uma conta nova (troca do token, fluxo do navegador do YouTube) **ainda não foi testado por terceiros** — se travar, abra um Issue. Se algo não bater no seu servidor, use `prompts/01-instalar-do-zero.md` e abra um Issue.

## 0. O servidor (leia `01a-servidor-e-requisitos.md`)
O robô precisa de um **servidor ligado 24 h**. **Mínimo = Dell Wyse 3040:** processador de **4 núcleos a 1,44 GHz** (turbo até 1,92 GHz; Intel Atom x5-Z8350), **2 GB de RAM**, **24 GB de armazenamento no total**, rede cabeada e Debian 13 (sem interface gráfica). O armazenamento total cobre sistema, robô, dados, backup e swap. Recomendado: 4 núcleos a 2 GHz ou mais, 4 GB de RAM e 32 GB de armazenamento no total. Nobreak é altamente aconselhável.

## 1. Sistema operacional
Instale **Debian 13 (trixie)** ou Ubuntu 24.04+, versão "servidor" (sem interface gráfica), com SSH. Crie o usuário de serviço (sugestão: `promobot`) com `sudo`.

```bash
sudo apt install -y adduser sudo    # só se o comando 'adduser' não existir (imagens mínimas)
sudo adduser promobot
sudo usermod -aG sudo promobot
```
Acesse sempre por SSH com **chave** (não senha): `docs/11-seguranca-e-backup.md`.

## 2. Pacotes do sistema
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git sqlite3 curl \
  nodejs npm chromium xvfb x11vnc novnc websockify ffmpeg \
  fonts-liberation fonts-dejavu-core
node --version   # precisa ser 20 ou mais
```
(`ffmpeg` só é necessário se for usar conteúdo em vídeo; `x11vnc/novnc/websockify` só para o login do Mercado Livre.)

## 3. Código e ambiente Python
```bash
# 1) baixe o kit para a sua pasta pessoal (NÃO apague depois: o passo 7 usa deploy/)
git clone <URL-DO-REPOSITORIO> ~/promobot-kit
# 2) copie o robô para /opt/promobot (o ponto em "src/." copia também arquivos ocultos)
sudo mkdir -p /opt/promobot && sudo chown promobot: /opt/promobot
cp -r ~/promobot-kit/src/. /opt/promobot/
cp ~/promobot-kit/.env.example /opt/promobot/.env
cd /opt/promobot
# 3) ambiente Python com as versões fixadas
python3 -m venv venv
venv/bin/pip install -r requirements.lite.txt
mkdir -p data/logs
chmod 600 .env
```
- `requirements.lite.txt` é o conjunto enxuto (robô sem IA/vídeo). `requirements.txt` acrescenta o driver do PostgreSQL.
- O `playwright` (usado pelo `linkgen`) **não baixa navegador**: usa o Chromium do sistema (`LINKGEN_CHROMIUM=/usr/bin/chromium`).
- O `.env.example` já vem no **perfil leve e em modo simulação** (`SIMULATE_POSTS=true`).

> **Repositório privado no GitHub:** o `git clone` por HTTPS pede **usuário e token** (a senha da conta não funciona). Se aparecer `fatal: could not read Username for 'https://github.com'`, é falta de login. Três jeitos:
> 1. **Token (mais simples):** no GitHub → *Settings → Developer settings → Personal access tokens → Fine-grained tokens* → crie um token só com acesso de **leitura ao conteúdo** deste repositório; use o token como senha no `git clone`.
> 2. **GitHub CLI:** `sudo apt install gh && gh auth login`, depois `gh repo clone <dono>/promobot-kit ~/promobot-kit`.
> 3. **ZIP:** na página do repositório, *Code → Download ZIP*, envie para o servidor (`scp`) e descompacte em `~/promobot-kit`.
> Seu acesso ao repositório depende de o autor ter te convidado (*Settings → Collaborators*).

## 4. Conector do WhatsApp
```bash
cd /opt/promobot/wa
npm install --omit=dev
```

## 5. Primeiro teste em modo simulação
No `.env`, deixe **vazios** `TELEGRAM_BOT_TOKEN` e `WHATSAPP_GROUP_NAME` e coloque `SIMULATE_POSTS=true`. Rode uma coleta manual:
```bash
cd /opt/promobot
PYTHONPATH=/opt/promobot venv/bin/python -m app.main --once
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl status
tail -n 40 data/outbox.log     # os posts que SERIAM enviados
```
Se aparecerem posts no `outbox.log`, a coleta, as regras e os textos estão funcionando.

**O que esperar (medido na VM do mínimo do Wyse):** a coleta leva cerca de **1 minuto**; o log mostra linhas `collected` por fonte (AliExpress, Pelando, Promobit, Gatry, Shopee…); o `ctl status` mostra `ofertas_na_fila` em dezenas; o primeiro post simulado aparece em `data/outbox.log` em seguida.

> **Atenção:** para a simulação gerar posts você precisa de **pelo menos uma forma de gerar link de afiliado**: as chaves da **Shopee** ou do **AliExpress** (`05-afiliados.md`). Sem nenhuma chave, o AliExpress e a Shopee ficam sem link e quase nada vira post. As ofertas do Mercado Livre/Pelando saem como **bônus** (link limpo, sem comissão) enquanto o navegador do ML não está logado (o `.env.example` já vem com `ML_PAUSED_UNTIL` e `ML_BONUS_MODE` para isso). Sem esse perfil o robô tenta o navegador do ML, falha com `Connection refused` e trava com o alerta "login do ML expirou?".

## 6. Rodar os testes
```bash
PYTHONPATH=/opt/promobot venv/bin/python -m pytest -q tests
```
Alguns testes dependem do `.env` (ex.: intervalos): se você mudou os padrões, eles podem falhar — é esperado.

## 7. Serviços do systemd
Os modelos estão em `~/promobot-kit/deploy/systemd/*.service` (e o timer em `LEIA-timer-e-overrides.txt`). Copie, ajuste o usuário/caminhos se for diferente e ative:
```bash
sudo cp ~/promobot-kit/deploy/systemd/promobot-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now promobot-wa promobot-bot promobot-status
# só se for usar Mercado Livre com link de afiliado:
sudo systemctl enable --now promobot-tela promobot-linkgen
```
Confira:
```bash
systemctl is-active promobot-bot promobot-wa
journalctl -u promobot-bot -f
ss -tln | grep -E ':3000|:8088'      # o conector (3000) deve estar em 127.0.0.1; o status (8088) fica na rede local
```
Na VM de teste os três serviços ficaram `active`, respeitaram os limites de memória e **voltaram sozinhos depois de reiniciar**. Com o navegador do ML, a tela virtual e o VNC ligados juntos, o uso foi de ~0,94 GB de 1,9 GB de RAM.

## 8. Conectar o WhatsApp
Siga `06-grupos-whatsapp-telegram.md` (pareamento por código de 8 caracteres ou QR).

## 9. Conectar as contas de afiliado
- Shopee e AliExpress: chaves no `.env` (`05-afiliados.md`).
- Mercado Livre: login único no navegador do `linkgen` por túnel SSH (`05-afiliados.md`).

## 10. Rotinas automáticas (cron)
Garanta que os scripts são executáveis (o Git do kit já guarda isso; se o seu sistema perder, rode `chmod +x /opt/promobot/backup.sh /opt/promobot/ferramentas/*.sh`).

Como `root` ou com `sudo crontab -e`:
```cron
40 3 * * *   /opt/promobot/backup.sh                              # backup diário do banco/.env/sessão
*/5 * * * *  /opt/promobot/ferramentas/vigia_recursos.sh        # memória e disco (só anota em data/alertas.log)
20 4 * * *   /opt/promobot/ferramentas/manutencao.sh            # enxuga banco e logs (para e religa o robô)
```
- `backup.sh` guarda em `/srv/backup` **se esse disco estiver montado**; senão em `/opt/promobot/backup-local` (só os 3 últimos). Edite `DEST=` para outro lugar.
- Os scripts leem o usuário em `DONO=` (padrão `promobot`).
- ⚠️ **Não** coloque no cron os scripts de `ferramentas/do-autor/`: eles dependem dos discos USB do servidor do autor (um deles **para os serviços** se não achar esses discos). Veja `ferramentas/do-autor/LEIA-ME.md`.
- Os recursos de **conteúdo** (fila de Reels, estúdio, músicas) usam `/srv/cache` por padrão. Se for usá-los: `sudo mkdir -p /srv/cache && sudo chown promobot: /srv/cache` (ou mude `FILA_REELS_DIR`).

## 11. Ligar de verdade (depois de 1 dia em simulação)
1. Preencha `WHATSAPP_GROUP_NAME` (nome exato do grupo) e `WHATSAPP_NUMBER`.
2. Tire `SIMULATE_POSTS`.
3. `sudo systemctl restart promobot-bot`.
4. Acompanhe: `ctl status` e `ctl alertas 20` na primeira hora.

## 12. Redes sociais (opcional — só depois de o grupo estar funcionando)
O robô de grupos **não precisa** de nenhuma rede social. Faça este passo só se quiser **Stories/feed no Instagram e na Página do Facebook, Threads e Shorts no YouTube**. Tudo usa **API oficial** (o robô nunca entra na sua conta pelo login) e, enquanto o app estiver em **modo de desenvolvimento**, funciona para as **suas próprias** contas **sem passar pela revisão da Meta**.

**Regra de ouro:** gere a **prévia**, aprove o visual, e só então ligue a publicação. Nunca cole token no chat nem no Git: os scripts abaixo pedem sem mostrar na tela e gravam no `.env` (permissão 600).

Todos os comandos rodam no servidor, em `/opt/promobot`. Cada conexão é independente: faça só as que quiser.

### 12.1 Instagram + Página do Facebook (Meta)
**Antes de começar (no celular/computador, na sua conta):**
1. O Instagram precisa ser **Profissional** (Comercial ou Criador): Instagram → *Configurações → Tipo de conta e ferramentas → Mudar para conta profissional*.
2. Crie (ou use) uma **Página do Facebook** e **vincule** o Instagram a ela: na Página → *Configurações → Contas vinculadas → Instagram*. Perfil **pessoal** do Facebook **não tem API** (o robô só posta na Página).
3. Você precisa ser **administrador** da Página.

**Criar o app (uma vez, em `developers.facebook.com`):**
1. *Meus apps → Criar app* → tipo **Empresa (Business)**. Dê qualquer nome. Se pedir "casos de uso" / produtos, escolha os que dão **Instagram** (publicação de conteúdo) e **Páginas** (gerenciar a Página).
2. Deixe o app em **Modo de desenvolvimento** (o padrão). **Não** precisa publicar o app nem pedir revisão para postar nas **suas** contas.
3. Em *Configurações do app → Básico* anote o **ID do app** e a **Chave secreta do app** (botão "Mostrar").

**Gerar o token (expira em ~1 hora; o script troca por um longo):**
1. Abra o **Explorador da Graph API** (`developers.facebook.com/tools/explorer`), escolha o seu app e *Tipo de token = Token de usuário*.
2. Em *Permissões*, adicione: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish` (se a sua Página estiver dentro de um *Portfólio empresarial*, adicione também `business_management`).
3. Clique em *Gerar token de acesso*. Na janela da Meta, **marque a sua Página e o Instagram** vinculado e aceite. Copie o token (mais de 50 caracteres).

**Conectar:**
```bash
cd /opt/promobot
venv/bin/python ferramentas/meta_conectar.py
```
Ele pede o ID do app, a chave secreta e o token (os dois últimos **não aparecem** na tela), troca por um token longo, lista as Páginas, acha sozinho o ID da Página e do Instagram vinculado, e grava `META_APP_ID`, `META_APP_SECRET`, `META_USER_TOKEN`, `META_PAGE_ID`, `META_PAGE_TOKEN` e `META_IG_ID` no `.env`. O **token da Página não expira**; o de usuário dura ~60 dias (só é usado para renovar). **Não liga a publicação.**

### 12.2 Threads (opcional)
O Threads usa um app **à parte** dentro do mesmo painel de desenvolvedor.
1. No painel do app, adicione o caso de uso **Acessar a API do Threads**. Em *Funções do app → Funções*, adicione a sua conta como **Testador do Threads** e **aceite o convite** no aplicativo do Threads (*Configurações → Conta → Permissões do site → Convites*).
2. Em *Configurações do app do Threads*, copie a **Chave secreta do app do Threads** e gere um token no **Gerador de token de usuário** com `threads_basic` e `threads_content_publish`.
3. No servidor:
```bash
venv/bin/python ferramentas/threads_conectar.py
```
Ele confere o token, troca por um de **longa duração (~60 dias)** e grava `THREADS_APP_SECRET` e `THREADS_TOKEN` (e `data/threads_token.txt`). Depois disso o robô **renova sozinho todo domingo às 4h**. Para postar no Threads, ligue `THREADS_ENABLED=true` (passo 12.5).

### 12.3 YouTube (Shorts automáticos; opcional)
1. Em `console.cloud.google.com`: crie um **projeto** → *APIs e serviços → Biblioteca* → ative **YouTube Data API v3**.
2. *Tela de consentimento OAuth*: tipo **Externo**, preencha o mínimo e adicione a sua conta como usuário de teste. Depois clique em **Publicar app** (modo *produção*). **Importante:** em modo *teste* o acesso **expira em 7 dias** e o robô para de enviar. Com o app não verificado, o Google mostra o aviso "app não verificado": clique em *Avançado → Continuar* (é o seu próprio app).
3. *Credenciais → Criar credenciais → ID do cliente OAuth* → tipo **App para computador**. Baixe o JSON e salve no servidor como `/opt/promobot/data/youtube/youtube_client.json` (`mkdir -p data/youtube` antes; `chmod 600`).
4. **No SEU computador** (que tem navegador), abra o túnel e deixe a janela aberta:
```bash
ssh -L 8765:127.0.0.1:8765 promobot@IP-DO-SERVIDOR
```
5. Nessa mesma sessão SSH (no servidor):
```bash
cd /opt/promobot && venv/bin/python ferramentas/youtube_conectar.py
```
Ele mostra um **link**: abra no navegador do seu computador, entre na conta **dona do canal** e autorize. O Google devolve para `127.0.0.1:8765` (que o túnel leva ao servidor) e o script grava `data/youtube/youtube_token.json`.
- As permissões são só `youtube.upload` e `youtube.readonly`: o robô **não consegue apagar nem editar** vídeos.
- O robô só envia **Shorts de Reels que estiverem na fila** (`08-conteudo-e-reels.md`); sem Reels prontos não há o que enviar.
- Se o YouTube deixar os envios sempre **privados**, é a regra para projetos de API **sem auditoria**: peça a auditoria do projeto à equipe de API do YouTube.

### 12.4 Conferir e ver a prévia (nada é publicado)
```bash
venv/bin/python ferramentas/social_verificar.py          # só leitura: Meta, Threads e YouTube
PYTHONPATH=/opt/promobot venv/bin/python ferramentas/social_previa.py   # gera um Story e um feed de exemplo em data/previa/
```
- `social_verificar.py` mostra `OK`/`FALHOU`/`nao configurado` por rede e confere as permissões do token. A opção `--escrita` faz um teste de escrita **seguro** (sobe uma foto **não publicada** na Página e apaga em seguida); use-a só se quiser ter certeza de que o token consegue postar.
- `social_previa.py` usa uma oferta recente (o robô precisa ter rodado algumas horas em simulação) e grava `data/previa/story-<id>.jpg` e `feed-<id>.jpg`. Copie para o seu computador (`scp`) e **aprove o visual**. Cores, nome e chamada (`BRAND_NAME`, `BRAND_COLOR`, `ACCENT_COLOR`, `SOCIAL_CTA`): `13-white-label.md`.

### 12.5 Ligar
No `.env`:
```text
CONTENT_ENABLED=true     # liga a AGENDA de conteúdo (sem isto nada abaixo roda)
SOCIAL_ENABLED=true      # Stories no Instagram e na Página
THREADS_ENABLED=true     # só se fez o 12.2
```
`sudo systemctl restart promobot-bot`. O padrão é **4 Stories por dia** com a melhor oferta (`SOCIAL_STORY_TIMES`). O carrossel educativo (`EDU_ENABLED`) e os jogos da semana (`GAMES_ENABLED`) vêm **desligados** no kit — são do nicho do autor; ligue só se quiser. Feed com oferta: `FEED_VENDAS_ENABLED=true`. Se o servidor ficar desligado no horário, o robô **recupera sozinho** o post perdido (`catchup`).

**Limites da API (não são defeito do robô):** não dá para pôr link clicável em Story (a arte diz "link na bio"), nem fixar comentário, nem editar bio/foto de perfil/post fixado: faça à mão.

### 12.6 TikTok
**Não implementado.** O TikTok só publica publicamente por API depois de uma **auditoria** dele. Alternativas e referências: `07-redes-sociais.md`.

### 12.7 Validade dos acessos
Token da Página: não expira · token de usuário Meta: ~60 dias · Threads: ~60 dias, **renova sozinho** · YouTube: longo, se o app estiver *publicado* · o guardião avisa em `data/alertas.log` quando o token da Meta está perto de vencer. Se qualquer rede parar, rode `social_verificar.py` primeiro. Problemas comuns: `14-problemas-comuns.md`.

## 13. Checklist final
- [ ] `ctl status` mostra `whatsapp_conectado: true`
- [ ] posts aparecem no grupo com foto, preço e link do **seu** afiliado (abra o link e confira a etiqueta/ID)
- [ ] (se usar redes) `social_verificar.py` sem `FALHOU` e a prévia aprovada por você antes de `SOCIAL_ENABLED=true`
- [ ] backup gerou o primeiro arquivo
- [ ] reiniciar o equipamento (`sudo reboot`) → tudo volta sozinho
- [ ] senha de SSH desabilitada e firewall ativo (`11-seguranca-e-backup.md`)
