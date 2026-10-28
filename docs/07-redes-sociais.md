# 07 — Redes sociais: Instagram, Facebook, Threads, YouTube (e TikTok)

Tudo aqui é **opcional**. O robô de grupos funciona sem nenhuma rede social. Cada rede usa **API oficial** (nenhum robô entra na sua conta pelo login).

## Regra de ouro: aprovar antes de postar
Para qualquer **tipo novo de post** (Stories, feed, Reel, carrossel) gere primeiro uma **prévia** e aprove. Mantenha `SOCIAL_ENABLED=false` até ver as prévias.

## Meta: Instagram + Página do Facebook (`app/social.py`)
**Pré-requisitos:** Instagram **profissional** (comercial/criador) vinculado a uma **Página do Facebook**. Perfil pessoal do Facebook **não** tem API.

**O passo a passo completo (com todos os cliques) está em `03-instalacao-passo-a-passo.md`, passo 12.** Resumo:

1. Crie um app em developers.facebook.com (tipo **Empresa**, modo de desenvolvimento: não precisa de revisão para as suas contas).
2. Permissões: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish` (+ `business_management` se a Página estiver num portfólio empresarial).
3. Gere o token no Explorador da Graph API e rode `ferramentas/meta_conectar.py`: ele troca por token de longa duração, pega o token da **Página** (**não expira**), descobre `META_PAGE_ID` e `META_IG_ID` e grava no `.env` sem mostrar nada na tela.
4. Confira com `ferramentas/social_verificar.py` e veja as artes com `ferramentas/social_previa.py` (nada é publicado). Só então `CONTENT_ENABLED=true` e `SOCIAL_ENABLED=true`.
5. O guardião checa a validade do token e alerta (`meta_token`).
6. **Não** coloque tokens no chat nem no Git. Se vazar, revogue e gere outro.

**O que o robô posta (padrão do autor, tudo ajustável):**
- **Stories** da melhor oferta do dia (`SOCIAL_STORY_TIMES`, 4 por dia).
- **Feed:** vitrine da loja/serviço (`SOCIAL_FEED_DAYS`, `SOCIAL_FEED_TIME`); oferta no feed só se `FEED_VENDAS_ENABLED=true`.
- **Link:** a API **não** coloca link clicável em Stories nem fixa comentário. O robô usa "link no perfil" e põe o link no 1º comentário do feed.
- **Instagram exige upload direto do vídeo** (`upload_type=resumable`); URL do vídeo dá erro.
- Bio, foto de perfil e post fixado **não** são editáveis por API: ajuste à mão.

## Threads (`app/threads.py`)
App separado do Threads (id/segredo próprios); conecte com `ferramentas/threads_conectar.py` (passo 12.2 do `03`). `THREADS_TOKEN` dura ~60 dias e é **renovado sozinho todo domingo às 4h** (`catchup`, job `threads_token`). Posta a mesma oferta dos Stories, com link clicável.

## YouTube (`app/youtube.py`)
Para **Shorts automáticos** (cada Reel da fila vira Short) e vídeos longos enviados do PC.
1. No Google Cloud, crie um projeto, ative a **YouTube Data API v3** e crie credencial OAuth do tipo **app para computador**. Publique o app (modo "produção") para o token não expirar em 7 dias.
2. Escopos: `youtube.upload` + `youtube.readonly` (**não permitem apagar nem editar vídeos pela API**).
3. Autorize uma vez com `ferramentas/youtube_conectar.py` (fluxo de loopback `127.0.0.1:8765`, com túnel SSH — passo 12.3 do `03`): ele grava `youtube_token.json` em `data/youtube/` (`chmod 600`); o `youtube_client.json` você baixa do Google Cloud e salva na mesma pasta.
4. **Shorts agendados na plataforma:** até 48 h antes do horário do Reel, o robô sobe o Short como **privado + `publishAt`**; o YouTube publica na hora marcada. Na hora do Reel o robô não sobe de novo. Limite: cota diária da API (~6 envios; cada upload custa 1600 de 10.000 unidades).
5. **Limitação:** como a API não edita/apaga, se você refizer um Reel **depois** de o Short estar agendado, apague o Short antigo no YouTube Studio.
6. Título do Short = 1ª linha da legenda + `#Shorts`; descrição = legenda com os links dos grupos.

## TikTok (não implementado)
O TikTok só permite postar por **API oficial de desenvolvedor** (Content Posting API). Pontos importantes (fonte: documentação do TikTok):
- Aplicativo **sem auditoria** só publica em modo **privado** e com contas privadas, com limite de usuários por dia. Para publicar **publicamente** é preciso passar por **auditoria do TikTok** (demora, sem garantia, e exige uma tela de postagem em que o usuário confirma cada post).
- Alternativas: (a) enviar para a **caixa de rascunhos** (`video.upload`) e publicar com um toque; (b) usar uma **ferramenta de agendamento** que já tenha acesso aprovado (ex.: Metricool, Buffer, Later) e ligá-la; (c) agendar à mão no TikTok Studio.
- **Não** automatize o login da conta (risco de banimento).
- Referências: [Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines), [Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post).
- Passo a passo para o Claude implementar: `prompts/04-redes-sociais.md`.

## Prazo de validade dos acessos (anote no calendário)
| Acesso | Validade | Renovação |
|---|---|---|
| Token de usuário Meta | ~60 dias | gerar outro e trocar pelo token de Página |
| Token de **Página** Meta | não expira | — |
| Token do Threads | ~60 dias | automática (domingo 4h) |
| OAuth do YouTube | refresh token longo | refazer se o app voltar a "teste" |
| Login do Mercado Livre (navegador) | variável | refazer por VNC (`05-afiliados.md`) |
| Sessão do WhatsApp | até desconectar | parear de novo |
