# 12 — Riscos legais e termos de uso

> **Não é aconselhamento jurídico.** É um mapa dos riscos que o autor conhece. Antes de **vender** ou **operar em escala**, consulte um advogado e leia os termos atuais de cada plataforma (eles mudam).

## 1. WhatsApp (o maior risco operacional)
- O conector usa **Baileys**, biblioteca **não oficial**. Os Termos do WhatsApp proíbem automação não autorizada. O número pode ser **banido**, e isso pode acontecer sem aviso.
- Mitigação já embutida: ritmo aleatório, teto diário, silêncio na madrugada, só envio, só grupos onde a pessoa entrou.
- Mitigação sua: **número dedicado**, começar devagar, não usar disparo em massa a contatos, manter plano B (Telegram, lista de transmissão, outro número).
- Alternativa oficial: **WhatsApp Business Platform (API oficial)** — paga por conversa, com modelos de mensagem; não substitui grupos. Não implementada aqui.

## 2. Programas de afiliado
Cada programa tem termos próprios. O que o autor aplica:
| Programa | Regra relevante | O que o robô faz |
|---|---|---|
| **Mercado Livre** | link só do próprio afiliado; contas podem ser **suspensas** por irregularidade | usa o link oficial do navegador logado; pausa por data se a conta for suspensa (`ML_PAUSED_UNTIL`) |
| **Shopee** | usar a Open API conforme os termos; sem fraude de clique | usa a API; não clica nos próprios links |
| **AliExpress** | tracking ID próprio; sem tráfego incentivado enganoso | usa API/Portals |
| **Awin (KaBuM, Samsung)** | comissão cancelada se o pedido usou **cupom que não veio da Awin** | nunca publica cupom de terceiros nessas lojas (`NO_OUTSIDE_COUPON_HOSTS`) |
- **Você** é o responsável pela sua conta de afiliado. Nunca compartilhe a conta com outras pessoas.
- Não faça "autoclique", não compre pelo próprio link para ganhar comissão sem consumo real.

## 3. Fontes e raspagem
- O robô prefere **APIs oficiais** e feeds. Para algumas fontes lê páginas públicas (ex.: Pelando). Termos de uso de sites podem restringir raspagem automatizada.
- Regras do projeto: respeitar limites (1 requisição por segundo nas listas), parar ao primeiro 403/429/captcha, **não burlar captcha** nem anti-bot, não derrubar o site.
- **Canais de promoção de terceiros** (ex.: páginas públicas do Telegram) só entram como **fonte de emergência** (`TG_CHANNELS`, vazio por padrão) e nunca como base: copiar a curadoria de outros grupos pode ser antiético e juridicamente discutível. O kit guarda **só o padrão** (modelo do produto, tipo de cupom), nunca o texto deles.

## 4. Direitos autorais
- **Fotos:** use só a foto do **próprio anúncio** (ou da página da loja). O robô nunca busca imagem em outro lugar (risco de direito de imagem e de produto errado).
- **Marcas e logotipos:** você pode citar o nome do produto/loja para identificar a oferta; não use logotipos de terceiros como se fossem seus.
- **Músicas:** use faixas de licença que permitam uso comercial (o autor usa bibliotecas livres para uso comercial; confira cada licença).
- **Conteúdo de terceiros** (notícias): o módulo de novidades usa manchete + resumo do feed + **fontes citadas**; não copia o texto.

## 5. Publicidade no Brasil
- Post de oferta com link de afiliado é **publicidade**: identifique (`#Anuncio`, `#publi`). O robô põe `#Anuncio` por padrão (`POST_HASHTAG`).
- Siga o **Código CONAR** e o **Código de Defesa do Consumidor**: preço e condições corretos, sem propaganda enganosa. O robô afirma só o que sabe (desconto calculado, histórico, cupom) e avisa "Preço pode variar" e "enquanto durarem os estoques".
- **Cupom:** o robô mostra como **sugestão** ("Tente o cupom…"), porque não consegue confirmar se vale para o anúncio.

## 6. Dados pessoais (LGPD)
- O robô não coleta dados dos participantes dos grupos. Se você guardar contatos, precisa de base legal (consentimento) e segurança.
- Documente quem tem acesso ao servidor. Fotos de clientes só com autorização.

## 7. Redes sociais (Meta, YouTube, TikTok)
- Use apenas as **APIs oficiais** e respeite as **políticas de plataforma** (limites de postagem, spam, conteúdo). Contas com muito disparo ou comportamento artificial podem ser limitadas.
- O TikTok exige **auditoria** para postagem pública por API (ver `07-redes-sociais.md`).
- Não automatize o login de contas pessoais.

## 8. Se você for vender ou revender este kit
- Defina uma **licença** (o `LICENSE` do V0 é provisório) e um **contrato** com escopo, o que está incluso, limites de suporte e **isenção**: o autor não controla contas de terceiros nem garante resultado.
- Cada cliente usa **suas** contas e chaves. Nunca ponha contas do cliente em um servidor seu sem contrato claro.
- Deixe explícito o risco de bloqueio do WhatsApp (item 1) por escrito.
- Veja `17-comercial.md`.

## 9. Resumo de "o que nunca fazer"
1. Burlar captcha ou usar contas de terceiros sem autorização.
2. Publicar cupom de terceiros em lojas cujo programa proíbe (KaBuM/Samsung via Awin).
3. Prometer preço/estoque/resultado que o robô não conhece.
4. Usar foto que não é do anúncio.
5. Disparar mensagens para pessoas que não pediram.
6. Guardar segredos no Git.
