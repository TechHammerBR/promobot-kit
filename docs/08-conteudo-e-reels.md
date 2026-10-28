# 08 — Conteúdo agendado e fila de Reels

O robô de **grupos** funciona sem nada disto. Este módulo é o que alimenta Instagram, Facebook, Threads e YouTube com conteúdo da **loja/marca** além das ofertas.

## Agenda padrão (tudo em `catchup.schedule()` e nas configurações)
| O quê | Quando (padrão) | Configuração |
|---|---|---|
| Stories com a melhor oferta do dia | 11h, 14h, 18h, 21h | `SOCIAL_STORY_TIMES` |
| Oferta no feed (vitrine) | seg/qua/sex 19:30 | `SOCIAL_FEED_DAYS/TIME`, só se `FEED_VENDAS_ENABLED=true` |
| Carrossel educativo da loja | terça 19h | `EDU_DAY`, `EDU_TIME` |
| Jogos grátis da semana (Epic/Steam) | quinta 13h | `GAMES_DAY`, `GAMES_TIME` |
| Jogos em promoção | segunda 19h | `GAMES2_DAY`, `GAMES2_TIME` |
| Novidades de tecnologia (carrossel) | qua/sex/sáb 12:30 | `ESTUDIO_DIAS`, `ESTUDIO_HORA` |
| Cupons gerais | todo dia 6h | `COUPON_POST_HOUR` |
| Relatórios | 23:00 e 23:50 | — |
| Renovação do token do Threads | domingo 4h | — |

Desligue o que não quiser: `CONTENT_ENABLED=false` (tudo), `ESTUDIO_ENABLED=false`, `SOCIAL_ENABLED=false`, etc.

## Recuperação após queda (`app/catchup.py`)
Cada post agendado é registrado em `data/schedule_state.json`. A cada 20 min (e 3 min depois de ligar) o robô recupera sozinho os horários **de hoje** que passaram sem rodar (tolerância de 3 a 5 h). Por isso reiniciar o servidor não perde o dia.

## Fila de Reels prontos (`app/fila_reels.py`)
O servidor pequeno **não fabrica vídeo**. Um **PC potente** (o "estúdio") gera o vídeo e **entrega numa pasta**; o servidor só publica na hora marcada.

```text
/srv/cache/reels-prontos/            (FILA_REELS_DIR)
  fila/<id>/video.mp4 + capa.jpg + meta.json     ← o PC copia para fila/<id>.tmp e renomeia (atômico)
  publicados/<id>/   falhou/<id>/   expirados/<id>/   ← destino final (nunca publica duas vezes)
  tipos-aprovados.json                           ← tipos já aprovados; outro tipo só sai com "aprovado": true
```
`meta.json`:
```json
{
 "id": "limpeza-ps5-20261029",
 "tipo": "limpeza",
 "legenda": "texto da legenda (com hashtags no fim)",
 "legenda_threads": "versão curta para o Threads (até ~480 caracteres)",
 "quando": "2026-10-29T12:30:00-03:00",
 "na_grade": true,
 "aprovado": true,
 "simular": false
}
```
- Publica em **Instagram, Facebook (Página) e Threads** e, se o YouTube estiver ligado, também como **Short** (agendado na plataforma até 48 h antes).
- A legenda recebe automaticamente o bloco dos **grupos de oferta** (regra: todo post leva o convite) antes das hashtags.
- Um timer do systemd (`promobot-fila-reels.timer`) confere a fila a cada 5 min. Itens que passam da validade (`valido_ate`, padrão `quando + 36 h`) vão para `expirados/`.
- Vídeos com `"simular": true` não publicam, só marcam como feitos (teste do fluxo).

## O estúdio de vídeo (NÃO incluído no kit)
No autor, o estúdio é um PC com GPU que:
- monta o Reel a partir de fotos/vídeos reais (texto grande branco/laranja, música em rodízio, capa 1080×1920);
- usa Whisper (transcrição) para achar as falas boas e cortar;
- mede o volume (−15 LUFS) e confere áudio antes de mostrar.
Nada disso é necessário para o robô de grupos. Se quiser montar o seu, use `prompts/05-pipeline-de-reels-no-pc.md`: o prompt descreve o contrato da fila e o padrão visual, e o Claude constrói o gerador no **seu** PC.

## Regras de conteúdo que funcionaram
- **Foto e vídeo reais**; nada de retoque de IA em fotos de serviço/produto da loja.
- Gancho curto (até 6 palavras) e legenda que entrega valor antes do pedido de contato.
- Capa em **todo** vídeo (1080×1920 para Reels; 1280×720 para YouTube).
- Não repetir assunto em dias seguidos; intercalar tipos (limpeza, dica, novidade).
- Sempre **mostrar a prévia** e esperar aprovação antes de agendar.
