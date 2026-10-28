from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Banco: SQLite local; em produção troque por postgresql+psycopg://...
    database_url: str = f"sqlite:///{(DATA_DIR / 'promobot.db').as_posix()}"

    # Telegram (vazio = modo simulação, posts vão para data/outbox.log)
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    shopee_trending_per_cycle: int = 3  # palavras 'quentes' (app/trending.py) buscadas na Shopee a cada ciclo
    pelando_every: int = 5  # Pelando no máx. 1 a cada N posts do canal (apoio; foco é Shopee/ML)
    telegram_post_enabled: bool = True  # false = não posta ofertas no canal do Telegram (pedido do dono 22/10)
    telegram_admin_chat_id: str = ""

    # Afiliados
    shopee_app_id: str = ""
    shopee_secret: str = ""
    shopee_keywords: str = ("mouse gamer redragon,teclado mecanico redragon,headset gamer hyperx,mouse logitech,teclado logitech,"
                            "ssd kingston,ssd nvme 1tb,memoria ram ddr4 kingston,memoria ddr5,fone qcy,fone baseus,fone edifier,"
                            "fone jbl bluetooth,controle 8bitdo,controle gamesir,controle xbox,controle ps5 dualsense,webcam logitech,"
                            "microfone fifine,monitor gamer,carregador baseus,carregador anker,hub usb c ugreen,cooler deepcool,"
                            "water cooler,placa de video,processador ryzen,placa mae gigabyte,fonte corsair,gabinete gamer,"
                            "roteador tp-link,smartphone xiaomi,smartphone samsung galaxy,smartwatch amazfit,tablet samsung,"
                            "pendrive sandisk,cartao micro sd sandisk,hd externo,caixa de som jbl,mousepad gamer,cadeira gamer,"
                            "teclado akko,teclado aula,mouse attack shark,headset redragon,notebook lenovo,notebook acer,ssd crucial")
    shopee_keywords_per_cycle: int = 3  # palavras por coleta (rodízio); a API permite 2000 chamadas/hora
    shopee_limit: int = 30
    shopee_min_price: float = 30.0
    shopee_min_rating: float = 4.7
    shopee_min_sold: int = 20
    shopee_mall_only: bool = True  # só loja oficial (Shopee Mall): loja indicada ainda vendia Logitech G304 falso a R$ 58
    shopee_max_discount: int = 70  # desconto acima disso em marca famosa costuma ser falsificado
    shopee_every: int = 3  # no máximo 1 Shopee a cada N posts (como o AliExpress)

    # Regras
    min_discount_pct: int = 30  # tecnologia (foco do canal)
    absurd_discount_pct: int = 60  # fora de tecnologia: só oferta absurda, e a IA ainda avalia
    dedupe_hours: int = 24
    collect_interval_min: int = 15
    max_posts_per_cycle: int = 10  # (legado)
    publish_interval_sec: int = 60  # (legado: substituído pelo intervalo variável abaixo)
    # Ritmo humano no WhatsApp: intervalo aleatório (minutos), menor nos horários de pico
    interval_min: float = 10
    interval_max: float = 18
    peak_interval_min: float = 7
    peak_interval_max: float = 12
    peak_hours: str = "11-14,19-23"  # faixas [início, fim) em horário de Brasília
    daily_post_limit: int = 50  # teto de posts de oferta por dia (cupons não contam)
    limit_reset_at: str = ""  # ISO; zera a contagem do dia a partir deste momento (ex.: liberar mais posts em dia de teste)
    repeat_min_drop: float = 0.30  # dentro de REPEAT_DAYS só repete se o preço novo for >= 30% menor que o da última vez (dono, 23/10)
    repeat_days: int = 3  # mesmo produto não volta antes disso
    queue_max_hours: int = 6  # oferta mais velha que isso na fila expira
    linkgen_url: str = "http://linkgen:8000"
    linkgen_enabled: bool = True  # navegador logado (ML: meli.la e cupons gerais). False no robô leve sem navegador
    ml_bonus_mode: bool = False  # com ML_PAUSED_UNTIL ativo: segue coletando ML e posta como BÔNUS (link limpo, sem comissão, sem abrir a página do produto)
    ml_paused_until: str = ""  # AAAA-MM-DD: até esta data não coleta/posta ML (conta de afiliado suspensa)
    # canais públicos de promoção do Telegram lidos como fonte (página t.me/s/<canal>, sem login); vazio = desligado
    tg_channels: str = ""  # canais publicos do Telegram lidos so como FONTE DE EMERGENCIA (t.me/s/<canal>, sem login); vazio = desligado
    tg_emergency_queue: int = 8  # só lê os canais se a fila tiver MENOS que isso (0 = nunca)
    tg_max_age_h: int = 3  # oferta de canal vence rápido
    tg_max_links_per_cycle: int = 25  # encurtadores abertos por coleta (1 por segundo)
    tg_temp: int = 120  # peso no score (equivale a uma oferta morna do Pelando)
    pelando_enabled: bool = True  # ofertas votadas do Pelando (só AliExpress/ML)
    pelando_min_temp: int = 100   # temperatura (votos) mínima
    pelando_bonus_min_temp: int = 100  # outras lojas (sem comissão, mantém o grupo movimentado): tecnologia votada
    pelando_bonus_any_temp: int = 400  # qualquer categoria se bombando (passa pela IA de curadoria)
    pelando_max_age_h: int = 12  # 14/10: 48 h trazia preço que já tinha mudado na loja   # só ofertas postadas nas últimas N horas
    pelando_search_terms: str = ("ssd,ssd nvme,ssd externo,hd externo,placa de video,rtx,radeon,processador,ryzen,intel core,placa mae,memoria ram,memoria ddr5,fonte,gabinete,water cooler,cooler,pasta termica,monitor,monitor gamer,monitor 144hz,monitor ultrawide,teclado,teclado mecanico,mouse,mouse gamer,mousepad,headset,fone gamer,microfone,webcam,controle,dualsense,controle xbox,cadeira gamer,mesa gamer,notebook,notebook gamer,macbook,mini pc,tablet,ipad,kindle,iphone,galaxy,celular,smartphone,motorola,xiaomi,poco,apple watch,smartwatch,fone bluetooth,airpods,caixa de som,soundbar,roteador,pendrive,cartao de memoria,impressora,smart tv,tv 4k,projetor,echo dot,fire tv,gopro,drone,carregador,power bank,hub usb,playstation,ps5,xbox,nintendo switch,steam deck,jogo ps5,jogo xbox,jogo pc,gift card,steam,jbl,logitech,redragon,hyperx,kingston,corsair,razer,asus,gigabyte,samsung,lg,dell,lenovo,acer,tp-link")
    pelando_search_per_cycle: int = 16  # termos buscados por coleta (rodízio): ~1 s cada
    pelando_search_min_temp: int = 40  # na busca por palavra de tecnologia o voto mínimo é menor (a busca já filtra o assunto)
    ali_enabled: bool = True
    ali_every: int = 3  # no máximo 1 post do AliExpress a cada N (a nota dele é inflada pelo "preço antigo" e tomava a fila toda)
    mix_enabled: bool = True  # dono 25/10/2026: Mercado Livre >= 50%, AliExpress <= 15%, resto Shopee; lojas sem afiliado nao saem (false = rodizio antigo)
    mix_ml: float = 0.50  # meta de Mercado Livre nos ultimos MIX_JANELA posts do canal
    mix_ali: float = 0.15  # teto de AliExpress
    mix_piso_ml: float = 0.30  # abaixo disso (tech) e sem oferta ML na fila, o grupo espera em vez de encher de Shopee/AliExpress
    mix_piso_ml_lar: float = 0.20  # idem na casa (o ML tem menos oferta de casa)
    mix_janela: int = 20
    # API oficial de afiliados (app/aliapi.py). Com as chaves preenchidas o navegador (linkgen) não é usado para o AliExpress.
    ali_app_key: str = ""
    ali_app_secret: str = ""
    ali_tracking_id: str = "default"  # Portals > Account > Tracking ID
    ali_category_ids: str = "7,44,509,502"  # informática, eletrônicos, celulares, componentes (vazio = todas)
    # buscas por MARCA conhecida (13/10: a busca genérica trazia placa X99/memória/fonte sem procedência)
    ali_keywords: str = ("gamesir controller,8bitdo controller,qcy earbuds,baseus earbuds,baseus usb c hub,ugreen usb c hub,"
                         "ugreen nvme enclosure,anker charger,soundcore earbuds,edifier,kz earphones,trn earphones,fifine microphone,"
                         "emeet webcam,rapoo mouse,logitech mouse,redragon keyboard,akko keyboard,aula keyboard,royal kludge keyboard,"
                         "ajazz keyboard,attack shark mouse,machenike,haylou,xiaomi,redmi,poco smartphone,amazfit,kingston ssd,"
                         "kingston ddr4,crucial ddr5,lexar ssd,lexar ddr5,netac ssd,netac ddr4,sandisk,adata,deepcool cooler,"
                         "thermalright cooler,id-cooling,cooler master,orico,hagibis,tp-link,ryzen processor,gigabyte motherboard,"
                         "msi motherboard,asus,samsung ssd,ulanzi,smallrig,teclast tablet,flydigi,tangzu,moondrop,epomaker,keychron,machinist motherboard,machinist x99,juhor ddr4,juhor ddr5,mougol")
    ali_known_brands_only: bool = True  # busca do AliExpress só publica marca da lista app/titles.MARCAS
    ali_keywords_per_cycle: int = 5  # palavras buscadas por coleta (rodízio): ~1 s cada pela API (~25 s no Portals)
    ali_min_sold: int = 10  # mínimo de vendas para confiar no produto
    ali_min_price: float = 40.0  # corta peças avulsas/acessórios minúsculos (R$)
    simulate_posts: bool = False
    # Texto dos posts
    group_invite_link: str = ""  # ex.: link de convite do grupo/canal do WhatsApp
    group_invite_label: str = "Grupo no WhatsApp"
    telegram_invite_link: str = ""  # quando existir o canal do Telegram
    post_hashtag: str = "#Anuncio"
    coupon_refresh_hours: int = 6
    # Canais / serviços internos
    whatsapp_group_name: str = ""  # vazio = WhatsApp desligado
    whatsapp_number: str = ""  # número do robô (só dígitos, com 55) para gerar código de pareamento
    wa_url: str = "http://wa:3000"
    ollama_url: str = "http://ollama:11434"
    ai_enabled: bool = True
    content_enabled: bool = True  # agenda de conteúdo (stories, feed, educativo, jogos, reels). False no robô leve (só grupos)
    ai_model: str = "qwen3-vl:8b-instruct"  # modelo ÚNICO (texto+visão+comandos), 100% na RTX 4060
    vision_model: str = "qwen3-vl:8b-instruct"  # valida se a foto é do produto (mesmo modelo: sem troca na GPU)
    # SEGUNDO CANAL (14/10/2026): comunidade do WhatsApp "Meu lar, minha oferta" = ofertas de CASA (cozinha, eletrodomésticos,
    # limpeza, cama/mesa/banho, móveis, ferramentas). Mesma coleta; a oferta vai para o canal "lar" quando o título é de casa
    # (engine.canal_de). Posta SÓ no grupo de avisos da comunidade (id fixo: o nome se repete na comunidade e no grupo de avisos).
    store_whatsapp: str = ""  # numero da loja so com digitos (5511999999999): vira o link wa.me/ dos orcamentos
    lar_enabled: bool = False
    lar_whatsapp_group_id: str = ""  # id do grupo de avisos (termina em @g.us); o conector wa lista os grupos em /groups
    lar_invite_link: str = ""  # convite do grupo/comunidade de casa (chat.whatsapp.com/...)
    lar_nome: str = "Ofertas para casa"
    lar_hour_start: int = 7  # público de casa: sem notificação de madrugada
    lar_hour_end: int = 23
    lar_daily_limit: int = 40  # começo conservador (número pessoal + conector não oficial = risco de bloqueio)
    lar_peak_interval_min: float = 2.5  # casa: intervalo nos horários de pico (PEAK_HOURS)
    lar_peak_interval_max: float = 3.5
    lar_interval_min: float = 12
    lar_interval_max: float = 20
    lar_min_discount_pct: int = 30
    ml_tag_tech: str = ""  # etiqueta do afiliado ML por canal (Administrar etiquetas)
    ml_tag_lar: str = ""
    lar_min_price: float = 8.0  # grupo de casa aceita "coisinha" barata (potes, utensílios) — pedido do grupo, 14/10
    lar_pelando_min_temp: int = 100  # páginas gerais do Pelando: oferta de casa votada
    lar_keywords: str = (
        "cozinha,panela,frigideira,caçarola,assadeira,forma de bolo,chaleira,cafeteira,café expresso,nespresso,dolce gusto,"
        "liquidificador,batedeira,mixer,processador de alimentos,espremedor,centrífuga,sanduicheira,grill,torradeira,"
        "air fryer,airfryer,fritadeira,forno elétrico,micro-ondas,microondas,fogão,cooktop,coifa,depurador,geladeira,refrigerador,"
        "freezer,frigobar,lava-louças,lava louças,lava e seca,máquina de lavar,lavadora de roupas,secadora,tanquinho,"
        "aspirador,robô aspirador,mop,vassoura,ferro de passar,vaporizador,purificador de água,filtro de água,bebedouro,"
        "ventilador,climatizador,ar-condicionado,ar condicionado,aquecedor,umidificador,desumidificador,"
        "colchão,travesseiro,edredom,jogo de cama,lençol,cobertor,toalha,cortina,tapete,sofá,poltrona,cadeira,mesa de jantar,"
        "guarda-roupa,cômoda,estante,rack,sapateira,organizador,pote,potes,marmita,garrafa térmica,copo térmico,"
        "faqueiro,jogo de facas,talheres,jogo de pratos,aparelho de jantar,copos,taças,utensílios,"
        "furadeira,parafusadeira,serra,lixadeira,jogo de ferramentas,caixa de ferramentas,lavadora de alta pressão,"
        "mangueira,jardim,churrasqueira,lâmpada,luminária,abajur,fechadura,"
        "detergente,sabão,amaciante,lava-roupas,desinfetante,papel higiênico,papel toalha,limpeza,"
        "tramontina,electrolux,brastemp,consul,mondial,philco,britânia,britania,oster,arno,wap,black+decker,midea,"
        "walita,cadence,tefal,rochedo,mallory,polishop,ypê,omo,vileda,karcher,kärcher,makita,bosch,dewalt,vonder"
        ",prateleira,nicho,suporte de parede,cabideiro,cabide,sapateira,organizador de gaveta,caixa organizadora,cesto,porta-toalha,porta toalha,toalheiro,saboneteira,dispenser,porta escova,tapete de banheiro,kit banheiro,lixeira,box de banheiro,chuveiro,ducha,torneira,assento sanitário,espelho,escorredor,tábua de corte,tabua de corte,potes herméticos,pote hermético,porta-tempero,porta tempero,jogo de copos,xícara,xícaras,caneca,pano de prato,avental,luva térmica,jogo americano,toalha de mesa,porta-copos,descanso de panela,espátula,concha,colher de silicone,utensílios de silicone,forma de bolo,assadeira,ralador,abridor,peneira,fruteira,porta-frios,boleira,garrafa,squeeze,lancheira,jogo de toalhas,toalha de banho,toalha de rosto,roupão,edredom,colcha,manta,cobertor,protetor de colchão,fronha,almofada,capa de almofada,capa de sofá,cortina,persiana,tapete,passadeira,varal,cesto de roupa,prendedor,tábua de passar,mop giratório,balde,rodo,vassoura,esponja,pano de chão,vaso,quadro,relógio de parede,luminária,abajur,fita de led,lâmpada,arandela,difusor,vela aromática")
    lar_pelando_terms: str = ("air fryer,jogo de panelas,frigideira,potes hermeticos,jogo de copos,talheres,faqueiro,"
                              "utensilios de cozinha,escorredor,tabua de corte,garrafa termica,cafeteira,liquidificador,"
                              "jogo de toalhas,toalha de banho,jogo de cama,edredom,travesseiro,cobertor,cortina,tapete,"
                              "organizador,caixa organizadora,prateleira,sapateira,cabide,kit banheiro,lixeira,chuveiro,"
                              "tramontina,electrolux,mondial,oster,wap,aspirador,ventilador,luminaria,"
                              "mop,varal,cesto de roupa,papel higienico,sabao,amaciante,detergente,furadeira,caixa de ferramentas")
    lar_shopee_keywords: str = ("jogo de toalhas,toalha de banho,jogo de cama,edredom,travesseiro,cortina,tapete sala,"
                                "organizador de gaveta,caixa organizadora,prateleira,nicho,sapateira,cabide,porta toalha,"
                                "kit banheiro,lixeira,potes hermeticos,jogo de copos,talheres,utensilios de silicone,escorredor,"
                                "tabua de corte,garrafa termica,jogo de panelas,frigideira,air fryer,cafeteira,liquidificador,"
                                "aspirador de po,mop giratorio,varal,luminaria,fita led,almofada,manta sofa,jogo americano")
    lar_shopee_por_ciclo: int = 4  # palavras de casa por coleta (era 2: o grupo ficava com a fila vazia)
    lar_pelando_por_ciclo: int = 8
    lar_basicos: str = "chinelo,chinelos,sandália,sandalia,rasteirinha,camiseta,camisetas,regata,blusa,legging,leggings,calça legging,short,shorts,bermuda,top fitness,top academia,meia,meias,cueca,cuecas,calcinha,calcinhas,sutiã,sutia,pijama,moletom,jaqueta,vestido,boné,bone,mochila,bolsa,necessaire,carteira,guarda-chuva,shampoo,xampu,condicionador,máscara capilar,sabonete,desodorante,antitranspirante,creme dental,pasta de dente,escova de dente,fio dental,enxaguante bucal,absorvente,protetor solar,hidratante,loção,perfume,colônia,esmalte,maquiagem,batom,rímel,pó compacto,escova de cabelo,pente,secador de cabelo,chapinha,barbeador,aparelho de barbear,cotonete,algodão,lenço umedecido,fralda,fraldas,sérum,skincare,protetor labial,garrafa squeeze,coqueteleira,corda de pular,faixa elástica,tapete de yoga,halter,halteres,caneleira,luva de treino,dry fit,academia,whey,creatina,ração,petisco,coleira,areia sanitária,brinquedo,mamadeira,chupeta,saco de lixo,pano de prato,pano de chão,pano microfibra,flanela,luva de borracha,balde,bacia,lancheira,caixa térmica,porta-treco,chaveiro,caderno,caneta,lápis,estojo,mochila escolar,conjunto infantil,conjunto feminino,conjunto masculino,camisa,camisas,calça,calcas,bermudas,roupa,tênis,tenis,sapatilha,cinto,macacão,body,babador,kit cuecas,kit meias,toalha de rosto,desodorante roll-on,hidratante corporal,sabonete líquido,esponja,vassoura,rodo,cabide,varal,tapete de banheiro"  # dia a dia (higiene, beleza, roupa, fitness, pet, utilidades): classifica como CASA
    lar_busca_shopee_basicos: str = "chinelo slide,sandalia feminina,camiseta dry fit,legging academia,top academia,short academia,meias esportivas,cueca boxer,pijama feminino,shampoo,condicionador,sabonete liquido,desodorante,creme dental,escova de dente,protetor solar,hidratante corporal,perfume,esmalte,kit skincare,secador de cabelo,chapinha,barbeador,absorvente,fralda,lenco umedecido,garrafa squeeze,coqueteleira,corda de pular,faixa elastica,tapete yoga,halter,mochila,necessaire,guarda-chuva,saco de lixo,pano de prato,pano microfibra,esponja de cozinha,balde,lancheira,caixa termica,caderno,caneta,racao,brinquedo"
    lar_busca_pelando_basicos: str = "chinelo,sandalia,camiseta,legging,roupa de academia,meias,cueca,pijama,shampoo,condicionador,sabonete,desodorante,creme dental,protetor solar,hidratante,perfume,esmalte,secador de cabelo,barbeador,absorvente,fralda,lenco umedecido,garrafa termica,squeeze,mochila,necessaire,saco de lixo,pano de prato,lancheira,caderno,racao,brinquedo"
    # CONVITE AOS CONTATOS (14/10/2026, decisão do dono ciente do risco de bloqueio): N contatos por dia recebem o convite dos dois
    # grupos, 1 mensagem a cada 1,5–4 min, quem já está nos grupos é pulado; texto em app/assets/convite.txt.
    convite_enabled: bool = False
    convite_por_dia: int = 50
    convite_hora: str = "10:30"
    # 13/10/2026 (dono): robô 24/7, parado só das 3h às 6h (janela de backup 03:40 e manutenção 04:20).
    active_hour_start: int = 6  # publica das 6h...
    active_hour_end: int = 27  # ...até as 3h do dia seguinte (acima de 24 = vira a noite; 24 = até meia-noite)
    night_hours: str = "0-3"  # madrugada: ritmo mais lento para não encher o grupo de notificações
    night_interval_min: float = 20
    night_interval_max: float = 30
    bot_ai_num_gpu: int = 0  # 08/10/2026: SEM GPU (a RTX 4060 morreu): IA só na CPU (foto ~40 s, curadoria ~14 s). Com placa nova: 99 = todas as camadas na GPU
    # REGRAS DOS PROGRAMAS DE AFILIADO (Awin, 13/10): KaBuM e Samsung cancelam a comissão de venda com cupom que não veio da Awin
    # -> nessas lojas o robô nunca publica cupom de terceiros nem oferta cujo preço depende de cupom
    # histórico de preço (app/pricehist.py): desconto falso x menor preço
    price_history_min_days: int = 3  # dias de histórico antes de julgar
    price_history_window_days: int = 30
    price_drop_pct: float = 5.0  # abaixo do menor preço já visto em pelo menos X% = "menor preço em N dias"
    offer_coupon_hint: bool = True  # sugere no post um cupom ativo da loja (ML/Shopee) ou autorizado pela Awin (KaBuM)
    # Awin (app/awin.py): conta do publisher (AWIN_PUBLISHER_ID). Samsung (25539) fica FORA do mapa: só pode promoção vinda da própria Awin.
    awin_publisher_id: str = ""
    awin_token: str = ""  # token OAuth2 da API (atalho "Gravar token Awin"); sem ele vale só AWIN_APPROVED_MIDS
    awin_merchants: str = "kabum.com.br:17729"  # loja:ID do anunciante
    awin_approved_mids: str = ""  # aprovações informadas à mão (o token descobre sozinho)
    no_outside_coupon_hosts: str = "kabum.com.br,samsung.com"
    shopee_coupons_enabled: bool = True  # cupons com código da Shopee (Pelando), igual ao do Mercado Livre
    shopee_code_post_gap_hours: float = 1  # cupom da Shopee esgota em ~1 h: avisa rápido
    code_post_gap_hours: float = 3  # cupons com código (Pelando): no máx. 1 post a cada N horas, só se houver código novo
    coupon_post_hour: int = 6  # post diário de cupons gerais
    # Identidade do canal (artes das redes sociais)
    brand_name: str = "Ofertas Tech"
    brand_color: str = "#1E2A78"
    accent_color: str = "#FF3D57"
    social_cta: str = "LINK DO GRUPO NA BIO"
    # Status do WhatsApp (recorrente). Desligado até o dono aprovar a prévia.
    voice_enabled: bool = False  # narração com a voz do dono nos Reels (serviço /opt/apps/voicelab); ligar após aprovação do dono
    voice_url: str = "http://voice:8300"
    voice_style: str = "neutro"  # neutro | solto | animado | vibrante (estilos medidos em voicelab/lab/expressivo.py)
    threads_enabled: bool = True  # Threads (app/threads.py)
    threads_token: str = ""
    social_enabled: bool = True  # Meta: Página + Instagram (app/social.py)
    meta_page_id: str = ""
    meta_ig_id: str = ""
    meta_page_token: str = ""
    social_story_times: str = "11:00,14:00,18:00,21:00"  # 4/dia (dono: sem poluição visual)
    social_feed_time: str = "19:30"
    social_feed_days: str = "mon,wed,fri"  # oferta no feed só nesses dias (feed = vitrine da loja)
    games_day: str = "thu"
    edu_day: str = "tue"  # carrossel educativo da loja (app/content.py)
    edu_time: str = "19:00"
    games_time: str = "13:00"  # Epic libera grátis qui 12h
    games2_day: str = "mon"  # 2ª edição: ofertas semanais da Steam começam na segunda
    games2_time: str = "19:00"
    status_enabled: bool = False
    reels_enabled: bool = False  # 14/10/2026: Wyse sem vídeo/voz; Reels só voltam com máquina maior
    reel_ofertas_enabled: bool = True  # Reel diário de ofertas (só na aba Reels, fora da grade do perfil)
    reel_ofertas_hora: str = "20:00"
    reel_leve: bool = True  # Wyse: sem zoom, música de arquivo (/srv/cache/music)
    feed_vendas_enabled: bool = False  # 14/10: oferta do dia, radar e top 5 fora do feed (dono: feed é conteúdo, venda vai p/ Stories)
    # ESTÚDIO (14/10/2026): novidades de tecnologia escritas pela IA do PC do dono (app/estudio.py)
    estudio_enabled: bool = True
    pexels_api_key: str = ""  # foto livre de fundo da capa das novidades (opcional; sem chave = ícone da editoria)
    estudio_foto_materia: bool = False  # capa com a foto da própria matéria (crédito na imagem); decisão do dono
    estudio_simples: bool = False  # True = novidades sem IA e sem o PC do dono (manchete + resumo do feed + fontes)
    estudio_estoque_alvo: int = 3  # posts prontos + tarefas esperando o PC
    estudio_validade_dias: int = 4  # notícia mais velha que isso é descartada
    estudio_dias: str = "wed,fri,sat"
    estudio_hora: str = "12:30"
    status_times: str = "12:30,20:00"  # alterna: 1º horário = divulgação do grupo, 2º = oferta do dia
    priority_keywords: str = (  # foco do dono (03/10): computador, peças, periféricos, games e celular
        "notebook,computador,pc gamer,desktop,monitor,ssd,nvme,hd externo,memória ram,memoria ram,placa de vídeo,placa de video,"
        "rtx,radeon,geforce,processador,ryzen,intel core,placa-mãe,placa mãe,placa mae,gabinete,fonte atx,water cooler,"
        "mouse,teclado,mousepad,headset,fone,webcam,microfone,cadeira gamer,gamer,roteador,mesh,switch de rede,impressora,"
        "pendrive,cartão de memória,tablet,ipad,macbook,smartphone,celular,iphone,galaxy,console,playstation,xbox,nintendo,controle")
    priority_bonus: int = 25  # tecnologia primeiro (pedido do dono)  # coleta de cupons gerais do ML  # true = publica em data/outbox.log mesmo sem Telegram
    banned_words: str = "recondicionado,usado,réplica"
    require_approval: bool = False


settings = Settings()
DATA_DIR.mkdir(exist_ok=True)
