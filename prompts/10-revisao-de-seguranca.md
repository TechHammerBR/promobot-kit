# 10 — Revisão de segurança

**Leia antes:** `docs/11-seguranca-e-backup.md`, `docs/12-riscos-e-termos.md`.

```text
TAREFA: fazer uma revisão de segurança do servidor e do repositório, SEM alterar nada até eu aprovar o plano.

SERVIDOR (somente leitura)
1. SSH: PasswordAuthentication, PermitRootLogin, X11Forwarding; chaves autorizadas; fail2ban; ufw (só OpenSSH aberto?).
2. Portas em escuta (ss -tlnp): wa 3000, linkgen 8000, VNC 6080 precisam estar só em 127.0.0.1; status 8088 só rede local.
3. Permissões: .env 600; data/wa 700; data/youtube 600; nenhum segredo em histórico de shell (history), crontab ou logs (grep por padrões de token SEM imprimir o valor).
4. Atualizações automáticas (unattended-upgrades) e espaço em disco.
5. Backup: existe? abre? contém segredos e está protegido? há cópia FORA do servidor? teste uma restauração numa pasta temporária.

REPOSITÓRIO
1. git grep por padrões de segredo (tokens de Meta/Google/Telegram, 'sk-', 'ghp_', chaves privadas, telefones, e-mails, CNPJ, links chat.whatsapp.com reais).
2. Confirme .gitignore (.env, data/, tokens, backups) e que git log não tem segredo antigo (git log -p | grep). Se tiver, recomende rotação de chaves e limpeza do histórico.
3. Dependências: pip/npm com vulnerabilidades conhecidas (pip list --outdated; npm audit) — só relate.

ENTREGA: tabela (item, risco alto/médio/baixo, evidência SEM mostrar segredo, correção sugerida). Espere meu OK antes de aplicar. Qualquer segredo encontrado: me diga ONDE está (arquivo:linha) e recomende revogar e gerar outro — não imprima o valor.
```
