# Prompt MASTER — cole este texto no Claude Code antes de qualquer tarefa

> Como usar: abra o Claude Code **dentro da pasta do repositório** e cole o bloco abaixo como **primeira mensagem**. Depois cole o prompt da tarefa (`01…10`). O Claude lê `CLAUDE.md` e `docs/` sozinho.

```text
Você vai trabalhar no PromoBot Kit: um robô que coleta, filtra e publica ofertas de e-commerce em grupos de WhatsApp (e, opcionalmente, Telegram, Instagram, Facebook, Threads e YouTube), com o link de afiliado do DONO deste servidor. Ele roda 24/7 num servidor pequeno (mínimo: Dell Wyse 3040 — 4 núcleos a 1,44 GHz, 2 GB de RAM, 24 GB de armazenamento no total) e é leve de propósito (sem Docker, sem Celery, sem IA em tempo de execução).

LEIA ANTES DE FAZER QUALQUER COISA, nesta ordem:
1. CLAUDE.md (regras de trabalho e do projeto)
2. docs/00-LEIA-PRIMEIRO.md e docs/01a-servidor-e-requisitos.md
3. docs/02-arquitetura.md
4. o documento específico da tarefa (indicado no prompt da tarefa)
5. docs/16-decisoes-e-historia.md (decisões já tomadas e lições)

COMO VOCÊ DEVE TRABALHAR
- O dono pode não ser técnico: explique em português simples, passo a passo, e faça você mesmo tudo que puder.
- Mostre um PLANO curto antes de mudar algo e espere meu OK para: ações destrutivas (apagar dados, mexer em firewall/SSH, reinstalar), mudanças em contas/credenciais e qualquer tipo NOVO de post.
- NUNCA peça nem imprima segredos (senhas, tokens, chaves). Credenciais vão só no .env (chmod 600), gravadas por scripts que leem sem eco (src/ferramentas/gravar_*.sh). Nunca coloque segredo no Git.
- NUNCA burle captcha nem anti-bot. Prefira APIs oficiais. Respeite os termos de cada programa de afiliado (ex.: Awin/KaBuM/Samsung: nunca cupom de terceiros).
- Foto do post só do próprio anúncio. Só afirme fatos que o robô sabe (desconto calculado, histórico, cupom). Todo post de oferta leva #Anuncio.
- Faça BACKUP do arquivo antes de alterar em produção (cp x x.bak_AAAAMMDD). Rode os testes antes e depois (PYTHONPATH=. venv/bin/python -m pytest -q tests). Alguns testes dependem do .env e podem falhar: avise o que já falhava antes.
- Patches com regex ou barras invertidas: escreva o script num ARQUIVO e rode (heredoc/`bash -c` comem barras). Depois valide com grep e py_compile.
- Ao terminar: diga o que mudou, como desfazer, o que testou, e registre decisões em docs/16-decisoes-e-historia.md.
- Se algo estiver ambíguo, pergunte UMA vez, objetivamente, e proponha a opção que você recomenda.

COMECE ASSIM (sem alterar nada)
1. Pergunte onde o robô está (este computador ou um servidor via SSH) e o estado dele (já instalado? em simulação? no ar?).
2. Se estiver instalado, rode: ctl status, ctl diag, ctl alertas 20 e resuma em 5 linhas.
3. Pergunte qual tarefa fazer (ou use o prompt de tarefa que eu colar a seguir).
```

## Como pedir cada tarefa
| Tarefa | Prompt |
|---|---|
| Instalar do zero num servidor | `01-instalar-do-zero.md` |
| Configurar contas de afiliado | `02-configurar-afiliados.md` |
| Conectar o WhatsApp | `03-conectar-whatsapp.md` |
| Ligar Instagram/Facebook/Threads/YouTube/TikTok | `04-redes-sociais.md` |
| Montar a fábrica de Reels no PC | `05-pipeline-de-reels-no-pc.md` |
| Trocar a marca | `06-whitelabel.md` |
| Mudar de nicho | `07-novo-nicho.md` |
| Diagnóstico e manutenção | `08-diagnostico-e-manutencao.md` |
| Novo coletor/fonte | `09-novos-coletores.md` |
| Revisão de segurança | `10-revisao-de-seguranca.md` |
