# 17 — Comercial: como compartilhar ou vender este kit

> Este arquivo é para o **autor** (ou para quem for revender). Não é aconselhamento jurídico nem financeiro.

## O que existe para vender
Um **kit técnico** + **documentação** + **prompts** para o comprador (com o Claude Code) instalar e manter o robô no **servidor dele**, com **as contas dele**. Não é um SaaS: não há painel nem hospedagem sua.

## Modelos possíveis
| Modelo | O que entrega | Prós | Contras |
|---|---|---|---|
| **A. Kit + documentação** (autoatendimento) | repositório privado + docs + prompts | escala; baixo custo de suporte | comprador precisa de perfil técnico/curiosidade; mais dúvidas |
| **B. Kit + instalação remota** | A + sessão para instalar no servidor dele | mais valor percebido; menos desistência | seu tempo por cliente |
| **C. Servidor pronto** (você monta o mini PC e envia) | equipamento configurado; ele só liga e loga | experiência fácil | logística, hardware, garantia |
| **D. Assinatura de suporte/manutenção** | monitoramento, atualizações de regras, ajustes | renda recorrente | responsabilidade contínua; contas de terceiros |

Sugestão para começar: **A para validar** com poucas pessoas de confiança, depois **B** como produto principal.

## O que cobrar (referências, não promessas)
Defina pelo **tempo e risco** que você assume, não pela comissão do cliente. Exemplos de composição: preço do kit + taxa de instalação + mensalidade opcional de suporte. Pesquise o que o mercado de automação/afiliados cobra e teste com 3 a 5 clientes antes de fixar.

## Checklist de venda
- [ ] **Licença** definida (o `LICENSE` do V0 é provisório) e **contrato** com escopo, prazo, suporte, isenção de responsabilidade (WhatsApp/afiliados) e proteção de dados.
- [ ] Repositório **privado**; acesso por convite; **nada** do seu ambiente dentro (rode a verificação de dados pessoais).
- [ ] **Termo de risco** assinado sobre o bloqueio do WhatsApp (`12-riscos-e-termos.md`).
- [ ] Cliente tem (ou cria) as contas: afiliados, WhatsApp dedicado, Meta/YouTube se quiser.
- [ ] Servidor do cliente atende o **mínimo** (`01a-servidor-e-requisitos.md`).
- [ ] Instalação testada **do zero** (VM) na mesma versão que você vai entregar.
- [ ] Cliente sabe operar o básico: `ctl status`, `alertas`, pausar, restaurar backup.
- [ ] Canal de suporte e **horário** definidos.
- [ ] **Nunca** guarde senhas/chaves do cliente com você.

## O que o comprador recebe, passo a passo
1. Convite ao repositório privado.
2. `README` + `docs/00-LEIA-PRIMEIRO.md`.
3. Prompts prontos (`prompts/`) para o Claude instalar, configurar afiliados, conectar WhatsApp e ajustar a marca.
4. Lista de contas a criar (`05` e `07`).
5. Revisão final (checklist de `03` e `13`).

## Risco que você assume ao vender
- Bloqueios de contas do cliente (WhatsApp, afiliados) — **reduza** com contrato e orientação, não prometa.
- Dependência de terceiros: lojas mudam layout, APIs mudam, o ML pode exigir captcha. Combine **o que é manutenção** (inclusa ou cobrada à parte).
- Suporte infinito: limite o escopo (ex.: X horas no primeiro mês).
- Reputação: um cliente bloqueado reclama. Seja claro desde o início.

## Como mostrar o produto sem expor dados
Use o grupo de testes do autor em **modo simulação** (`data/outbox.log`) e **prints** dos posts reais com identificação removida. Grave um vídeo curto: servidor → `ctl status` → um post saindo no grupo.

## Próximos passos sugeridos
1. Testar o V0 em VM e num segundo servidor real (`16`).
2. Reunir 3 a 5 interessados de confiança (convite no GitHub privado).
3. Anotar toda dúvida: viram melhorias na documentação.
4. Só depois definir preço e abrir para mais gente.
