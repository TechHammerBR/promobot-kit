# 13 — White-label (trocar a marca e o nicho)

O código foi feito para **uma loja de manutenção de computadores** (TechHammer) com grupos de ofertas de **tecnologia** e **casa**. Para usar com a sua marca (ou outro nicho) há três camadas, da mais fácil para a mais trabalhosa.

## Camada 1 — Troca de texto da marca (automática)
```bash
python src/ferramentas/whitelabel.py --listar                       # onde a marca do autor aparece
cp brand.example.json brand.json && editar brand.json              # seus nomes
python src/ferramentas/whitelabel.py --config brand.json            # simulação
git commit -am "antes do white-label"                               # ponto de volta
python src/ferramentas/whitelabel.py --config brand.json --aplicar
```
Troca nome da marca, @ do Instagram e região por todo o código e documentação (≈ 50 ocorrências). Revise com `git diff`.

## Camada 2 — Configuração (`.env`)
| O que | Variável |
|---|---|
| Nome da marca nas artes | `BRAND_NAME`, `BRAND_COLOR`, `ACCENT_COLOR` |
| Chamada nas artes ("LINK DO GRUPO NA BIO") | `SOCIAL_CTA` |
| Hashtag de anúncio | `POST_HASHTAG` |
| Convites dos grupos | `GROUP_INVITE_LINK`, `GROUP_INVITE_LABEL`, `LAR_INVITE_LINK` |
| Nome do grupo de casa | `LAR_NOME` |
| Telefone de orçamento | `STORE_WHATSAPP` |
| Etiquetas de afiliado | `ML_TAG_TECH`, `ML_TAG_LAR` |

## Camada 3 — Conteúdo e arte (à mão ou com o Claude)
Estes itens **não** se resolvem com troca de texto. Use `prompts/06-whitelabel.md`.
| Item | Onde | O que fazer |
|---|---|---|
| Logos dos grupos | `src/app/assets/logo-ofertas.png`, `logo-casa.png` | coloque os seus (PNG transparente) |
| Descrição/convite dos grupos | `src/app/assets/descricao-*.txt`, `convite.txt` | use `descricao.exemplo.txt` como modelo |
| Fontes e identidade visual das artes | `src/app/social_art.py`, `noticia_art.py`, `content.py` (cores `BRAND_*`) | ajuste cores/fontes; o padrão é minimalista escuro com destaque laranja |
| **Serviços da loja** (limpeza, pasta térmica, montagem…) | `content.py` (`CTA_LINES`, `TAGS`, séries do carrossel educativo), `prices.py` (tabela de preços) | **reescreva para os seus serviços** ou desligue `CONTENT_ENABLED` |
| Palavras do nicho (tecnologia/casa) | `PRIORITY_KEYWORDS`, `SHOPEE_KEYWORDS`, `ALI_KEYWORDS`, `LAR_*`, `PELANDO_SEARCH_TERMS` | troque por palavras do seu nicho |
| Marcas confiáveis | `titles.py` (lista `MARCAS`) | adapte ao seu nicho |
| Classificação de canal (tech × casa) | `engine.py` (`canal_de`, `is_tech`) | ajuste regras/listas |
| Fontes de ofertas | `collectors/` | acrescente/retire coletores do seu nicho |

## Trocar de nicho (ex.: pet, beleza, ferramentas, moda)
1. Defina o público e as lojas com afiliado que interessam.
2. Troque palavras-chave (tabela acima) e o `PRIORITY_KEYWORDS`.
3. Ajuste `engine.is_tech`/`canal_de` (o que é "foco" e o que vai para o segundo grupo).
4. Ajuste as regras de foto: para moda/beleza, fotos com **pessoa** são normais — a regra de `photocheck.py` foi calibrada para **produto em fundo de catálogo**. Recalibre com `ferramentas/calibrar_foto.py` em ~150 fotos reais do seu nicho.
5. Revise `BANNED_WORDS` e a marca confiável (`titles.py`).
6. Faça uma semana em simulação lendo `data/outbox.log` antes de ligar.
Prompt pronto: `prompts/07-novo-nicho.md`.

## Antes de entregar a um cliente
- [ ] `whitelabel.py --listar` não encontra mais a marca do autor
- [ ] `.env` do cliente com chaves **dele**; nenhum dado do autor no servidor
- [ ] logos/descrições/convites do cliente em `assets/`
- [ ] serviços e preços da tabela dele (ou conteúdo da loja desligado)
- [ ] testes passam (`pytest`) e `ctl status` está verde
- [ ] cliente sabe os riscos (`12-riscos-e-termos.md`) e como pedir ajuda
