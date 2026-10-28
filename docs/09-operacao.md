# 09 — Operação do dia a dia

## Rotina de 2 minutos (todo dia)
```bash
cd /opt/promobot
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl status     # posts do dia, fila, WhatsApp, pausa
PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl alertas 20 # o que deu errado
```
O que olhar em `status`: `posts_hoje` x `limite_diario`, `ofertas_na_fila` (se zerar, algo parou de coletar), `whatsapp_conectado: true`, `falhas_24h` baixo, `pausado: false`.

## Comandos do `ctl`
Veja a lista em `referencia/comandos-ctl.md`. Resumo:
| Comando | Efeito | Tipo |
|---|---|---|
| `status` | resumo geral | leitura |
| `diag` | por que não está postando (causa provável) | leitura |
| `alertas [n]` | últimos alertas | leitura |
| `fila [n]`, `buscar TERMO` | olhar a fila / procurar | leitura |
| `pausar [min]`, `retomar` | parar/voltar a postar | **ação** |
| `postar [n]` | posta já n ofertas | **ação** |
| `cupons` | posta o post de cupons agora | **ação** |
| `desconto N`, `limite N`, `intervalo MIN [MAX]` | muda regra em tempo real | **ação** |

Os pedidos vão por `data/control.json` e o robô executa na próxima rodada (até ~1 min).

## Página de status
`http://IP-DO-SERVIDOR:8088` (somente leitura, só na rede local). Mostra serviços, memória, disco e últimos posts.

## Logs
```bash
journalctl -u promobot-bot -f          # robô ao vivo
journalctl -u promobot-wa -f           # WhatsApp
journalctl -u promobot-linkgen -f      # navegador do ML
tail -f data/logs/*.log                # logs em arquivo (JSON)
cat data/alertas.log | tail            # alertas do sistema
tail -n 40 data/outbox.log             # (simulação) o que seria enviado
```

## Pausa de manutenção
`touch data/MAINTENANCE` pausa a manutenção automática e as rotinas que religam serviços; apague o arquivo ao terminar. Para pausar **os posts**, use `ctl pausar 120` (minutos).

## Reiniciar com segurança
```bash
sudo systemctl restart promobot-bot     # seguro: o catchup retoma o que faltou
sudo systemctl restart promobot-wa      # reconecta sozinho se a sessão estiver boa
sudo reboot                             # tudo volta sozinho (serviços têm Restart=always)
```

## Atualizar o código
1. **Backup** do arquivo que vai mudar (`cp app/x.py app/x.py.bak_AAAAMMDD`).
2. Altere; rode `PYTHONPATH=/opt/promobot venv/bin/python -m pytest -q tests`.
3. `sudo systemctl restart promobot-bot`.
4. `ctl status` + `ctl alertas`. Se algo quebrou, volte o backup.
Mudança que vale para a loja toda (regra, horário, formato) → registre em `docs/16-decisoes-e-historia.md`.

## Backup e restauração
- O `backup.sh` roda às 03:40: banco (cópia consistente), `.env`, sessão do WhatsApp (`data/wa`), `control.json` e estados. Mantém 14 dias.
- Restaurar: pare o robô, extraia o `.tar.gz` mais recente em `/opt/promobot`, suba de novo. Detalhes em `11-seguranca-e-backup.md`.
- **Teste a restauração** pelo menos uma vez (um backup nunca testado não é backup).

## Manutenção automática
`ferramentas/manutencao.sh` (04:20): para o robô, enxuga o banco (ofertas recusadas/expiradas antigas), compacta, limpa temporários e logs velhos, confere disco/memória/serviços e religa. Resultado em `data/saude.log`. O vigia `vigia_recursos.sh` roda a cada 5 min e escreve em `alertas.log` quando a memória ou o disco ficam baixos.

## Queda de energia
- Com o BIOS em "ligar após queda", o servidor volta sozinho; os serviços sobem; o `catchup` recupera os posts de hoje.
- Depois de um boot "sujo", confira: `ctl status`, `ctl alertas 20` e se o WhatsApp reconectou. O Mercado Livre pode pedir login de novo.

## Calendário de renovações
Veja a tabela de validade de acessos em `07-redes-sociais.md`.

## Checklist semanal (10 minutos)
- [ ] `ctl alertas 50` — algum alerta repetido?
- [ ] disco e memória (`df -h`, `free -m`)
- [ ] backup mais recente existe e abre (`tar tzf`)
- [ ] links de afiliado estão gerando comissão no painel da loja
- [ ] grupo: alguém reclamou de foto estranha, preço errado ou repetição? Ajuste a regra e registre.
- [ ] (se usar Instagram) leia a **revisão semanal** (próxima seção) e aplique 1 ajuste na semana.

## Revisão semanal do Instagram (só leitura)
Com o Instagram conectado (`03`, passo 12), o robô lê os seus posts pela API oficial e escreve um relatório em `data/revisao_instagram/ultima.md` **todo domingo às 20h** (precisa de `CONTENT_ENABLED=true`). Para gerar na hora: `PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl revisao-ig 60` (últimos 60 dias).
- Mostra: seguidores e variação; os 5 posts que mais se destacaram e os 5 que menos funcionaram (comparados com o normal do **mesmo formato**); nota média por formato, tema, tipo de gancho (1ª linha), dia da semana e horário; e 3 a 5 recomendações para a semana.
- A **nota** é curtidas + 3 × comentários (comentário vale mais). Alcance e visualizações exigem a permissão `instagram_manage_insights` no token (opcional; sem ela o relatório usa só curtidas e comentários).
- Com poucos posts por grupo os números são **pistas, não leis** (o relatório marca "amostra pequena"). Não usa IA, não posta e não manda notificação.
- Como usar: leia o relatório, escolha **uma** coisa para repetir e **uma** para parar, e anote no seu caderno de decisões (`16`). Para pedir ao Claude que interprete: cole o `ultima.md` e use as skills/prompts de diagnóstico de perfil.
