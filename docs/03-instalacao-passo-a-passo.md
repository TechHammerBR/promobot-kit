# 03 — Instalação passo a passo

> **Aviso V0:** estes passos foram escritos a partir de um servidor que já funciona (Debian 13, Python 3.13, Node 20, Dell Wyse 3040). **Ainda não foram repetidos numa máquina limpa.** Se algo não bater, use o prompt `prompts/01-instalar-do-zero.md` para o Claude Code adaptar ao seu caso — e depois corrija este arquivo.

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
```

## 8. Conectar o WhatsApp
Siga `06-grupos-whatsapp-telegram.md` (pareamento por código de 8 caracteres ou QR).

## 9. Conectar as contas de afiliado
- Shopee e AliExpress: chaves no `.env` (`05-afiliados.md`).
- Mercado Livre: login único no navegador do `linkgen` por túnel SSH (`05-afiliados.md`).

## 10. Rotinas automáticas (cron)
Como `root` ou com `sudo crontab -e`, ajuste os caminhos e agende (exemplos reais do autor):
```cron
40 3 * * *   /opt/promobot/backup.sh                         # backup diário do banco/.env/sessão
*/5 * * * *  /opt/promobot/ferramentas/vigia_recursos.sh           # memória/CPU
*/5 * * * *  /opt/promobot/ferramentas/vigia_armazenamento.sh      # disco
20 4 * * *   /opt/promobot/ferramentas/manutencao.sh               # enxuga banco e logs (para/religa o robô)
```
Adapte `backup.sh` ao seu destino de backup (`DEST=`). Os scripts leem o usuário em `DONO=` (padrão `promobot`).

## 11. Ligar de verdade (depois de 1 dia em simulação)
1. Preencha `WHATSAPP_GROUP_NAME` (nome exato do grupo) e `WHATSAPP_NUMBER`.
2. Tire `SIMULATE_POSTS`.
3. `sudo systemctl restart promobot-bot`.
4. Acompanhe: `ctl status` e `ctl alertas 20` na primeira hora.

## 12. Checklist final
- [ ] `ctl status` mostra `whatsapp_conectado: true`
- [ ] posts aparecem no grupo com foto, preço e link do **seu** afiliado (abra o link e confira a etiqueta/ID)
- [ ] backup gerou o primeiro arquivo
- [ ] reiniciar o equipamento (`sudo reboot`) → tudo volta sozinho
- [ ] senha de SSH desabilitada e firewall ativo (`11-seguranca-e-backup.md`)
