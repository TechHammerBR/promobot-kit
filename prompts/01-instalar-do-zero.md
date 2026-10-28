# 01 — Instalar do zero num servidor

**Leia antes:** `docs/01a-servidor-e-requisitos.md`, `docs/03-instalacao-passo-a-passo.md`, `docs/04-configuracao.md`.

```text
TAREFA: instalar o PromoBot Kit do zero no meu servidor, em MODO SIMULAÇÃO, seguindo docs/03-instalacao-passo-a-passo.md.

DADOS QUE VOU TE DAR (pergunte o que faltar, um item por vez):
- endereço do servidor (IP) e usuário SSH; ou diga se é este mesmo computador
- sistema operacional e versão (esperado: Debian 13 ou Ubuntu 24.04+, sem interface gráfica)
- processador (núcleos e GHz), memória RAM e armazenamento TOTAL (mínimo aceito: 4 núcleos a 1,44 GHz, 2 GB de RAM, 24 GB de armazenamento no total)

O QUE FAZER
1. Verifique o servidor contra o mínimo (docs/01a). Se estiver abaixo, PARE e me diga o que falta.
2. Crie o usuário de serviço, a pasta /opt/promobot e instale os pacotes do sistema (docs/03, passo 2).
3. Copie src/ para /opt/promobot, crie o venv, instale requirements.lite.txt e o conector (npm install --omit=dev em wa/).
4. Crie o .env a partir de .env.example com chmod 600. Deixe SIMULATE_POSTS=true e WHATSAPP_GROUP_NAME vazio. NÃO peça chaves agora.
5. Rode: python -m app.main --once, depois ctl status e tail data/outbox.log. Mostre 3 posts simulados.
6. Rode os testes e liste o que falha (e se já falhava por depender do .env).
7. Instale as unidades do systemd (deploy/systemd), ative promobot-wa, promobot-bot e promobot-status. Confirme que sobem sozinhas depois de um reboot.
8. Configure cron: backup 03:40, vigias, manutenção (docs/03, passo 10), ajustando usuário e caminhos.
9. Endureça o acesso (docs/11): chave SSH, senha desabilitada, ufw só com SSH, fail2ban. PEÇA minha confirmação antes de mexer em SSH/firewall e mantenha uma sessão aberta para não me trancar fora.

CRITÉRIOS DE ACEITAÇÃO (marque cada um e mostre a prova)
- [ ] ctl status responde e mostra ofertas na fila
- [ ] outbox.log tem posts com foto, preço e link
- [ ] reiniciar o servidor sobe tudo sozinho
- [ ] backup gerou um arquivo que abre (tar tzf)
- [ ] nenhum segredo foi impresso no chat nem salvo fora do .env

NÃO FAÇA: ligar publicação real, pedir tokens, abrir portas na internet, instalar Docker, usar conteúdo do repositório que não seja deste kit.
ENTREGA: relatório curto com o que foi instalado, o que falhou e os próximos passos (afiliados, WhatsApp).
```
