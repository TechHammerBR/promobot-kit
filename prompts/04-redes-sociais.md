# 04 — Redes sociais (Meta, Threads, YouTube, TikTok)

**Leia antes:** `docs/07-redes-sociais.md`, `docs/08-conteudo-e-reels.md`, `docs/12-riscos-e-termos.md` (seção 7).

```text
TAREFA: ligar UMA rede social por vez, sempre com PRÉVIA aprovada por mim antes de publicar. Comece por: Instagram+Página (Meta). Depois, se eu pedir: Threads, YouTube, TikTok.

REGRAS
- Só API oficial. Nunca automatize o login de conta pessoal.
- SOCIAL_ENABLED=false até eu aprovar as prévias.
- Tokens: nunca no chat nem no Git; grave com script que leia sem eco. Anote a validade de cada um (docs/07, tabela).

META (Instagram + Facebook)
1. Verifique: Instagram é PROFISSIONAL e está vinculado a uma Página do Facebook? (se não, guie a conversão)
2. Guie a criação do app (tipo Empresa; produtos Instagram e Páginas) e as permissões pages_manage_posts, instagram_basic, instagram_content_publish.
3. Obtenha token de usuário de longa duração e troque por token de PÁGINA; grave META_PAGE_ID, META_IG_ID, META_PAGE_TOKEN.
4. Gere 1 Story e 1 post de feed de PRÉVIA (arquivos locais, sem publicar). Mostre. Só publique após eu dizer "pode".
5. Confira os limites da API: sem link clicável em Stories; link no 1º comentário do feed; vídeo exige upload direto.

YOUTUBE
1. Projeto no Google Cloud, YouTube Data API v3, credencial OAuth "app para computador", app em PRODUÇÃO.
2. Escreva o script de autorização (loopback 127.0.0.1) que gera youtube_token.json; guarde em data/youtube/ com chmod 600.
3. Teste com um vídeo PRIVADO. Ligue os Shorts automáticos da fila (app/youtube.py) só depois.
4. Explique a limitação: a API não edita nem apaga vídeos; cota diária pequena.

THREADS: app separado; THREADS_TOKEN com renovação semanal (já existe job).

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
