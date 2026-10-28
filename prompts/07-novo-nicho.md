# 07 — Mudar de nicho (pet, beleza, ferramentas, moda, casa…)

**Leia antes:** `docs/10-regras-de-negocio.md`, `docs/13-white-label.md` (seção "Trocar de nicho").

```text
TAREFA: adaptar o robô ao MEU nicho: <descreva o nicho e o público>. Hoje ele é ajustado para tecnologia (grupo "tech") e casa/dia a dia (grupo "lar").

PERGUNTE
1. Qual o público e o que ele quer comprar? Que lojas têm afiliado para mim?
2. Quero 1 grupo ou 2? O que é o "foco" e o que vai para o segundo grupo?
3. Faixas de preço que fazem sentido (mínimo/máximo) e desconto mínimo aceitável.

PASSOS
1. Proponha as listas: PRIORITY_KEYWORDS, SHOPEE_KEYWORDS, ALI_KEYWORDS, PELANDO_SEARCH_TERMS, LAR_* (ou o equivalente), BANNED_WORDS e as MARCAS confiáveis (titles.py). Mostre e espere OK.
2. Ajuste engine.is_tech/canal_de para o novo foco; escreva testes (tests/test_canais.py) com 20 títulos reais do nicho (10 que devem entrar, 10 que não).
3. Recalibre a foto: se o nicho tem fotos com PESSOA (moda, beleza), a regra de photocheck.py (produto em fundo de catálogo) vai reprovar demais. Meça com ferramentas/calibrar_foto.py em ~150 fotos reais, proponha limites novos e mostre a taxa de aprovação antes e depois. Não afrouxe sem medir.
4. Rode UMA SEMANA em simulação; ao fim mostre: posts/dia, % por loja, motivos de rejeição (top 10), 10 amostras de posts (texto). Ajuste e repita.
5. Só então ligue a publicação real, com DAILY_POST_LIMIT conservador.

CRITÉRIOS DE ACEITAÇÃO
- [ ] 90%+ dos posts simulados são do nicho certo (revisão manual de 50)
- [ ] menos de 5% de fotos ruins nas amostras
- [ ] regras e decisões registradas em docs/16

NÃO FAÇA: copiar a lista de outro grupo, ligar publicação real sem a semana de simulação, afrouxar regra de foto sem medir.
```
