# 02 — Configurar contas de afiliado

**Leia antes:** `docs/05-afiliados.md`, `docs/12-riscos-e-termos.md` (seção 2).

```text
TAREFA: conectar minhas contas de afiliado ao robô, uma loja por vez, seguindo docs/05-afiliados.md. Eu faço os cadastros e logins; você orienta e configura.

ORDEM SUGERIDA: Shopee (mais simples) → AliExpress → Mercado Livre (navegador logado) → Awin/KaBuM (opcional).

PARA CADA LOJA
1. Me diga EXATAMENTE onde clicar para criar a conta de afiliado/obter a chave (com o nome atual dos menus; se não tiver certeza, diga que pode ter mudado e peça um print).
2. Grave as chaves no .env SEM eu colar no chat: use src/ferramentas/gravar_*.sh (ou crie um script igual que leia com read -s). Nunca imprima a chave.
3. Teste a conexão com uma chamada simples e mostre só o resultado (sem a chave).
4. Rode uma coleta (--once) e mostre 2 ofertas dessa loja com o MEU link; peça que eu clique e confirme no painel da loja.

MERCADO LIVRE (cuidado)
- Guie o login único pelo navegador do linkgen (túnel SSH + VNC, docs/05). A porta 6080 fica só em 127.0.0.1.
- Teste: curl http://127.0.0.1:8000/health deve dar logged_in:true; gere 1 link meli.la de teste.
- Se aparecer reCAPTCHA, NÃO tente burlar: me peça para marcar a caixinha no VNC.
- Pergunte quantas etiquetas eu criei e preencha ML_TAG_TECH / ML_TAG_LAR.

AWIN/KABUM
- Preserve a regra: nunca publicar cupom de terceiros nem oferta dependente de cupom nessas lojas (NO_OUTSIDE_COUPON_HOSTS).

CRITÉRIOS DE ACEITAÇÃO
- [ ] cada loja ligada gera link com MEU identificador
- [ ] nenhum segredo apareceu no chat, nos logs ou no Git
- [ ] o robô continua em simulação até eu aprovar

NÃO FAÇA: clicar nos meus próprios links em loop, criar contas por mim, compartilhar a conta com terceiros, remover as proteções de programa.
```
