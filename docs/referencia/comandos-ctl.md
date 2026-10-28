# Comandos do `ctl` (operacao pela linha de comando)

```bash
cd /opt/promobot && PYTHONPATH=/opt/promobot venv/bin/python -m app.ctl <comando>
```

```text
Controle do robô pela linha de comando — uso do Claude/administrador (sem servidor HTTP e sem IA de conversa).

    cd /opt/apps/promobot && docker compose exec -T bot python -m app.ctl <comando> [argumentos]

Consulta:  status | diag | fila [n] | buscar TERMO | cupons-ativos | alertas [n] | relatorio
Ações:     pausar [min] | retomar | postar [n] | cupons | desconto N | limite N | intervalo MIN [MAX] | codigo-wa
Conteúdo:  tabela | preco "<serviço> <valor>" | edu [tema] | servico "<descrição>" | aprovar | cancelar

Tudo passa por app.control: o bot executa na próxima rodada (até ~1 min). Avisos do sistema ficam em data/alertas.log.
```

Exemplos: `status`, `diag`, `alertas 20`, `pausar 60`, `retomar`, `postar 3`, `intervalo 5 8`, `desconto 30`, `limite 100`, `fila`, `buscar <termo>`, `relatorio`.

> Atencao: `postar`, `cupons`, `pausar`... sao ACOES (mudam o que vai ao ar), nao so leitura. Para so olhar use `status`, `diag`, `alertas`, `fila`.
