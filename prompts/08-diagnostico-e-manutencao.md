# 08 — Diagnóstico e manutenção

**Leia antes:** `docs/09-operacao.md`, `docs/14-problemas-comuns.md`.

```text
TAREFA: diagnosticar o robô e corrigir o que for preciso. Sintoma que estou vendo: <descreva>.

ROTEIRO (SÓ LEITURA primeiro; não mude nada até entender)
1. ctl status, ctl diag, ctl alertas 30. Resuma em 5 linhas.
2. systemctl is-active promobot-bot promobot-wa promobot-linkgen promobot-status; uptime -s (houve reinício/queda de energia?); df -h; free -m.
3. journalctl -u promobot-bot --since "-2h" filtrando erros; conectividade (DNS/internet); WhatsApp (curl 127.0.0.1:3000/status); ML (curl 127.0.0.1:8000/health).
4. Compare com docs/14-problemas-comuns.md e diga a causa PROVÁVEL e a evidência.
5. Proponha a correção MAIS SIMPLES. Mostre o plano e espere meu OK se for: reiniciar algo que pode derrubar o WhatsApp, mexer em .env, em código, em firewall/SSH, apagar dados.

AO CORRIGIR
- Backup do arquivo antes (cp x x.bak_AAAAMMDD). Teste antes/depois (pytest). Reinicie só o necessário.
- Para ajuste de regra (foto, cupom, ritmo): meça com dados reais das últimas 24 h antes de concluir e depois confirme o efeito.
- Registre em docs/16 e diga como desfazer.

ATENÇÃO
- ctl postar / cupons / pausar são AÇÕES (mudam o que vai ao ar): não rode "para testar".
- Captcha do ML: NÃO burlar; me peça para resolver no VNC ou espere.
- Nunca imprima o .env nem tokens.

ENTREGA: causa, o que fez, como verificou, como desfazer, e se algo ficou pendente.
```
