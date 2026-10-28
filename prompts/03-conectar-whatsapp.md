# 03 — Conectar o WhatsApp

**Leia antes:** `docs/06-grupos-whatsapp-telegram.md`, `docs/12-riscos-e-termos.md` (seção 1).

```text
TAREFA: conectar o WhatsApp ao robô e fazer o primeiro post REAL de teste, com o menor risco possível.

ANTES DE COMEÇAR, CONFIRME COMIGO (uma pergunta de cada vez)
1. Tenho um número DEDICADO ao robô? (se for o pessoal, avise do risco e recomende um chip só dele)
2. Entendi que o conector é NÃO OFICIAL e que existe risco de bloqueio? (explique em 3 linhas e peça um "entendi")
3. Qual é o nome EXATO do grupo? O número do robô é administrador? O grupo está como "só admins enviam"?

PASSOS
1. Suba promobot-wa e gere o código de pareamento (GET /pair?number=55...). Me diga em que tela do celular digitar.
2. Confirme /status connected:true e liste /groups. Mostre só o nome e o id do grupo certo.
3. Preencha WHATSAPP_GROUP_NAME e WHATSAPP_NUMBER no .env (sem imprimir o resto do arquivo).
4. Configure o ritmo conservador na PRIMEIRA SEMANA: DAILY_POST_LIMIT=30, intervalos padrão, horário ativo padrão. Deixe CONVITE_ENABLED=false.
5. Gere UM post real de teste com ctl postar 1 (explique que isso é uma ação). Me peça para conferir no grupo: foto, preço, link e #Anuncio.
6. Só depois de eu confirmar, tire SIMULATE_POSTS e reinicie o robô. Acompanhe a primeira hora (ctl status, alertas).
7. Configure o vigia (guardião) e verifique que o aviso de desconexão chega em data/alertas.log.

CRITÉRIOS DE ACEITAÇÃO
- [ ] posts chegam ao grupo com intervalos variados
- [ ] derrubar o promobot-wa e subir de novo reconecta sozinho
- [ ] a sessão (data/wa) entra no backup e tem permissão 700
- [ ] nenhum código de pareamento ou chave ficou salvo fora do necessário

NÃO FAÇA: disparos em massa, convidar contatos automaticamente, aumentar o limite diário sem eu pedir, usar o número pessoal sem aviso.
```
