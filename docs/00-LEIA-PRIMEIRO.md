# 00 — Leia primeiro

Este guia é curto de propósito. Ele responde: **vale a pena, quanto custa, quanto tempo leva, o que pode dar errado e o que você precisa ter antes de começar.**

## O que você está recebendo
Um robô que publica ofertas com o **seu** link de afiliado em grupos de WhatsApp (e opcionalmente outras redes), 24 horas por dia, num computador pequeno. É o mesmo robô que roda em produção para o autor, sem os dados pessoais dele. É um **kit em fase de testes**, não um serviço pronto: você instala no seu equipamento e usa as suas contas. Seu retorno ajuda a melhorar os guias (`17-distribuicao-e-testes.md`).

## Quanto custa de verdade
| Item | Custo aproximado |
|---|---|
| Computador pequeno (ex.: Dell Wyse 3040 usado, ou qualquer mini PC/Raspberry com 2 GB+) | R$ 150 a R$ 600 (uma vez) |
| Pendrive/SSD para backup e cache | R$ 40 a R$ 150 (uma vez) |
| Energia (consumo muito baixo; meça com um medidor de tomada) | poucos reais por mês |
| Contas de afiliado (Mercado Livre, Shopee, AliExpress) | **grátis** |
| Chip/número de WhatsApp para o robô (recomendado ter um número só dele) | R$ 15 a R$ 30 por mês (pré-pago) |
| IA local, Claude, APIs pagas | **zero no dia a dia**: nada precisa de IA em tempo de execução. O Claude Code é usado só para instalar e manter. |

## Quanto tempo leva
- Instalar e ver o robô rodando em **modo simulação**: algumas horas.
- Ter as contas de afiliado aprovadas: de 1 a 10 dias (depende de cada programa).
- Ver o grupo crescendo e gerando comissão: **semanas a meses**. O robô entrega conteúdo; audiência e conversão dependem de você.

## O que você precisa ter antes
1. **Um servidor** (computador Linux ligado 24/7, com internet estável). O mínimo é a configuração de um **Dell Wyse 3040**: 4 núcleos a 1,44 GHz, 2 GB de RAM, 24 GB de armazenamento no total e cabo de rede. Veja `01a-servidor-e-requisitos.md` e depois `03-instalacao-passo-a-passo.md`.
2. Conta de **afiliado** em pelo menos uma loja (Shopee é a mais simples; Mercado Livre exige o programa de afiliados ativo). `05-afiliados.md`.
3. Um **número de WhatsApp** e um **grupo** (ou comunidade) onde o robô vai postar. `06-grupos-whatsapp-telegram.md`.
4. Opcional: contas das redes sociais (Instagram profissional + Página do Facebook) e canal do YouTube. `07-redes-sociais.md`.
5. **Claude Code** instalado no seu computador, se quiser que ele faça a instalação com você. Os prompts estão em `prompts/`.

## Riscos que você precisa aceitar (resumo)
Leia `12-riscos-e-termos.md` inteiro. Em uma frase cada:
- **WhatsApp:** o conector é **não oficial**. Existe risco de a conta ser bloqueada. O robô reduz o risco (ritmo humano, teto diário), mas não o elimina. Use um número só para o robô, não o seu pessoal.
- **Afiliados:** cada programa tem regras (ex.: cupom de terceiros pode cancelar comissão). O robô já respeita as conhecidas, mas **você** é o responsável pela conta.
- **Fontes:** o robô não burla captcha. Quando uma loja bloqueia, a fonte pausa e você resolve à mão.
- **Resultado:** nada aqui garante vendas, seguidores ou renda.

## Como ler a documentação
| Quero… | Leia |
|---|---|
| Entender o que o robô faz | `01-visao-geral.md` |
| Saber **qual servidor comprar** e as specs mínimas | `01a-servidor-e-requisitos.md` |
| Entender como ele é por dentro | `02-arquitetura.md` |
| Instalar | `03-instalacao-passo-a-passo.md` |
| Saber o que preencher no `.env` | `04-configuracao.md` e `referencia/configuracoes.md` |
| Ligar Mercado Livre, Shopee, AliExpress | `05-afiliados.md` |
| Ligar WhatsApp e Telegram | `06-grupos-whatsapp-telegram.md` |
| Instagram, Facebook, Threads, YouTube | `07-redes-sociais.md` |
| Vídeos e conteúdo agendado | `08-conteudo-e-reels.md` |
| Operar no dia a dia | `09-operacao.md` |
| Entender as regras do robô | `10-regras-de-negocio.md` |
| Segurança e backup | `11-seguranca-e-backup.md` |
| Trocar a marca | `13-white-label.md` |
| Resolver um problema | `14-problemas-comuns.md` |
| Participar da fase de testes e dar retorno | `17-distribuicao-e-testes.md` |
| Ver o que já foi testado (VM) e os problemas achados | `18-teste-de-instalacao.md` |

## Glossário rápido
- **Afiliado:** você ganha comissão quando alguém compra por um link seu.
- **Link meli.la:** link curto de afiliado do Mercado Livre.
- **Modo simulação:** o robô faz tudo, mas em vez de enviar escreve em `data/outbox.log`.
- **Conector `wa`:** programa que fala com o WhatsApp (só envia).
- **`linkgen`:** navegador logado na sua conta do Mercado Livre que gera os links de afiliado.
- **Guardião / vigias:** scripts que checam se está tudo no ar e religam o que cair.
- **`ctl`:** comando para controlar o robô (status, pausar, postar…).
