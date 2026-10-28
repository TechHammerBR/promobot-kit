# 05 — Fábrica de Reels no PC (estúdio) + entrega na fila

**Leia antes:** `docs/08-conteudo-e-reels.md`. O estúdio **não** está neste kit: este prompt faz o Claude construir o **seu** no **seu PC** (não no servidor pequeno).

```text
TAREFA: montar, no MEU PC (não no servidor), um gerador de Reels verticais (1080x1920, 30 fps, H.264/AAC) e entregá-los na fila de vídeos prontos do servidor, conforme docs/08-conteudo-e-reels.md.

PERGUNTE PRIMEIRO
1. Meu PC: sistema, GPU (para codificar com NVENC e transcrever com Whisper) e onde guardar os arquivos (NUNCA no disco do sistema se eu pedir outro).
2. Que tipo de Reel quero (antes/depois de serviço, dica, novidade, oferta)? Quais fotos/vídeos reais tenho?
3. Identidade visual: cores, fonte, logo (use assets meus; nada de IA para retocar foto de serviço).

PADRÃO QUE FUNCIONOU (use como base)
- Gancho de PROBLEMA nos primeiros 3 s (até 6 palavras), texto grande (branco com contorno, destaque em cor), marca no rodapé do Story (o topo é coberto pela barra do Instagram).
- Antes/depois direto; sem prometer resultado que eu não confirmei; sem tempo de execução se não agrega.
- Fechamento com pergunta que gera contato ("Seu PC tá precisando respirar também?") e botão "FALE COM A GENTE".
- Música em RODÍZIO (nunca as 3 de sempre), volume baixo; se houver fala minha, "ducking" (música abaixa quando falo). Alvo: -15 LUFS, pico -2 dBTP.
- Capa 1080x1920 (capa.jpg) em TODO vídeo; para YouTube, 1280x720.
- Mostre a prévia leve (MP4 pequeno) e espere meu OK antes de agendar.

ENTREGA NA FILA (contrato do servidor)
- Pasta fila/<id>.tmp com video.mp4, capa.jpg e meta.json; depois renomear para fila/<id> (atômico). Campos do meta.json: id, tipo, legenda, legenda_threads, quando (ISO com fuso), na_grade, aprovado, simular.
- Primeiro teste com "simular": true para ver o fluxo sem publicar.
- A legenda leva os links dos grupos (o servidor acrescenta o bloco se faltar).

QUALIDADE (antes de me mostrar)
- [ ] ffprobe confirma 1080x1920, áudio presente, duração coerente com os slides
- [ ] medi o volume (ebur128) e conferi o áudio de ponta a ponta (sem fala cortada/repetida)
- [ ] sem erro de português no texto da tela; sem afirmar o que não sei
- [ ] se usei minha fala, transcrevi (Whisper) e cortei palavrão/assuntos alheios

NÃO FAÇA: publicar direto, usar foto/vídeo que não é meu, usar música sem licença comercial, deixar arquivos grandes no disco do sistema.
```
