# 18 — Relatório do teste de instalação (VM, 28/10/2026)

Teste feito **do zero** numa máquina virtual com o **mínimo do Wyse**, seguindo o `docs/03` passo a passo, em **modo simulação**. Objetivo: descobrir o que travaria quem fosse instalar.

## Ambiente do teste
| Item | Valor |
|---|---|
| Máquina | VM (WSL2) num PC com Windows 11 |
| Sistema | **Debian 13 (trixie)** — imagem oficial `debian:trixie-slim` (mínima) |
| Limites | **4 núcleos, 2 GB de RAM, 4 GB de swap** (= mínimo do Wyse) |
| Versões | Python 3.13.5, Node 20.19.2, Chromium 156, SQLite 3.46 (**idênticas** às do servidor do autor) |
| Dados | chaves de API de teste (Shopee, AliExpress, Awin); **sem** WhatsApp, Meta, Threads, Telegram, login do ML |

## Resultado por passo
| Passo do `03` | Resultado | Tempo |
|---|---|---|
| 1. Sistema e usuário `promobot` | ✅ (precisou `adduser`, ver achado 1) | 1 min |
| 2. Pacotes do sistema | ✅ sem erro | ~1,5 min |
| 3. Código e ambiente Python (versões fixadas) | ✅ (precisou corrigir o fluxo, achados 2 e 3) | ~1 min |
| 4. Conector do WhatsApp (`npm install`) | ✅ 80 MB, biblioteca carrega | 4 s |
| 5. Coleta em simulação (`--once`) | ✅ depois dos achados 4 e 5 | ~1 min |
| 6. Testes automáticos | ✅ **79 passam, 0 falham** (depois do achado 8) | 1 s |
| 7. Serviços do systemd | ✅ `active`, com limites de memória; voltam sozinhos após reiniciar | — |
| 7b. Navegador do ML (Xvfb + linkgen + VNC) | ✅ sobe, VNC só em `127.0.0.1`; **0,94 GB de 1,9 GB** com tudo ligado | — |
| 10. Backup / restauração | ✅ restaurei o banco (558 ofertas, 4 tabelas) | <1 s |
| `ctl` (postar, pausar, retomar, desconto, intervalo, limite, buscar, fila, relatório) | ✅ | — |
| **Não testado** | pareamento do WhatsApp (precisa de número real), login do Mercado Livre, redes sociais, YouTube | — |

Primeiro post simulado apareceu ~1 min depois do `--once`; depois o robô passou a postar sozinho com a **chamada v2** e link de afiliado da Shopee gerado pela API.

## Achados (todos corrigidos no kit)
| # | Problema | Gravidade | Correção |
|---|---|---|---|
| 1 | `adduser` não existe em imagem mínima | baixa | nota no guia |
| 2 | `rm -rf tmp` do guia **apagava `deploy/`**, necessária no passo 7 | média | o clone fica em `~/promobot-kit` |
| 3 | Clone de repositório **privado** pede login (`could not read Username`) | média | guia com token / `gh` / ZIP |
| 4 | **Padrões herdados do Docker** (`wa`, `linkgen`, `ollama`; IA ligada; conteúdo/redes ligados): `Name or service not known` ao publicar | **alta** | perfil leve por padrão no `config.py` e `.env.example` |
| 5 | Sem login do ML, toda oferta do ML tentava o navegador, falhava e **travava o robô** (alerta "login do ML expirou?") | **alta** | `.env.example` com `ML_PAUSED_UNTIL`/`ML_BONUS_MODE` (ML sai como bônus) |
| 6 | Scripts `.sh` sem permissão de execução (`Permission denied`) | média | `+x` gravado no Git |
| 7 | `backup.sh` falhava em instalação nova (arquivo de estado ainda não existe) | média | só inclui o que existe |
| 8 | 2 testes já falhavam (data fixa de 07/10 vira bomba-relógio; regra de casa mudou) | baixa | testes corrigidos (**também na produção**) |
| 9 | `ctl diag` dava falso alarme ("IA fora do ar", "gerador de links fora do ar") e tinha endereço de Docker fixo | média | corrigido (**também na produção**) |
| 10 | **API do conector do WhatsApp escutava em todas as interfaces** (`*:3000`), contra o que o guia afirma | **alta (segurança)** | `listen(3000, '127.0.0.1')` (**também na produção**) |
| 11 | Scripts com caminhos dos **discos USB do autor**; um deles (`vigia_armazenamento.sh`) **para os serviços** se não achar esses discos | **alta** | movidos para `ferramentas/do-autor/` com aviso; `vigia_recursos.sh` generalizado |
| 12 | Faltava `playwright` no `requirements.txt` | média | acrescentado |
| 13 | Dados pessoais restantes (ID de grupo fixo em `convites.py`) | **alta (privacidade)** | removido; verificador reforçado |
| 14 | Quebras de linha `CRLF` do Windows quebrariam os `.sh` no Linux | **alta** | `LF` forçado + `.gitattributes` |

## O que isto ensinou
- **Testar do zero vale muito:** 14 problemas, 6 de gravidade alta, que o autor nunca viu porque o servidor dele já estava configurado.
- Quatro correções valem **também para a produção** (diag, WhatsApp só em localhost, 2 testes) e já foram aplicadas lá.
- Sem chave de afiliado quase nada vira post: o guia agora avisa.

## Como repetir o teste
O autor usou uma VM em WSL2 (`wsl --import` do rootfs oficial do Debian, com `.wslconfig` de 4 núcleos, 2 GB de RAM e 4 GB de swap). Em qualquer VM ou servidor, siga o `03` com os mesmos limites e registre as diferenças aqui (ou num Issue).
