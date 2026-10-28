# 11 — Segurança e backup

O servidor guarda **chaves de afiliado, tokens de redes sociais e a sessão do seu WhatsApp**. Quem tiver acesso a ele tem acesso a tudo isso. Trate como um cofre.

## Acesso ao servidor (SSH)
1. Entre sempre com **chave SSH**, não senha. No seu PC: `ssh-keygen -t ed25519`; copie a chave pública com `ssh-copy-id promobot@IP`.
2. Depois de testar que a chave funciona, **desligue a senha** e o login do root em `/etc/ssh/sshd_config`:
   ```text
   PasswordAuthentication no
   PermitRootLogin no
   X11Forwarding no
   ```
   `sudo systemctl restart ssh` (mantenha uma sessão aberta enquanto testa em outra, para não se trancar para fora).
3. **Firewall:** só o SSH aberto.
   ```bash
   sudo apt install -y ufw fail2ban unattended-upgrades
   sudo ufw default deny incoming && sudo ufw allow OpenSSH && sudo ufw enable
   ```
   `fail2ban` bane IPs que erram a senha/chave várias vezes; `unattended-upgrades` aplica correções de segurança sozinho.
4. **Nenhuma porta do robô fica aberta**: `wa` (3000), `linkgen` (8000), VNC (6080) escutam só em `127.0.0.1`. A página de status (8088) é só para a rede local — não faça redirecionamento de porta no roteador.
5. Acesso de fora de casa: use uma VPN (ex.: Tailscale), nunca abra a porta do SSH para a internet.

## Segredos
- Ficam **somente** no `/opt/promobot/.env` (`chmod 600`) e em `data/youtube/` (`chmod 600`).
- **Nunca** no Git, no chat, em captura de tela, em e-mail. O `.gitignore` do kit bloqueia `.env`, `data/`, tokens e chaves.
- Para gravar uma chave sem aparecer na tela: `ferramentas/gravar_meta.sh`, `ferramentas/gravar_awin.sh` (leem com `read -s`).
- Se um segredo **vazou** (colado em chat, commitado, foto de tela): **revogue e gere outro** na hora. Apagar a mensagem não basta.
- Depois de entregar o servidor ou o repositório a alguém, troque todas as chaves.

## O que NUNCA entra no repositório
`.env`, `data/` (banco, sessão do WhatsApp, estado), `youtube_token.json`, `youtube_client.json`, qualquer `*token*.txt`, backups, logs, fotos de clientes, e arquivos com telefone/CNPJ/links de convite pessoais. Antes de cada `git push`, rode a verificação de dados pessoais (`sanitiza.py`/`verifica`, ou um `git grep` pelos seus dados).

## Backup (o que e como)
| O que | Onde |
|---|---|
| banco `promobot.db` (cópia consistente via `sqlite3 .backup`) | `backup.sh` às 03:40 |
| `.env` | idem (o backup contém segredos → **guarde-o protegido**) |
| sessão do WhatsApp `data/wa` | idem |
| estados (`control.json`, índices, `schedule_state.json`) | idem |
- Destino: pendrive/SSD montado em `/srv/backup` (padrão do autor). Mantém 14 dias. Sem o disco, guarda só 3 no interno.
- **Cópia fora do servidor:** de tempos em tempos copie o backup mais recente para outro lugar (outro disco, nuvem **com senha/criptografia**). Se a casa pegar fogo ou o equipamento queimar, o pendrive vai junto.
- Backup **contém segredos**: não envie por e-mail nem suba para um repositório.

### Restaurar
```bash
sudo systemctl stop promobot-bot promobot-wa
cd /opt/promobot
tar xzf /srv/backup/promobot/promobot-AAAAMMDD-HHMM.tar.gz        # traz .env e data/
cp promobot.db data/promobot.db && rm promobot.db                  # o banco vem na raiz do tar
sudo systemctl start promobot-wa promobot-bot
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl status
```
**Teste a restauração** numa máquina de teste (ou na VM) antes de precisar dela.

## Imagem do sistema
O autor também faz uma imagem semanal do disco interno (`ferramentas/imagem_wyse.sh`) e um espelho diário (`espelho.sh`). Opcional, mas salva horas se o disco morrer.

## Atualizações do sistema
- `unattended-upgrades` cuida das correções de segurança.
- Atualizações grandes (troca de versão do Debian) **faça com calma, fora do horário de posts**, com backup recente.

## Disco e memória cheios
Os vigias avisam em `alertas.log` (disco > 85%, memória baixa). A manutenção noturna enxuga o banco e os logs. Se o disco interno é pequeno (8 GB), mantenha os dados grandes (cache, vídeos) no pendrive/SSD externo.

## Privacidade (LGPD)
- O robô **não coleta dados dos membros** dos grupos. O conector do WhatsApp só envia; não lê mensagens.
- Se você guardar contatos (função de convite), isso é dado pessoal: peça consentimento e proteja o arquivo (permissão 600/700).
- Fotos e vídeos de **clientes** (serviços da loja) só com autorização.
