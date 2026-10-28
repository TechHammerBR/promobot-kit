# Histórico de versões

Formato: `v0.N` = versão para testadores (beta fechado). Cada versão tem uma *tag* no Git (`git tag`). Para ver o que mudou entre duas: `git log v0.2..v0.3 --oneline`.

## v0.3 — 28/10/2026 — Redes sociais no passo a passo
- **Novo passo 12 no guia de instalação** (`docs/03`): como conectar Instagram + Página do Facebook, Threads e YouTube, com todos os cliques, permissões e armadilhas; TikTok explicado como "não implementado".
- **Ferramentas novas** em `src/ferramentas/`: `meta_conectar.py`, `threads_conectar.py`, `youtube_conectar.py` (conectam sem mostrar token na tela), `social_verificar.py` (confere tudo só com leitura; `--escrita` faz um teste seguro), `social_previa.py` (gera o Story e o feed de exemplo sem publicar).
- Novas chaves `EDU_ENABLED` e `GAMES_ENABLED` (desligadas no kit): quem liga só os Stories não recebe mais o carrossel educativo e os jogos da semana do autor.
- `.env.example` com bloco "REDES SOCIAIS"; `docs/07`, `docs/14` e `prompts/04` atualizados. Removido `gravar_meta.sh` (tinha dado do autor).

## v0.2 — 28/10/2026 — Instalação testada em VM
- Instalação do zero **testada numa VM com o mínimo do Wyse** (4 núcleos, 2 GB de RAM, 4 GB de swap): 17 de 17 verificações; relatório em `docs/18`.
- **Perfil leve por padrão** (sem Docker, sem IA, conteúdo e redes desligados, modo simulação) — o guia anterior travava em hosts que só existem no Docker.
- Scripts de operação genéricos; os que dependem dos discos do autor foram para `src/ferramentas/do-autor/`.
- API do WhatsApp só em `127.0.0.1`; permissão de execução dos `.sh`; testes sem data fixa.

## v0.1 — 28/10/2026 — Primeira versão
- Código limpo dos dados pessoais, documentação (`docs/00`–`17`), prompts para o Claude Code, ferramenta white-label.
