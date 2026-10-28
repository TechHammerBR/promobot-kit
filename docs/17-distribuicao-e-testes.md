# 17 — Distribuição para testes (fase atual)

> **Fase atual: testes gratuitos com um grupo pequeno de pessoas de confiança. Não há venda.** Se der muito certo, aí sim pensamos em vender (última seção).

## Objetivo dos testes
Descobrir **onde as pessoas travam** ao instalar e usar, antes de abrir para mais gente. Cada dificuldade vira melhoria nos guias ou no código.

## Para quem vai testar (leia isto primeiro)
1. Leia `00-LEIA-PRIMEIRO.md` e `01a-servidor-e-requisitos.md`: **você precisa de um servidor ligado 24 h** (mínimo: 4 núcleos a 1,44 GHz, 2 GB de RAM, 24 GB de armazenamento total).
2. Siga `03-instalacao-passo-a-passo.md` em **modo simulação**. Só ligue a publicação real depois de 1 dia lendo `data/outbox.log`.
3. Use **suas próprias contas** e chaves. Ninguém precisa (nem deve) mandar chave ou senha para o autor.
4. Anote **tudo que travou**, mesmo que pareça bobo: um comando que falhou, um termo confuso, uma tela diferente.
5. Mande o retorno (veja abaixo).
6. **Risco do WhatsApp:** leia `12-riscos-e-termos.md`. Use número dedicado e comece devagar.

Dica: o `prompts/00-MASTER-contexto.md` + `prompts/01-instalar-do-zero.md` fazem o Claude Code te guiar na instalação.

## Como dar retorno
Abra um **Issue** no repositório (aba *Issues* → *New issue* → modelo "Relato de teste") ou mande por mensagem. Inclua:
- Em que passo você estava (número do `03`).
- O que esperava e o que aconteceu (cole a **mensagem de erro**, sem chaves).
- Seu servidor (processador, RAM, armazenamento, sistema).
- Quanto tempo levou até o robô rodar em simulação.

## Para o autor: como distribuir
- Repositório **privado**; convide cada pessoa em *Settings → Collaborators* (permissão de leitura basta; escrita só para quem for ajudar a corrigir).
- Entregue junto: link do repo, o aviso de risco (`12`) e o que se espera do teste.
- **Nunca** guarde senhas, chaves ou acesso ao servidor de ninguém.
- Registre as versões: `git tag v0.3` ao distribuir; a cada correção importante, a próxima (`v0.4`…) e uma linha no `CHANGELOG.md`
- Antes de cada atualização: `python -I sanitiza.py` e `gera_referencias.py` (verificação de dados pessoais) e só então `git push`.

## Roteiro do teste (checklist para quem testa)
- [ ] Servidor atende o mínimo (`01a`)
- [ ] Sistema instalado e acesso por SSH com chave (`03`, `11`)
- [ ] Pacotes e ambiente Python instalados sem erro
- [ ] `python -m app.main --once` gera posts em `data/outbox.log` (simulação)
- [ ] Testes automáticos rodam (`pytest`); falhas esperadas anotadas
- [ ] Serviços do systemd sobem e voltam sozinhos depois de reiniciar
- [ ] Backup gera arquivo e a restauração funciona
- [ ] Afiliados ligados (pelo menos Shopee) e link com **o seu** identificador
- [ ] WhatsApp pareado e 1 post real de teste no **seu** grupo
- [ ] Dúvidas e travas anotadas e enviadas

## O que o autor vai medir
- Quantas pessoas chegaram ao "rodando em simulação" e em quanto tempo.
- Em que passo cada uma travou.
- Quais erros se repetem (viram correção na documentação ou no código).
- Se alguém teve bloqueio de conta (WhatsApp/afiliado) e em que condições.
- O que as pessoas **pediram** que não existe (vira roadmap, `15`).

## Regras da fase de testes
- Gratuito, sem garantia e sem suporte garantido; o autor ajuda **na medida do possível**.
- Cada pessoa é responsável por **suas** contas e pelo cumprimento das regras de cada plataforma.
- Não redistribuir o kit (o `LICENSE` é provisório: todos os direitos reservados).
- Não publicar prints com chaves, números ou links de convite privados.

## Depois dos testes (futuro: possível venda)
Só se os testes forem bem, o autor decide **se e como** vender. Pontos a resolver nessa hora (não agora):
1. **Licença e contrato** definitivos, com orientação jurídica; isenção sobre contas de terceiros (WhatsApp, afiliados) e sobre resultado.
2. **Modelo:** kit com documentação, kit + instalação assistida, ou servidor pronto; suporte opcional.
3. **Preço** definido pelo tempo e risco assumidos, testado com poucos primeiros usuários.
4. **Instalação testada do zero** na mesma versão que será entregue (o laboratório em VM do autor serve para isso).
5. Termo de risco do WhatsApp **assinado**.
6. Limites claros de suporte.
Até lá, **nada disto se aplica**: o kit é só para teste.
