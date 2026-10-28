# 01a — Você precisa de um servidor (e quais as especificações mínimas)

## Em uma frase
O PromoBot **precisa de um computador que fique ligado 24 horas por dia, 7 dias por semana**, com internet estável. **Não** é um programa para instalar no seu PC ou notebook do dia a dia, e não roda no celular. O robô só vale a pena se postar o dia todo, inclusive de madrugada, quando você dorme ou desliga o PC.

## O mínimo = a configuração do Wyse (referência testada em produção)
O mínimo deste kit é **exatamente o servidor onde ele roda hoje**: um **Dell Wyse 3040** (thin client usado, barato).

| Item | Mínimo (= Wyse 3040) | Observações |
|---|---|---|
| **Processador** | x86-64, **4 núcleos**, ~1,4 GHz (Intel Atom x5-Z8350) | qualquer CPU x86-64 igual ou melhor serve |
| **Memória RAM** | **2 GB** (1,9 GB utilizáveis) | funciona **com swap**: no Wyse há 1,9 GB de zram + 4 GB de swap em disco |
| **Armazenamento interno** | **8 GB** (eMMC/SSD) | o sistema + robô usam ~3,1 GB; sobra folga |
| **Armazenamento extra (USB)** | **1 pendrive de 16 GB** (backup) | no Wyse há também SSD/pendrives para cache e cópia (opcional) |
| **Rede** | **cabo Ethernet** | Wi-Fi funciona, mas cai mais |
| **Sistema** | **Debian 13** ("trixie") sem interface gráfica; Ubuntu 24.04+ também serve | |
| **GPU** | **não precisa** | nenhuma IA roda no servidor |
| **Energia** | consumo muito baixo (meça com um medidor de tomada) | recomendável **nobreak** pequeno |

### Uso real medido no Wyse (28/10/2026, robô completo com Mercado Livre)
| Recurso | Uso |
|---|---|
| RAM em uso | ~1,2 GB de 1,9 GB (o navegador do ML, o Chromium, usa ~0,8 GB somados) |
| Swap (zram) em uso | ~235 MB |
| Sem o navegador do ML (só Shopee/AliExpress via API) | ~450 MB de RAM no total |
| Disco: código + ambiente Python + conector | ~320 MB |
| Disco: dados (banco, sessão do WhatsApp, logs) | ~225 MB (cresce devagar; a manutenção noturna enxuga) |
| CPU | carga média ~2 de 4 durante coletas; ociosa o resto do tempo |

> **Conclusão prática:** 2 GB de RAM **funciona**, mas é o limite. Os serviços têm limite de memória (`MemoryHigh/MemoryMax`) justamente para isso. Se for usar o Mercado Livre pelo navegador, **tenha swap**. Sem o Chromium, 1 GB já basta.

## Recomendado (mais folga, quase o mesmo preço)
| Item | Recomendado |
|---|---|
| CPU | x86-64 moderno de 4 núcleos (ex.: Intel N100/N95) |
| RAM | **4 GB** (8 GB se quiser rodar também PostgreSQL ou várias instâncias) |
| Armazenamento | **SSD de 32 GB+** (interno) + pendrive/SSD externo para backup |
| Rede | Ethernet + IP **reservado** no roteador |
| Energia | **nobreak** + BIOS configurada para "ligar após queda de energia" |

## Onde colocar o servidor
| Opção | Prós | Contras |
|---|---|---|
| **Em casa/na loja** (mini PC, thin client) — **recomendado** | custo único baixo; **IP residencial** (lojas e WhatsApp desconfiam menos); você controla o equipamento | depende da sua internet e da energia |
| **VPS Linux** (nuvem) | não cai com a energia; acesso de qualquer lugar | **IP de datacenter** pode ser bloqueado por lojas/captcha e olhado com desconfiança pelo WhatsApp; mensalidade; **não testado** neste kit |
| Raspberry Pi | barato | **não testado** (Chromium/Node em ARM podem exigir ajustes) |

Se escolher VPS: mínimo **2 GB de RAM, 20 GB de disco, Debian 13**, IP fixo, e prepare-se para resolver captcha com mais frequência.

## Rede e segurança do servidor
- **Nenhuma porta precisa ser aberta na internet.** O robô só faz conexões de saída. O único acesso é o **SSH** (de preferência só pela rede local ou por VPN como o Tailscale). Veja `11-seguranca-e-backup.md`.
- IP fixo **local** (reserva no roteador) facilita o acesso por SSH.
- Internet estável; o consumo de dados é pequeno (texto e fotos).

## O que você NÃO precisa
- Placa de vídeo, IA, Docker, banco de dados externo, domínio ou site.
- O estúdio de vídeo (Reels, voz) é **outro computador, opcional** (um PC potente); o servidor só recebe os vídeos prontos. Veja `08-conteudo-e-reels.md`.

## Antes de comprar: checklist
- [ ] x86-64, 4 núcleos, **2 GB de RAM ou mais**
- [ ] 8 GB de armazenamento interno **ou mais** (+ um pendrive de 16 GB)
- [ ] porta **Ethernet**
- [ ] consegue instalar Debian/Ubuntu (a maioria dos thin clients e mini PCs sim; confira se aceita boot por USB)
- [ ] um lugar com **energia estável** e, de preferência, um nobreak
