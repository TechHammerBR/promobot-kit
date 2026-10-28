# PromoBot Kit (V0)

Robô que **monitora, filtra, enriquece e publica ofertas e cupons** de e-commerce em grupos de WhatsApp (e, opcionalmente, Telegram, Instagram, Facebook, Threads e YouTube), com **link de afiliado do próprio dono**. Roda 24/7 num computador pequeno e barato (testado num Dell Wyse 3040: Atom, 2 GB de RAM) e foi construído com a ajuda do **Claude Code**.

> ## ⚠️ Você precisa de um **servidor**
> O robô tem que ficar **ligado 24 h por dia**: não roda no seu PC/notebook do dia a dia nem no celular. O **mínimo** é a configuração do servidor onde ele roda hoje, um **Dell Wyse 3040**: processador de **4 núcleos a 1,44 GHz** (turbo até 1,92 GHz; Intel Atom x5-Z8350), **2 GB de RAM**, **24 GB de armazenamento no total**, rede cabeada e Debian 13. Detalhes, medições reais e alternativas em [`docs/01a-servidor-e-requisitos.md`](docs/01a-servidor-e-requisitos.md).

> **Status: V0 em fase de testes** (distribuição gratuita para um grupo pequeno; ainda não está à venda). Veja `docs/17-distribuicao-e-testes.md`.
>
> **V0 (primeira versão para compartilhar).** O código é o mesmo que roda em produção, mas foi limpo dos dados pessoais do autor. A documentação foi escrita a partir do servidor real. **A instalação foi testada do zero numa VM com o mínimo do Wyse** (28/10/2026; veja `docs/18-teste-de-instalacao.md`). Ainda **não** foi testado o pareamento do WhatsApp (precisa de número real) nem o login do Mercado Livre. Leia `docs/00-LEIA-PRIMEIRO.md` antes de começar.

## O que ele faz

1. **Coleta** ofertas a cada 15 minutos (Mercado Livre, Shopee, AliExpress, e fontes de apoio como Pelando) e cupons com código.
2. **Filtra**: desconto mínimo, marcas confiáveis, preço histórico (desconto falso), repetição, foto boa (sem IA, só medidas da imagem), categoria (tecnologia e casa).
3. **Converte o link** para o link de afiliado do dono (ML via navegador logado; Shopee e AliExpress via API oficial).
4. **Publica** com ritmo humano: intervalos aleatórios, horário ativo, teto diário, pausa na madrugada. Cada post tem foto, preço, desconto, cupom sugerido e link.
5. **Cuida de si mesmo**: guardião religa o que cair, backup diário, alertas, recupera agendamentos perdidos após queda de energia.
6. **Conteúdo extra (opcional)**: Stories, feed, carrossel educativo, jogos grátis da semana, notícias, Reels prontos entregues por uma fila, Shorts no YouTube agendados na plataforma.

## O que NÃO vem aqui

- Suas contas, chaves e grupos (cada pessoa que for testar usa as suas). Veja `.env.example`.
- Logos, artes e textos de marca do autor (`src/app/assets/LEIA-ME.md` explica o que colocar).
- O estúdio de vídeo que roda num PC potente (gerador de Reels, voz clonada). A **fila** que recebe os vídeos prontos está aqui; a fábrica não. Veja `docs/08-conteudo-e-reels.md` e `prompts/05-pipeline-de-reels-no-pc.md`.
- Garantia de resultado de vendas ou de que contas de terceiros (WhatsApp, Meta, afiliados) não sofrerão bloqueio. Leia `docs/12-riscos-e-termos.md`.

## Estrutura do repositório

```text
README.md                 este arquivo
CLAUDE.md                 instruções para o Claude Code que for trabalhar neste projeto
.env.example              todas as configurações (gerado do código)
docs/                     guias passo a passo (comece pelo 00)
  referencia/             tabelas geradas do código: configurações, módulos, comandos
prompts/                  prompts prontos para mandar ao Claude (construir, configurar, manter)
src/
  app/                    o robô (Python 3.12+)
  wa/                     conector do WhatsApp (Node, não oficial, só ENVIA)
  linkgen/                navegador logado que gera links de afiliado do Mercado Livre
  ferramentas/               scripts de operação (backup, vigias, status web, whitelabel)
  tests/                  testes automáticos
deploy/systemd/           serviços que mantêm tudo no ar
```

## Começo rápido (resumo)

1. Leia `docs/00-LEIA-PRIMEIRO.md` (custos, riscos, o que você precisa ter).
2. Prepare a máquina: `docs/03-instalacao-passo-a-passo.md`.
3. Copie `.env.example` para `.env` e preencha **só o essencial** (`docs/04-configuracao.md`). Comece em **modo simulação**.
4. Conecte o WhatsApp (`docs/06-grupos-whatsapp-telegram.md`) e as contas de afiliado (`docs/05-afiliados.md`).
5. Deixe rodando em simulação por 1 dia, leia `data/outbox.log` e só então ligue a publicação de verdade.
6. Para ajustar a marca: `docs/13-white-label.md`.

## Usando com o Claude Code

Abra a pasta do projeto no Claude Code e cole o prompt de `prompts/00-MASTER-contexto.md`. Ele explica o projeto, as regras e como pedir cada tarefa. Os demais prompts da pasta `prompts/` cobrem instalação, afiliados, WhatsApp, redes sociais, white-label, novo nicho e manutenção.

## Licença

**Todos os direitos reservados** (ver `LICENSE`). Este repositório é privado e compartilhado por convite. Não redistribua sem autorização por escrito do autor.
