# 06 — White-label (a minha marca)

**Leia antes:** `docs/13-white-label.md`.

```text
TAREFA: trocar toda a identidade do autor pela MINHA marca, sem quebrar o robô.

PERGUNTE: nome da marca, @ do Instagram, cidade/região, cores (hex), logo (arquivo), serviços que a minha loja oferece e os preços, telefone de orçamento (só dígitos), links dos meus grupos.

PASSOS
1. Crie um commit "antes do white-label" (ponto de volta).
2. Rode src/ferramentas/whitelabel.py --listar e mostre onde a marca do autor aparece.
3. Monte brand.json com as trocas, rode em SIMULAÇÃO, me mostre o resumo e só então aplique (--aplicar). Revise o git diff com atenção (marcas parecidas, URLs, hashtags).
4. Configure no .env: BRAND_NAME, BRAND_COLOR, ACCENT_COLOR, SOCIAL_CTA, POST_HASHTAG, STORE_WHATSAPP, LAR_NOME, GROUP_INVITE_LINK, LAR_INVITE_LINK.
5. Coloque os meus logos e textos em src/app/assets/ (logo-ofertas.png, logo-casa.png, descricao-tech.txt, descricao-casa.txt, convite.txt).
6. CONTEÚDO DE SERVIÇO: reescreva os serviços e a tabela de preços (content.py: CTA_LINES, TAGS, séries do carrossel educativo; prices.py) para o MEU negócio — ou, se eu não tiver serviços, desligue CONTENT_ENABLED. Mostre o texto antes de aplicar. Não invente serviço, preço, garantia nem prazo: pergunte.
7. Ajuste cores/fonte das artes (social_art.py, noticia_art.py) e gere 3 prévias (Story, feed, carrossel) para eu aprovar.
8. Rode os testes e whitelabel.py --listar de novo: não pode sobrar a marca do autor.

CRITÉRIOS DE ACEITAÇÃO
- [ ] whitelabel.py --listar: 0 ocorrências da marca do autor
- [ ] testes passam (ou o que falha já falhava antes)
- [ ] prévias aprovadas por mim
- [ ] nenhum dado do autor (telefone, grupos, etiquetas, IDs) permanece

NÃO FAÇA: inventar serviços/preços/garantias, copiar a identidade do autor, publicar antes da aprovação.
```
