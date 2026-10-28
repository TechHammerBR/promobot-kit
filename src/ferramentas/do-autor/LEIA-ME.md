# Scripts do servidor do autor (NÃO instale sem entender)

Estes scripts foram feitos para o **servidor específico do autor** (um Dell Wyse 3040 com vários discos USB: SSD externo em `/srv/cache`, pendrives em `/srv/backup`, `/srv/espelho`, `/srv/cache-copia`). Eles assumem esses discos e esses pontos de montagem.

**Perigo:** `vigia_armazenamento.sh` **para os serviços do robô** e tenta remontar discos quando não encontra os discos do autor. Num servidor diferente ele pode derrubar o robô à toa. **Não coloque no cron** se você não tem exatamente essa estrutura.

| Script | O que faz | Depende de |
|---|---|---|
| `vigia_armazenamento.sh` | vigia os discos USB e remonta/religa serviços | `/srv/cache`, `/srv/backup`, `/srv/espelho`, `/srv/cache-copia` |
| `copia_cache.sh` | copia o SSD para um pendrive de hora em hora | `/srv/cache`, `/srv/cache-copia` |
| `espelho.sh` | espelho diário dos itens críticos em outro pendrive | `/srv/backup`, `/srv/espelho` |
| `imagem_wyse.sh` | imagem semanal do disco interno | `/srv/backup` |
| `saude_ssd.sh` | lê o SMART do SSD externo | SSD NVMe externo |
| `retomar.sh` | remonta tudo depois de mexer nos discos | fstab do autor |
| `render.sh` | roda tarefa pesada sem travar o servidor | pendrive para temporários |
| `uso.sh`, `uso_dia.sh` | relatório de uso e custo de energia | cron do autor |

Use como **exemplo** para criar os seus, ou peça ao Claude (`prompts/08-diagnostico-e-manutencao.md`) para adaptar à sua máquina.
