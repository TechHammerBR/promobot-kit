# 04 — Redes sociais (Meta, Threads, YouTube, TikTok)

**Leia antes:** `docs/07-redes-sociais.md`, `docs/08-conteudo-e-reels.md`, `docs/12-riscos-e-termos.md` (seção 7).

```text
TAREFA: ligar UMA rede social por vez, sempre com PRÉVIA aprovada por mim antes de publicar. Comece por: Instagram+Página (Meta). Depois, se eu pedir: Threads, YouTube, TikTok.

REGRAS
- Só API oficial. Nunca automatize o login de conta pessoal.
- SOCIAL_ENABLED=false até eu aprovar as prévias.
- Tokens: nunca no chat nem no Git; grave com script que leia sem eco. Anote a validade de cada um (docs/07, tabela).

FERRAMENTAS PRONTAS (já existem em ferramentas/; NÃO reescreva, use): meta_conectar.py, threads_conectar.py, youtube_conectar.py, social_verificar.py, social_previa.py.
Guia completo com todos os cliques: docs/03, passo 12. Eu faço os cliques nos sites; você me guia e roda os scripts.

META (Instagram + Facebook)
1. Verifique: Instagram é PROFISSIONAL e está vinculado a uma Página do Facebook? (se não, guie a conversão)
2. Guie a criação do app (tipo Empresa, modo de desenvolvimento) e a geração do token no Explorador da Graph API com as permissões pages_show_list, pages_read_engagement, pages_manage_posts, instagram_basic, instagram_content_publish (+ business_management se a Página estiver em portfólio empresarial).
3. Eu rodo ferramentas/meta_conectar.py (token longo, token da PÁGINA, META_PAGE_ID e META_IG_ID gravados sem eco). Rode ferramentas/social_verificar.py e me explique cada linha.
4. Rode ferramentas/social_previa.py (Story e feed de PRÉVIA, sem publicar). Mostre. Só ligue CONTENT_ENABLED e SOCIAL_ENABLED após eu dizer "pode".
5. Confira os limites da API: sem link clicável em Stories; link no 1º comentário do feed; vídeo exige upload direto.

YOUTUBE
1. Projeto no Google Cloud, YouTube Data API v3, tela de consentimento PUBLICADA (senão expira em 7 dias), credencial OAuth "app para computador" salva em data/youtube/youtube_client.json.
2. Eu abro o túnel (ssh -L 8765:127.0.0.1:8765) e rodo ferramentas/youtube_conectar.py; ele grava data/youtube/youtube_token.json (chmod 600).
3. Teste com um vídeo PRIVADO. Ligue os Shorts automáticos da fila (app/youtube.py) só depois.
4. Explique a limitação: a API não edita nem apaga vídeos; cota diária pequena; projeto sem auditoria pode ficar só com envios privados.

THREADS: app separado; conecte com ferramentas/threads_conectar.py (THREADS_TOKEN com renovação semanal, já existe job). Ligue THREADS_ENABLED só depois do social_verificar.py sem FALHOU.

TIKTOK (não implementado)
1. Explique em 5 linhas as opções (docs/07): rascunho (video.upload), ferramenta de agendamento aprovada, ou manual no TikTok Studio. Recomende uma e espere minha escolha.
2. Se eu escolher rascunho: implemente app/tiktok.py com OAuth, upload para a caixa de entrada e testes; NÃO prometa publicação pública (exige auditoria).
3. Peça-me para criar a conta de desenvolvedor e o app; eu mesmo faço o login.

CRITÉRIOS DE ACEITAÇÃO
- [ ] cada rede tem uma PRÉVIA aprovada por mim antes do 1º post real
- [ ] tokens fora do Git, com validade anotada
- [ ] falha em uma rede NUNCA derruba as outras (log, não exceção)

NÃO FAÇA: postar sem prévia aprovada, usar login/senha, prometer resultado de alcance.
```
