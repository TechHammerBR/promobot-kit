# 14 — Problemas comuns (e como resolver)

Primeiro de tudo: `ctl status`, `ctl diag`, `ctl alertas 20`. O `diag` aponta a causa mais provável.

## Não está postando
| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `posts_hoje` parado e `ofertas_na_fila` > 0 | fora do horário ativo, teto diário atingido, robô pausado, ou mix esperando oferta do Mercado Livre | `ctl status` (veja `pausado`, `limite_diario`); `ctl retomar`; ajuste `DAILY_POST_LIMIT` ou os intervalos |
| `ofertas_na_fila` = 0 | fontes bloqueadas ou sem resposta | `ctl alertas`; veja `SourceHealth`; teste a internet/DNS do servidor |
| `whatsapp_conectado: false` | sessão caiu | `curl 127.0.0.1:3000/status`; reinicie `promobot-wa`; se continuar, **parear de novo** (`06`) |
| só Shopee/AliExpress saindo | ML sem link (login/captcha) | veja a linha abaixo sobre o Mercado Livre |

## Mercado Livre: "Publicação falhou 3x seguidas (login do ML expirou?)"
A mensagem típica é `Locator.wait_for ... "Compartilhar" ... Timeout`. Causas, em ordem:
1. **reCAPTCHA** do ML ("Por segurança, complete esta etapa"): acontece depois de reiniciar o navegador/queda de energia ou muita atividade. O robô **não burla**. Veja a tela: `GET http://127.0.0.1:8000/shot?url=<produto>` salva um print em `data/linkgen/shot.png`. Resolva à mão pelo VNC (`05`) **ou espere**: já liberou sozinho em horas. Enquanto isso o robô segue com Shopee/AliExpress e o ML fica pausado por 60 min a cada falha.
2. **Login expirou:** `curl 127.0.0.1:8000/health` → `logged_in:false` → refaça o login pelo VNC.
3. **Layout mudou:** o botão "Compartilhar" na barra preta de afiliados mudou de lugar/nome → ajuste `linkgen/server.py` (função que gera o link).
4. **Conta suspensa:** veja o painel de afiliados; use `ML_PAUSED_UNTIL`.

## Foto estranha no post (madeira, banner, pessoa…)
- O Wyse valida foto **por medidas** (`photocheck.py`), sem IA: pode deixar passar casos raros. Foi assim que uma textura de madeira (quadro de vídeo do anúncio) foi postada; a regra "sem produto em destaque" corrigiu.
- Para ver por que uma foto passou/foi barrada: `PYTHONPATH=. venv/bin/python -c "from PIL import Image; from app import photocheck; print(photocheck.avaliar(Image.open('foto.jpg')))"`.
- Mande o **print** do caso e recalibre com `ferramentas/calibrar_foto.py`. Evite afrouxar limites sem testar em ~150 fotos reais.

## Sem energia / reiniciou sozinho
- `uptime -s` mostra quando ligou. Após o boot, os serviços sobem sozinhos.
- Confira: WhatsApp reconectou? ML pediu login/captcha? `ctl alertas`.
- Se aconteceu várias vezes: **nobreak**; BIOS em "ligar após queda de energia"; não force desligamento (corrompe o banco).

## "Temporary failure in name resolution"
Sem DNS/internet no servidor. Teste `ping 1.1.1.1` e `ping google.com`. Costuma passar quando a internet volta; as fontes pausam e retomam sozinhas.

## Memória baixa (`Wyse com pouca memória livre`)
Normal perto do limite em 2 GB. Veja os maiores consumidores: `ps -eo rss,comm --sort=-rss | head`. O Chromium do `linkgen` é o maior; reinicie `promobot-linkgen` se passar de ~1 GB. Garanta swap/zram. Sem ML por navegador o uso cai muito.

## "Ofertas repetidas" ou "mesmo produto duas vezes"
- Regra: `REPEAT_DAYS=3` e exceção de queda ≥ 30%. Produto igual com **link diferente** pode escapar; confira `product_key` em `engine.py`.
- Se quiser mais rigidez, aumente `REPEAT_DAYS` (ex.: 5).

## Posts sem cupom
Veja se há códigos ativos: `ctl cupons-ativos` (leitura). Se vazio, a fonte (Pelando) pode ter mudado de layout. O robô só sugere cupom **seguro** (valor mínimo cabe, categoria certa).

## YouTube: Short não agendou / "quota"
- A cota diária da API é pequena (~6 envios). O robô agenda 1 Short por rodada e tenta 3 vezes; depois publica na hora do Reel.
- O vídeo **privado agendado** aparece no YouTube Studio com data de publicação. Para corrigir um Short já agendado, apague no Studio (a API não apaga).

## Meta (Instagram/Facebook): erro de token
- Primeiro passo para qualquer rede social: `venv/bin/python ferramentas/social_verificar.py` (só leitura; mostra qual rede falhou e por quê).
- `meta_conectar.py` diz **"nenhuma Pagina veio no token"**: ao gerar o token, na janela da Meta você precisa **marcar a Página e o Instagram**; gere de novo.
- `meta_conectar.py` diz **"Pagina nao tem Instagram profissional vinculado"**: converta o Instagram para conta profissional e vincule à Página (Página → Configurações → Contas vinculadas).
- **"a Meta recusou o token"**: o token do Explorador vale ~1 hora; gere outro e rode de novo.
- `social_verificar.py` mostra **Permissões: FALTAM ...**: gere o token de novo adicionando essas permissões e rode `meta_conectar.py` outra vez.
- `threads_conectar.py`: **token recusado** = o token do gerador vale ~1 h; confira também se a sua conta está como *Testador do Threads* e se você aceitou o convite no app do Threads.
- `youtube_conectar.py`: a página do Google dá **"não foi possível conectar"** = faltou o túnel `ssh -L 8765:127.0.0.1:8765` aberto no seu computador. **"não devolveu o refresh token"** = remova o acesso do app em `myaccount.google.com/permissions` e rode de novo. YouTube que para de funcionar depois de 7 dias = a tela de consentimento está em *teste*: publique o app.
- `meta_token` nos alertas: o token venceu/foi revogado → gere outro e rode `meta_conectar.py` (`07`).
- Vídeo recusado no Instagram: precisa de **upload direto**; confira tamanho/formato (MP4 H.264/AAC, 9:16).

## Alertas "gatry: 0 ofertas extraídas"
Fonte sem itens (ou de nicho que você não usa). Pode ignorar ou desligar o coletor.

## Banco "database is locked" / lento
SQLite sob carga. Reinicie o robô; a manutenção noturna compacta o banco. Se o volume crescer, migre para PostgreSQL (`DATABASE_URL`).

## Problemas que apareceram no teste de instalação (VM, 28/10/2026)
| Sintoma | Causa | Solução |
|---|---|---|
| `adduser: command not found` | imagem mínima de Debian | `sudo apt install -y adduser sudo` |
| `fatal: could not read Username for 'https://github.com'` | repositório **privado** sem login | token, `gh auth login` ou ZIP (`03`, passo 3) |
| `Name or service not known` ao publicar | padrões antigos apontavam para nomes de Docker (`wa`, `linkgen`, `ollama`) | já corrigido: o kit usa `127.0.0.1` |
| `Connection refused` e alerta "login do ML expirou?" sem ter usado o ML | oferta do ML tentando o navegador que não está logado | perfil leve: `ML_PAUSED_UNTIL` + `ML_BONUS_MODE` (já no `.env.example`) |
| coleta traz `verificacao anti-robo` do Mercado Livre | o ML pede verificação a robôs sem o navegador logado | esperado; o robô **não** burla; veja `05` |
| `./backup.sh: Permission denied` | script sem permissão de execução | `chmod +x backup.sh ferramentas/*.sh` (o Git do kit já guarda o +x) |
| `perl: warning: Setting locale failed` ao instalar pacotes | locale não configurado | inofensivo; opcional: `sudo apt install locales && sudo dpkg-reconfigure locales` |
| `ctl diag` diz "IA local fora do ar" / "gerador de links fora do ar" | o diagnóstico cobrava serviços que estão desligados de propósito | já corrigido |
| 2 testes falhando (`catchup`, `canal_de_casa`) | data fixa no teste + regra de casa mudou | já corrigido |

## Quando pedir ajuda ao Claude
Use `prompts/08-diagnostico-e-manutencao.md`: ele já traz o roteiro (rodar `status`, `diag`, `alertas`, ler logs) e as regras de segurança.
