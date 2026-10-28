# 15 — Roadmap e ideias

O que está **pronto**, o que está **pela metade** e o que é **ideia**. Use como lista de pedidos para o Claude (`prompts/`).

## Pronto (V0)
- Coleta ML/Shopee/AliExpress/Pelando/Promobit e cupons com código
- Regras (desconto, repetição, histórico de preço, mix de lojas, marca confiável)
- Link de afiliado (ML via navegador, Shopee/Ali via API, Awin/KaBuM)
- Publicação no WhatsApp com ritmo humano; dois canais (tech e casa)
- Validação de foto sem IA, cupom sugerido relevante, chamada v2 dos posts
- Guardião/vigias/manutenção/backup; recuperação após queda (`catchup`)
- Conteúdo: Stories, feed, carrossel educativo, jogos, novidades; fila de Reels; Shorts agendados no YouTube

## Pela metade / limitações conhecidas
- **Instalação do zero ainda não repetida** numa máquina limpa (este V0 inclui um teste em VM; veja `16`).
- **TikTok:** não implementado; depende de auditoria (`07`).
- **Estúdio de vídeo** (PC): não incluído.
- **White-label** exige trabalho manual na camada 3 (`13`): serviços da loja e identidade visual estão no código.
- **Painel web** de gestão: só uma página de status somente leitura.
- **Uma pessoa por servidor:** não há multiusuário.

## Ideias ordenadas por valor
1. **Painel web** simples (login) para ver fila, pausar, mudar desconto/limite, ver alertas — hoje só por linha de comando.
2. **Instalador** (`install.sh`) que faz os passos de `03` sozinho e valida (hoje é manual).
3. **Multiusuário:** um servidor atendendo vários grupos/contas com isolamento (exige banco por cliente ou PostgreSQL com `tenant_id`).
4. **Cupons por categoria** com mais fontes (além do Pelando) e confirmação real de aplicabilidade quando a loja expõe.
5. **Estúdio de Reels como produto separado** (PC) com gerador de capas, legendas e trilhas.
6. **TikTok** por rascunhos (`video.upload`) ou integração com ferramenta de agendamento.
7. **API oficial do WhatsApp Business** como alternativa ao conector não oficial, para quem não aceita o risco.
8. **Relatório semanal** de desempenho (cliques por etiqueta, comissão estimada) puxando dos painéis de afiliado onde houver API.
9. **Detector de preço falso** mais forte com histórico longo e comparação entre lojas.
10. **Modo Docker/Compose** opcional para quem tem máquina maior.

## Como transformar uma ideia em tarefa
Abra o Claude Code no repositório, cole `prompts/00-MASTER-contexto.md` e peça: "Implemente a ideia N do `docs/15-roadmap-e-ideias.md`; mostre o plano, espere meu OK, faça backup, rode os testes e registre a decisão em `docs/16-decisoes-e-historia.md`."
